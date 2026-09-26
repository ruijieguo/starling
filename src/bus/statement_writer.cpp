#include "starling/bus/statement_writer.hpp"

#include "starling/affect/affect_vector.hpp"
#include "starling/retrieval/claim_evidence.hpp"
#include <nlohmann/json.hpp>
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"
#include "starling/tom/nesting_depth_writer.hpp"

#include <chrono>
#include <cstdio>
#include <iomanip>
#include <random>
#include <sstream>
#include <string>

namespace starling::bus {

using persistence::detail::bind_sv;
using persistence::detail::iso8601_utc;
using persistence::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

namespace {

std::string random_id() {
    // Same scheme as PipelineLedger::random_id and OutboxWriter::random_event_id.
    // M0.4+1 will lift this into starling/util/uuid.hpp as real UUIDv7.
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng(), b = rng();
    std::ostringstream oss;
    oss << std::hex << std::setfill('0')
        << std::setw(8) << static_cast<std::uint32_t>(a >> 32) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(a >> 16) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(a) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(b >> 48) << '-'
        << std::setw(12) << (b & 0xFFFFFFFFFFFFULL);
    return oss.str();
}

// JSON escape for source_hash + UUIDs. P1 vocabulary is ASCII; no \uXXXX needed.
std::string json_string(std::string_view s) {
    std::string out;
    out.reserve(s.size() + 2);
    out.push_back('"');
    for (char c : s) {
        if      (c == '"')  out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else if (static_cast<unsigned char>(c) < 0x20) { /* skip control */ }
        else                out.push_back(c);
    }
    out.push_back('"');
    return out;
}

std::string source_spans_json(const starling::extractor::ExtractedStatement& s,
                              std::string_view engram_id,
                              const std::string& semantic_claim = "") {
    if (!semantic_claim.empty()) {
        auto span = nlohmann::json::parse(semantic_claim).at("source_span");
        span["chunk_index"] = s.chunk_index;
        span["observed_at"] = nlohmann::json::parse(semantic_claim).at("source_time");
        return nlohmann::json::array({span}).dump();
    }
    std::string out = "[{";
    out += "\"engram_ref\":";
    out += json_string(engram_id);
    out += ",\"chunk_index\":" + std::to_string(s.chunk_index);
    out += ",\"observed_at\":" + json_string(s.observed_at);
    out += ",\"source_hash\":" + json_string(s.source_hash);
    out += "}]";
    return out;
}

std::string evidence_json(std::string_view engram_id, std::string_view content_hash) {
    std::string out = "[{";
    out += "\"engram_ref\":" + json_string(engram_id);
    out += ",\"content_hash\":" + json_string(content_hash);
    out += ",\"status\":\"active\"";
    out += "}]";
    return out;
}

std::string perceived_by_json(const std::vector<std::string>& items) {
    std::string out = "[";
    bool first = true;
    for (const auto& id : items) {
        if (!first) out.push_back(',');
        out += json_string(id);
        first = false;
    }
    out.push_back(']');
    return out;
}

// Look up an existing APPROVED statement matching the §15.3.2 chunk-duplicate
// criteria. Returns the existing stmt_id if found, otherwise empty string.
std::string find_existing_in_chunk(
        starling::persistence::Connection& conn,
        const starling::extractor::ExtractedStatement& s,
        std::string_view evidence_engram_id,
        const std::string& semantic_claim) {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    std::string sql = "SELECT id FROM statements "
        "WHERE tenant_id = ? AND holder_id = ? "
        "  AND predicate = ? AND canonical_object_hash = ? ";
    if (semantic_claim.empty()) {
        sql += " AND evidence_json LIKE ? ";
    } else {
        // The contract distinguishes mental-state bearer, relation polarity,
        // reporting scope and exact source unit. Sharing an object hash in one
        // Engram does not make different scoped propositions duplicates.
        sql += " AND subject_kind = ? AND subject_id = ? AND holder_perspective = ? "
               " AND modality = ? AND polarity = ? AND object_kind = ? "
               " AND semantic_claim_json = ? ";
    }
    sql += " AND review_status = 'approved' ORDER BY created_at ASC LIMIT 1";
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "find_existing_in_chunk: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, s.holder_tenant_id);
    bind_sv(h.get(), 2, s.holder_id);
    bind_sv(h.get(), 3, s.predicate);
    bind_sv(h.get(), 4, s.canonical_object_hash);
    if (semantic_claim.empty()) {
        const std::string like_pat = std::string("%\"engram_ref\":\"") + std::string(evidence_engram_id) + "\"%";
        bind_sv(h.get(), 5, like_pat);
    } else {
        bind_sv(h.get(), 5, s.subject_kind);
        bind_sv(h.get(), 6, s.subject_id);
        bind_sv(h.get(), 7, schema::to_string(s.holder_perspective));
        bind_sv(h.get(), 8, schema::to_string(s.modality));
        bind_sv(h.get(), 9, schema::to_string(s.polarity));
        bind_sv(h.get(), 10, s.object_kind);
        bind_sv(h.get(), 11, semantic_claim);
    }
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_DONE) return "";
    if (rc != SQLITE_ROW) throw make_sqlite_error(db, "find_existing_in_chunk: step");
    return reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
}

void insert_statement_row(
        starling::persistence::Connection& conn,
        const std::string& stmt_id,
        const starling::extractor::ExtractedStatement& s,
        std::string_view evidence_engram_id,
        std::string_view evidence_content_hash,
        schema::ReviewStatus effective_review_status,
        const std::string& derived_from_json,
        int derived_depth,
        int nesting_depth,
        const std::string& semantic_claim) {
    sqlite3* db = conn.raw();
    const std::string ts = iso8601_utc(std::chrono::system_clock::now());
    const std::string spans = source_spans_json(s, evidence_engram_id, semantic_claim);
    const std::string evid  = evidence_json(evidence_engram_id, evidence_content_hash);
    const std::string perc  = perceived_by_json(s.perceived_by);

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
        "INSERT INTO statements("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate, object_kind, object_value,"
        "  canonical_object_hash, canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at,"
        "  valid_from, valid_to, event_time_start,"
        "  salience, affect_json, activation, last_accessed,"
        "  provenance, evidence_json, source_spans_json, perceived_by_json, scope_parties_json,"
        "  consolidation_state, review_status,"
        "  derived_from_json, derived_depth,"
        "  nesting_depth,"
        "  created_at, updated_at, semantic_claim_json, event_time_end"
        ") VALUES ("
        "  ?, ?, ?, ?,"
        "  ?, ?, ?, ?, ?,"
        "  ?, 'v1',"
        "  ?, ?, ?, ?,"
        "  ?, ?, ?,"
        "  ?, '{}', 0.0, ?,"
        "  ?, ?, ?, ?, ?,"
        "  'volatile', ?,"
        "  ?, ?,"
        "  ?,"
        "  ?, ?, ?, ?"
        ")",
        -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "StatementWriter::write: prepare INSERT statements");
    }
    StmtHandle h(raw);
    int i = 1;
    bind_sv(h.get(), i++, stmt_id);
    bind_sv(h.get(), i++, s.holder_tenant_id);
    bind_sv(h.get(), i++, s.holder_id);
    bind_sv(h.get(), i++, schema::to_string(s.holder_perspective));
    bind_sv(h.get(), i++, s.subject_kind);
    bind_sv(h.get(), i++, s.subject_id);
    bind_sv(h.get(), i++, s.predicate);
    bind_sv(h.get(), i++, s.object_kind);
    bind_sv(h.get(), i++, s.object_value);
    bind_sv(h.get(), i++, s.canonical_object_hash);
    bind_sv(h.get(), i++, schema::to_string(s.modality));
    bind_sv(h.get(), i++, schema::to_string(s.polarity));
    sqlite3_bind_double(h.get(), i++, s.confidence);
    bind_sv(h.get(), i++, s.observed_at);
    if (s.valid_from.has_value()) {
        bind_sv(h.get(), i++, *s.valid_from);
    } else {
        sqlite3_bind_null(h.get(), i++);
    }
    if (s.valid_to.has_value()) {
        bind_sv(h.get(), i++, *s.valid_to);
    } else {
        sqlite3_bind_null(h.get(), i++);
    }
    if (!semantic_claim.empty()) {
        const auto event = nlohmann::json::parse(semantic_claim).at("event_time");
        if (event.is_null()) sqlite3_bind_null(h.get(), i++);
        else bind_sv(h.get(), i++, event.at("start").get_ref<const std::string&>());
    } else if (s.event_time_start.has_value()) {
        bind_sv(h.get(), i++, *s.event_time_start);
    } else {
        sqlite3_bind_null(h.get(), i++);
    }
    // 出生 salience = 中性 AffectVector 的公式值(≈0.0144),非 0。spec §3.9
    // 「写入打分」:全中性记忆也必须 > 采样器 w_min(0.01),否则 Replay
    // 永远采不到它,volatile→consolidated 晋升被锁死(P2.o 实测根因之二)。
    sqlite3_bind_double(h.get(), i++, affect::salience(affect::AffectVector{}));
    bind_sv(h.get(), i++, ts);  // last_accessed
    bind_sv(h.get(), i++, schema::to_string(s.provenance));
    bind_sv(h.get(), i++, evid);
    bind_sv(h.get(), i++, spans);
    bind_sv(h.get(), i++, perc);
    std::string scope_parties_js;
    if (s.scope_parties.empty()) {
        sqlite3_bind_null(h.get(), i++);
    } else {
        scope_parties_js = perceived_by_json(s.scope_parties);  // reuse JSON-array-of-strings serializer
        bind_sv(h.get(), i++, scope_parties_js);
    }
    bind_sv(h.get(), i++, schema::to_string(effective_review_status));
    bind_sv(h.get(), i++, derived_from_json);
    sqlite3_bind_int(h.get(), i++, derived_depth);
    sqlite3_bind_int(h.get(), i++, nesting_depth);
    bind_sv(h.get(), i++, ts);  // created_at
    bind_sv(h.get(), i++, ts);  // updated_at
    if (semantic_claim.empty()) {
        sqlite3_bind_null(h.get(), i++);
        sqlite3_bind_null(h.get(), i++);
    } else {
        bind_sv(h.get(), i++, semantic_claim);
        const auto event = nlohmann::json::parse(semantic_claim).at("event_time");
        if (event.is_null() || event.at("end").is_null()) sqlite3_bind_null(h.get(), i++);
        else bind_sv(h.get(), i++, event.at("end").get_ref<const std::string&>());
    }

    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "StatementWriter::write: step INSERT statements");
    }
}

std::string statement_written_payload(
        const std::string& stmt_id,
        std::string_view tenant_id,
        std::string_view holder_id,
        std::string_view holder_perspective,
        std::string_view predicate,
        std::string_view canonical_object_hash,
        std::string_view review_status,
        std::string_view extraction_span_key,
        std::string_view evidence_engram_id) {
    std::string out = "{";
    out += "\"stmt_id\":"               + json_string(stmt_id);
    out += ",\"tenant_id\":"            + json_string(tenant_id);
    out += ",\"holder_id\":"            + json_string(holder_id);
    out += ",\"holder_perspective\":"   + json_string(holder_perspective);
    out += ",\"predicate\":"            + json_string(predicate);
    out += ",\"canonical_object_hash\":"+ json_string(canonical_object_hash);
    out += ",\"consolidation_state\":\"volatile\"";
    out += ",\"review_status\":"        + json_string(review_status);
    out += ",\"extraction_span_key\":"  + json_string(extraction_span_key);
    out += ",\"engram_ref_id\":"        + json_string(evidence_engram_id);
    out += "}";
    return out;
}

}  // namespace

StatementWriteOutcome StatementWriter::write(
        const starling::extractor::ExtractedStatement& s,
        std::string_view evidence_engram_id,
        std::string_view extraction_span_key,
        std::optional<std::string> causation_parent_event_id) {

    const std::string stmt_id = random_id();

    // For the evidence_json we need the engram's content_hash. Query for it
    // here rather than threading it through, so callers don't have to know.
    sqlite3* db = conn_.raw();
    std::string content_hash;
    std::string source_time;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
                "SELECT content_hash, created_at FROM engrams WHERE id = ? AND tenant_id = ?",
                -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "StatementWriter::write: prepare engrams content_hash");
        }
        StmtHandle h(raw);
        bind_sv(h.get(), 1, evidence_engram_id);
        bind_sv(h.get(), 2, s.holder_tenant_id);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            content_hash = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
            source_time = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
        }
    }

    // New propositions keep their parent lineage, never a copied direct
    // admission certificate. State-only consolidation does not enter this path.
    std::string semantic_claim;
    if (s.derived_from.empty() && s.provenance == schema::StatementProvenance::USER_INPUT
        && !s.semantic_claim_json.empty()) {
        retrieval::StatementRow claim_input;
        claim_input.semantic_claim_json = s.semantic_claim_json;
        auto claim = retrieval::parse_claim_evidence(claim_input);
        if (!claim.is_object()) throw std::invalid_argument("StatementWriter: malformed_claim");
        claim["source_time"] = source_time;
        if (!claim.contains("source_span") ||
            claim["source_span"].value("engram_ref", "") != evidence_engram_id ||
            claim["source_span"].value("source_hash", "") != s.source_hash || source_time.empty())
            throw std::invalid_argument("StatementWriter: inconsistent_claim source");
        semantic_claim = claim.dump();
        retrieval::StatementRow row;
        row.tenant_id = s.holder_tenant_id; row.holder_id = s.holder_id;
        row.holder_perspective = schema::to_string(s.holder_perspective);
        row.subject_id = s.subject_id; row.subject_kind = s.subject_kind; row.predicate = s.predicate;
        row.object_kind = s.object_kind; row.object_value = s.object_value;
        row.nesting_depth = s.llm_nesting_depth;
        row.modality = schema::to_string(s.modality);
        row.polarity = schema::to_string(s.polarity);
        row.semantic_claim_json = semantic_claim;
        row.source_spans_json = source_spans_json(s, evidence_engram_id, semantic_claim);
        const auto reason = retrieval::claim_evidence_error(conn_, row);
        if (!reason.empty()) throw std::invalid_argument("StatementWriter: " + reason);
    }

    // Compare finalized source evidence, after trusted observation time is
    // attached. Legacy rows retain the existing chunk-level duplicate rule.
    const std::string existing = find_existing_in_chunk(conn_, s, evidence_engram_id, semantic_claim);
    const auto effective = existing.empty() ? s.review_status : schema::ReviewStatus::REVIEW_REQUESTED;

    // Compute derived_from_json and derived_depth.
    int derived_depth = 0;
    std::string derived_from_json = "[]";
    if (!s.derived_from.empty()) {
        std::ostringstream oss;
        oss << "[";
        for (size_t k = 0; k < s.derived_from.size(); ++k) {
            if (k) oss << ",";
            oss << json_string(s.derived_from[k]);
        }
        oss << "]";
        derived_from_json = oss.str();

        // Look up max(derived_depth) among parent rows in the current tenant.
        std::string in_clause;
        for (size_t k = 0; k < s.derived_from.size(); ++k) {
            if (k) in_clause += ",";
            in_clause += "?";
        }
        const std::string depth_sql =
            "SELECT MAX(derived_depth) FROM statements "
            "WHERE tenant_id = ? AND id IN (" + in_clause + ")";
        sqlite3_stmt* q_raw = nullptr;
        if (sqlite3_prepare_v2(conn_.raw(), depth_sql.c_str(), -1, &q_raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(conn_.raw(), "StatementWriter::write: prepare MAX(derived_depth)");
        }
        StmtHandle q(q_raw);
        bind_sv(q.get(), 1, s.holder_tenant_id);
        for (size_t k = 0; k < s.derived_from.size(); ++k)
            sqlite3_bind_text(q.get(), static_cast<int>(k + 2),
                              s.derived_from[k].c_str(), -1, SQLITE_TRANSIENT);
        int max_parent_depth = 0;
        // MAX() returns SQL NULL when no matching parent rows exist; sqlite3_column_int
        // reports NULL as 0, so the child gets depth=1. Orphan parents are tolerated
        // by design — they are not an error condition.
        if (sqlite3_step(q.get()) == SQLITE_ROW)
            max_parent_depth = sqlite3_column_int(q.get(), 0);
        derived_depth = max_parent_depth + 1;
    }

    // Compute nesting_depth: 0 for non-statement objects; parent.nesting_depth+1
    // for object_kind=="statement". Uses the default soft ceiling
    // (max_nesting_depth=32); throws NestingDepthOverflow only beyond it.
    const int nesting_depth = tom::nesting_depth_writer::compute_nesting_depth(conn_, s);

    insert_statement_row(conn_, stmt_id, s, evidence_engram_id, content_hash, effective,
                         derived_from_json, derived_depth, nesting_depth, semantic_claim);

    // Build and append the bus_events row.
    const std::string canonical_key = std::string(extraction_span_key);
    const std::string window_bucket  = compute_window_bucket(
        "statement.written", std::chrono::system_clock::now());

    BusEvent ev;
    ev.tenant_id        = s.holder_tenant_id;
    ev.event_type       = "statement.written";
    ev.primary_id       = stmt_id;
    ev.aggregate_id     = stmt_id;
    // 05_bus.md:273: accumulate parent chain + parent.event_id.
    if (causation_parent_event_id.has_value()) {
        ev.causation_chain = compute_child_chain(
            conn_, *causation_parent_event_id);
    }
    const std::string causation_root =
        ev.causation_chain.empty() ? std::string{} : ev.causation_chain.front();
    ev.idempotency_key  = compute_idempotency_key(
        "statement.written", stmt_id, canonical_key, causation_root, window_bucket);
    ev.payload_json     = statement_written_payload(
        stmt_id, s.holder_tenant_id, s.holder_id,
        schema::to_string(s.holder_perspective),
        s.predicate, s.canonical_object_hash,
        schema::to_string(effective), extraction_span_key,
        evidence_engram_id);

    OutboxWriter writer(conn_);
    writer.append(ev);

    if (!existing.empty()) {
        return StatementWriteChunkDuplicate{
            .stmt_id          = stmt_id,
            .original_stmt_id = existing,
            .event_id         = ev.event_id,
        };
    }
    return StatementWriteAccepted{
        .stmt_id         = stmt_id,
        .event_id        = ev.event_id,
        .outbox_sequence = ev.outbox_sequence,
    };
}

}  // namespace starling::bus
