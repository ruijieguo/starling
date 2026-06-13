#include "starling/bus/bus.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/subscriber_pump.hpp"
#include "starling/bus/conflict_probe.hpp"
#include "starling/bus/normalized_interval.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/bus/statement_writer.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram_store.hpp"
#include "starling/evidence/evidence_validator.hpp"
#include "starling/extractor/statement_validator.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/store/sqlite_statement_store.hpp"
#include "starling/schema/enums.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <variant>

namespace starling::bus {

namespace {

std::string source_identity_hash(const starling::evidence::SourceIdentity& s) {
    std::string blob;
    blob.reserve(64 + s.adapter_name.size() + s.source_item_id.size() + s.source_version.size());
    blob += s.adapter_name;    blob += '\x1f';
    blob += s.source_item_id;  blob += '\x1f';
    blob += s.source_version;  blob += '\x1f';
    blob += std::to_string(s.chunk_index);
    return starling::crypto::sha256_hex(blob);
}

std::string json_string(std::string_view sv) {
    std::string out;
    out.reserve(sv.size() + 2);
    out.push_back('"');
    for (char c : sv) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x",
                                  static_cast<unsigned char>(c));
                    out += buf;
                } else {
                    out.push_back(c);
                }
        }
    }
    out.push_back('"');
    return out;
}

std::string accepted_payload(const starling::evidence::Engram& e) {
    std::ostringstream os;
    os << "{"
       << "\"engram_id\":"      << json_string(e.id) << ","
       << "\"content_hash\":"   << json_string(e.content_hash) << ","
       << "\"retention_mode\":" << json_string(starling::schema::to_string(e.retention_mode)) << ","
       << "\"source_kind\":"    << json_string(starling::schema::to_string(e.source_kind)) << ","
       << "\"tenant_id\":"      << json_string(e.tenant_id)
       << "}";
    return os.str();
}

std::string no_store_payload(const starling::evidence::EngramInput& i) {
    std::ostringstream os;
    os << "{"
       << "\"tenant_id\":"      << json_string(i.tenant_id) << ","
       << "\"source_kind\":"    << json_string(starling::schema::to_string(i.source_kind)) << ","
       << "\"privacy_class\":"  << json_string(starling::schema::to_string(i.privacy_class)) << ","
       << "\"adapter_name\":"   << json_string(i.source.adapter_name) << ","
       << "\"source_item_id\":" << json_string(i.source.source_item_id) << ","
       << "\"source_version\":" << json_string(i.source.source_version) << ","
       << "\"chunk_index\":"    << i.source.chunk_index << ","
       << "\"reason\":\"self_pollution_guard_or_producer_declared_no_store\""
       << "}";
    return os.str();
}

std::string idempotent_payload(const starling::evidence::Engram& existing) {
    std::ostringstream os;
    os << "{"
       << "\"existing_engram_id\":" << json_string(existing.id) << ","
       << "\"content_hash\":"       << json_string(existing.content_hash) << ","
       << "\"tenant_id\":"          << json_string(existing.tenant_id)
       << "}";
    return os.str();
}

BusEvent make_event(
    starling::persistence::Connection& conn,
    std::string_view event_type,
    std::string_view primary_id,
    std::string_view aggregate_id,
    std::string_view tenant_id,
    std::string payload_json,
    const std::optional<std::string>& causation_parent) {

    BusEvent e;
    e.tenant_id    = std::string(tenant_id);
    e.event_type   = std::string(event_type);
    e.primary_id   = std::string(primary_id);
    e.aggregate_id = std::string(aggregate_id);
    // 05_bus.md:273: N.causation_chain = parent.causation_chain + [parent.event_id].
    // compute_child_chain pulls parent's chain from bus_events and appends
    // parent.event_id; throws CausationOverflow when the resulting chain
    // exceeds the depth-3 cap (caught by Bus::write to emit system.runaway).
    if (causation_parent) {
        e.causation_chain = compute_child_chain(conn, *causation_parent);
    }
    const std::string causation_root =
        e.causation_chain.empty() ? std::string{} : e.causation_chain.front();
    const std::string window_bucket = compute_window_bucket(
        event_type, std::chrono::system_clock::now());
    e.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, primary_id, causation_root, window_bucket);
    e.payload_json = std::move(payload_json);
    return e;
}

// 32 random hex chars for statement_edges.id. Per-edge primary key only —
// not stored in user-facing protocols, so no UUID-v4/v7 nibble bits required.
std::string random_edge_id() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

void insert_statement_edge(
    starling::persistence::Connection& conn,
    std::string_view src_id,
    std::string_view dst_id,
    std::string_view tenant_id,
    std::string_view edge_kind,
    std::optional<std::string> canonical_conflict_key = std::nullopt) {
    const char* sql =
        "INSERT INTO statement_edges"
        "(id, tenant_id, src_id, dst_id, edge_kind, canonical_conflict_key, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw persistence::detail::make_sqlite_error(conn.raw(), "insert_statement_edge prepare");
    starling::persistence::StmtHandle h(raw);
    const std::string edge_id = random_edge_id();
    const std::string now_iso = persistence::detail::iso8601_utc(std::chrono::system_clock::now());
    persistence::detail::bind_sv(h.get(), 1, edge_id);
    persistence::detail::bind_sv(h.get(), 2, tenant_id);
    persistence::detail::bind_sv(h.get(), 3, src_id);
    persistence::detail::bind_sv(h.get(), 4, dst_id);
    persistence::detail::bind_sv(h.get(), 5, edge_kind);
    if (canonical_conflict_key.has_value()) {
        sqlite3_bind_text(h.get(), 6,
                          canonical_conflict_key->c_str(), -1, SQLITE_STATIC);
    } else {
        sqlite3_bind_null(h.get(), 6);
    }
    persistence::detail::bind_sv(h.get(), 7, now_iso);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_DONE) return;
    if (rc == SQLITE_CONSTRAINT && canonical_conflict_key.has_value()) {
        // UNIQUE partial index violation: a conflicts_with edge with this
        // canonical_conflict_key already exists. Silently drop the duplicate
        // and emit a WARN to stderr — per spec §8.4.
        std::fprintf(stderr,
            "[bus.conflict_key] WARN dedup hit on canonical_conflict_key=%s "
            "(edge_kind=conflicts_with, tenant=%s); existing edge retained.\n",
            canonical_conflict_key->c_str(),
            std::string(tenant_id).c_str());
        return;
    }
    throw persistence::detail::make_sqlite_error(conn.raw(), "insert_statement_edge step");
}

std::string conflict_payload(const ConflictMatch& m, std::string_view new_stmt_id) {
    std::ostringstream os;
    os << "{"
       << "\"new_statement_id\":"  << json_string(new_stmt_id) << ","
       << "\"old_statement_id\":"  << json_string(m.matched_statement_id) << ","
       << "\"conflict_kind\":"     << json_string(to_string(m.kind)) << ","
       << "\"conflict_key\":"      << json_string(m.conflict_key_hex)
       << "}";
    return os.str();
}

// Apply the §15.3.1 mild-correction path. Caller MUST hold a TransactionGuard.
// Updates S_old's confidence (to new_confidence if higher) and appends a
// ConfidenceEvent to confidence_history_json.  provenance is intentionally
// NOT touched — that is the invariant being verified by TC-Q3a-001.
void apply_mild_correction(
    starling::persistence::Connection& conn,
    const ConflictMatch& match,
    double new_confidence,
    std::string_view new_evidence_engram_id) {

    // Read current confidence + confidence_history_json from S_old.
    double   old_confidence   = 0.0;
    std::string history_json  = "[]";
    {
        const char* sql =
            "SELECT confidence, confidence_history_json FROM statements "
            "WHERE id = ? AND tenant_id = ?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw persistence::detail::make_sqlite_error(conn.raw(), "mild_correction: fetch s_old prepare");
        starling::persistence::StmtHandle h(raw);
        persistence::detail::bind_sv(h.get(), 1, match.matched_statement_id);
        persistence::detail::bind_sv(h.get(), 2, match.matched_tenant_id);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            old_confidence = sqlite3_column_double(h.get(), 0);
            const auto* txt = sqlite3_column_text(h.get(), 1);
            if (txt) history_json = reinterpret_cast<const char*>(txt);
        }
    }

    // Build the appended confidence_history_json.
    // Append {"old_confidence":<v>,"ts":"<iso>","evidence_engram_ref":<eid>} to array.
    const std::string ts = persistence::detail::iso8601_utc(std::chrono::system_clock::now());
    // Strip trailing ']'; we'll re-close after appending. We only emit this column
    // ourselves (compact, no whitespace), so the last non-']' char is either '['
    // for an empty array or the closing '}' of the previous entry.
    if (!history_json.empty() && history_json.back() == ']') {
        history_json.pop_back();
    }
    if (!history_json.empty() && history_json.back() != '[') {
        // Previous entry exists — separate with comma.
        history_json.push_back(',');
    }
    // Format old_confidence with %.6g (6 significant digits, shortest representation).
    char conf_buf[32];
    std::snprintf(conf_buf, sizeof(conf_buf), "%.6g", old_confidence);
    history_json += "{\"old_confidence\":" + std::string(conf_buf);
    history_json += ",\"ts\":" + json_string(ts);
    history_json += ",\"evidence_engram_ref\":" + json_string(new_evidence_engram_id);
    history_json += "}]";

    // Only raise confidence; never lower it in a mild-correction path.
    const double updated_confidence = (new_confidence > old_confidence)
        ? new_confidence : old_confidence;

    // UPDATE S_old: bump confidence + append to history.  provenance NOT updated.
    // P3.b1 phase 2:写收编进 StatementStore(同 conn)。
    store::SqliteStatementStore(conn).apply_mild_correction(
        match.matched_statement_id, match.matched_tenant_id,
        updated_confidence, history_json, ts);
}

// Apply the §15.3.4 4-item atomic SUPERSEDES path. Caller MUST hold a
// TransactionGuard; this function never opens its own transaction. On any
// SQL error this throws and the caller's tx destructor rolls back.
//
// Step 1 (StatementWriter::write — INSERT S_new + emit statement.written) is
// already done by Bus::write before the conflict-kind switch, so this helper
// starts at step 2. The caller passes the freshly-written S_new id in
// new_stmt_id.
void apply_supersedes_atomic(
    starling::persistence::Connection& conn,
    const starling::extractor::ExtractedStatement& stmt,
    const std::optional<std::string>& causation_parent_event_id,
    const ConflictMatch& match,
    std::string_view new_stmt_id) {

    // Step 2: SUPERSEDES edge S_new -> S_old.
    insert_statement_edge(
        conn, new_stmt_id, match.matched_statement_id,
        match.matched_tenant_id, "supersedes", std::nullopt);

    // Step 3: UPDATE S_old to archived. Bypasses replaying_reconsolidating
    // per §3.5 T7-P1 — the consolidated -> archived transition is direct.
    // The WHERE includes consolidation_state='consolidated' as a defensive
    // guard against stale probe matches; if the row's state has changed
    // between probe and apply, sqlite3_changes() will be 0 and we throw.
    {
        // P3.b1 phase 2:写收编进 StatementStore;守卫 'consolidated' + updated_at,
        // changes!=1 检查保留。
        const std::string now_iso =
            persistence::detail::iso8601_utc(std::chrono::system_clock::now());
        if (store::SqliteStatementStore(conn).archive(
                {match.matched_statement_id}, match.matched_tenant_id,
                "consolidated", now_iso) != 1) {
            throw std::runtime_error(
                "supersedes_path: S_old row missing or wrong state at archive time");
        }
    }

    // Step 4a: emit statement.archived.
    const char* archive_reason =
        (match.kind == ConflictKind::DirectContradiction) ? "direct_contradiction"
                                                          : "superseding";
    OutboxWriter ow(conn);
    {
        std::ostringstream payload;
        payload << "{"
                << "\"reason\":"        << json_string(archive_reason) << ","
                << "\"superseded_by\":" << json_string(new_stmt_id)
                << "}";
        BusEvent ev = make_event(
            conn,
            "statement.archived",
            match.matched_statement_id,         // primary_id = S_old
            match.matched_supersedes_root_id,   // aggregate_id = supersedes root
            match.matched_tenant_id,
            payload.str(),
            causation_parent_event_id);
        ow.append(ev);
    }

    // Step 4b: emit statement.superseded.
    {
        std::ostringstream payload;
        payload << "{"
                << "\"new_statement_id\":" << json_string(new_stmt_id) << ","
                << "\"old_statement_id\":" << json_string(match.matched_statement_id) << ","
                << "\"conflict_kind\":"    << json_string(to_string(match.kind))
                << "}";
        BusEvent ev = make_event(
            conn,
            "statement.superseded",
            new_stmt_id,                        // primary_id = S_new
            match.matched_supersedes_root_id,   // aggregate_id = supersedes root
            stmt.holder_tenant_id,
            payload.str(),
            causation_parent_event_id);
        ow.append(ev);
    }
}

}  // namespace

Bus::Bus(starling::persistence::SqliteAdapter& adapter) : adapter_(adapter) {}

AppendEvidenceOutcome Bus::append_evidence(
    const starling::evidence::EngramInput& input,
    std::optional<std::string> causation_parent_event_id) {

    auto& conn = adapter_.connection();
    starling::persistence::TransactionGuard tx(conn);
    OutboxWriter writer(conn);

    auto outcome = starling::evidence::EvidenceValidator::validate(input, conn);

    if (auto* rej = std::get_if<starling::evidence::ValidationReject>(&outcome)) {
        return AppendEvidenceRejected{rej->reason};
    }

    if (std::holds_alternative<starling::evidence::ValidationNoStore>(outcome)) {
        const std::string sid_hash = source_identity_hash(input.source);
        BusEvent ev = make_event(
            conn,
            "evidence.no_store_audit",
            sid_hash, sid_hash,
            input.tenant_id,
            no_store_payload(input),
            causation_parent_event_id);
        writer.append_already_delivered(ev);
        tx.commit();
        return AppendEvidenceNoStore{ev.event_id};
    }

    if (auto* hit = std::get_if<starling::evidence::ValidationIdempotentHit>(&outcome)) {
        const auto& existing = hit->existing;
        BusEvent ev = make_event(
            conn,
            "evidence.idempotent_hit",
            existing.id, existing.id,
            input.tenant_id,
            idempotent_payload(existing),
            causation_parent_event_id);
        writer.append_already_delivered(ev);
        tx.commit();
        return AppendEvidenceIdempotent{
            starling::evidence::EngramRef{existing.id, existing.content_hash, existing.retention_mode},
            ev.event_id};
    }

    auto& proceed = std::get<starling::evidence::ValidationProceed>(outcome);
    auto engram = starling::evidence::EngramStore::put(input, proceed.resolved_policy, conn);
    BusEvent ev = make_event(
        conn,
        "evidence.appended",
        engram.id, engram.id,
        input.tenant_id,
        accepted_payload(engram),
        causation_parent_event_id);
    writer.append(ev);
    tx.commit();
    return AppendEvidenceAccepted{
        starling::evidence::EngramRef{engram.id, engram.content_hash, engram.retention_mode},
        ev.event_id,
        ev.outbox_sequence};
}

StatementWriteOutcome Bus::write(
    const starling::extractor::ExtractedStatement& stmt,
    std::string_view evidence_engram_id,
    std::string_view extraction_span_key,
    std::optional<std::string> causation_parent_event_id) {

    auto& conn = adapter_.connection();
    try {
        return write_impl(stmt, evidence_engram_id, extraction_span_key,
                          causation_parent_event_id);
    } catch (const CausationOverflow& ovf) {
        // Spec 05_bus.md:274: "len(causation_chain) > 3 → 拒绝派生事件，
        // emit system.runaway(chain_root, depth, source_event_id)".
        // The TransactionGuard inside write_impl already rolled back the
        // would-be derived write when the exception propagated. We now emit
        // the system.runaway event in its own transaction so the storm is
        // observable even though the derived write is rejected.
        starling::persistence::TransactionGuard runaway_tx(conn);
        std::ostringstream payload;
        payload << "{"
                << "\"chain_root\":"      << json_string(ovf.chain_root)      << ","
                << "\"source_event_id\":" << json_string(ovf.source_event_id) << ","
                << "\"depth\":"           << ovf.depth
                << "}";
        BusEvent runaway = make_event(
            conn,
            "system.runaway",
            ovf.source_event_id,         // primary_id = the parent that triggered overflow
            ovf.chain_root,              // aggregate_id = chain root (storm key)
            stmt.holder_tenant_id,
            payload.str(),
            std::nullopt);               // runaway is itself a root event — no parent
        OutboxWriter ow(conn);
        ow.append(runaway);
        runaway_tx.commit();
        // Re-throw so callers (Python binding, tests) see the rejection.
        throw std::runtime_error(
            "Bus::write rejected: causation_chain depth > 3, system.runaway emitted");
    }
}

StatementWriteOutcome Bus::write_impl(
    const starling::extractor::ExtractedStatement& stmt,
    std::string_view evidence_engram_id,
    std::string_view extraction_span_key,
    std::optional<std::string> causation_parent_event_id) {

    auto& conn = adapter_.connection();
    starling::persistence::TransactionGuard tx(conn);

    // M0.7: cross-tenant derived_from gate (§15.3.1 TC-NEG-CROSSTENANT).
    // Build the resolver closure: queries tenant_id of a parent statement by id.
    // Uses StmtHandle RAII; checks prepare_v2 return code per Task 7 quality bar.
    auto resolve_parent_tenant =
        [&conn, &stmt](const std::string& parent_id) -> std::string {
        const char* same_tenant_sql =
            "SELECT tenant_id FROM statements WHERE id = ? AND tenant_id = ? LIMIT 1";
        sqlite3_stmt* same_raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), same_tenant_sql, -1, &same_raw, nullptr) != SQLITE_OK)
            throw persistence::detail::make_sqlite_error(conn.raw(), "Bus::write resolve_parent_tenant same-tenant prepare");
        {
            starling::persistence::StmtHandle h(same_raw);
            persistence::detail::bind_sv(h.get(), 1, parent_id);
            persistence::detail::bind_sv(h.get(), 2, stmt.holder_tenant_id);
            if (sqlite3_step(h.get()) == SQLITE_ROW) {
                return stmt.holder_tenant_id;
            }
        }

        const char* sql =
            "SELECT DISTINCT tenant_id FROM statements WHERE id = ? LIMIT 2";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw persistence::detail::make_sqlite_error(conn.raw(), "Bus::write resolve_parent_tenant prepare");
        starling::persistence::StmtHandle h(raw);
        persistence::detail::bind_sv(h.get(), 1, parent_id);
        std::string out;
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            if (const char* txt = reinterpret_cast<const char*>(
                    sqlite3_column_text(h.get(), 0))) {
                out = txt;
            }
        }
        if (!out.empty() && sqlite3_step(h.get()) == SQLITE_ROW) {
            return "ambiguous:" + parent_id;
        }
        return out;
    };

    const auto v = starling::extractor::validate_for_write(stmt, resolve_parent_tenant);
    if (!v.ok()) {
        throw std::runtime_error(
            "validate_for_write rejected: " + v.error_kind + " — " + v.detail);
    }

    // Apply review_status override (cross-tenant protocol path sets REVIEW_REQUESTED).
    starling::extractor::ExtractedStatement effective = stmt;
    if (v.review_status_override) {
        effective.review_status = *v.review_status_override;
    }

    // M0.5: detect conflicts BEFORE writing so the partial_overlap / adjacent
    // edge writes (and direct_contradiction / superseding atomic SUPERSEDES in
    // Task 8) all happen in one transaction.
    const NormalizedInterval iv_new = normalize_interval(
        effective.valid_from, effective.valid_to, effective.event_time_start);
    ConflictProbe probe(conn);
    const auto match = probe.scan(effective, iv_new);

    StatementWriter writer(conn);
    auto outcome = writer.write(
        effective, evidence_engram_id, extraction_span_key, causation_parent_event_id);

    if (match.has_value()) {
        const std::string new_stmt_id =
            std::visit([](auto&& write_outcome) -> std::string {
                return write_outcome.stmt_id;
            }, outcome);

        switch (match->kind) {
            case ConflictKind::DirectContradiction:
            case ConflictKind::Superseding:
                // M0.5 Task 8: §15.3.4 atomic SUPERSEDES path. The
                // StatementWriter::write call above already executed step 1
                // (INSERT S_new + emit statement.written). The helper now
                // performs steps 2-4 inside the same TransactionGuard:
                //   2. INSERT statement_edges (S_new -> S_old, supersedes)
                //   3. UPDATE S_old.consolidation_state = 'archived'
                //      (bypasses replaying_reconsolidating per §3.5 T7-P1;
                //       defensive guard rolls the tx back if S_old changed
                //       state between probe and apply)
                //   4. INSERT bus_events: statement.archived (primary=S_old)
                //                       + statement.superseded (primary=S_new)
                // Any throw triggers TransactionGuard's destructor rollback —
                // S_new is not persisted, S_old retains 'consolidated', no
                // edge, no archive/superseded events.
                apply_supersedes_atomic(
                    conn, effective, causation_parent_event_id, *match, new_stmt_id);
                break;

            case ConflictKind::PartialOverlap: {
                insert_statement_edge(
                    conn, new_stmt_id, match->matched_statement_id,
                    effective.holder_tenant_id, "conflicts_with",
                    match->conflict_key_hex);

                // Build the belief.conflict event manually rather than via
                // make_event() because debounce semantics require the
                // canonical_key in the idempotency hash to be the
                // canonical_conflict_key (not primary_id). This pins
                // idempotency to (event_type, conflict_key, causation_root,
                // 10s window) so repeated belief.conflict emissions in the
                // same window collide on UNIQUE(idempotency_key) and the
                // catch below drops the dupes. primary_id stays = new_stmt_id
                // so the event row carries traceability back to S_new.
                BusEvent ev;
                ev.tenant_id    = effective.holder_tenant_id;
                ev.event_type   = "belief.conflict";
                ev.primary_id   = new_stmt_id;
                ev.aggregate_id = match->conflict_key_hex;
                if (causation_parent_event_id) {
                    ev.causation_chain = compute_child_chain(
                        conn, *causation_parent_event_id);
                }
                const std::string causation_root =
                    ev.causation_chain.empty() ? std::string{} : ev.causation_chain.front();
                const std::string window_bucket = compute_window_bucket(
                    "belief.conflict", std::chrono::system_clock::now());
                ev.idempotency_key = compute_idempotency_key(
                    "belief.conflict",
                    match->conflict_key_hex,   // aggregate_id
                    match->conflict_key_hex,   // canonical_key (debounce on conflict_key, not primary_id)
                    causation_root,
                    window_bucket);
                ev.payload_json = conflict_payload(*match, new_stmt_id);

                OutboxWriter ow(conn);
                try {
                    ow.append(ev);
                } catch (const starling::persistence::SqliteError& e) {
                    if (e.code() != SQLITE_CONSTRAINT_UNIQUE) throw;
                    // Debounced: another belief.conflict with the same
                    // canonical_conflict_key already landed in this 10s window.
                }
                break;
            }

            case ConflictKind::MildCorrection:
                // §15.3.1: same polarity, non-severe conflict — bump S_old's
                // confidence (if S_new is higher) and append the prior value to
                // S_old.confidence_history_json.  provenance is NOT touched —
                // that invariant is verified by TC-Q3a-001.
                apply_mild_correction(
                    conn, *match, effective.confidence, evidence_engram_id);
                break;

            case ConflictKind::Adjacent:
                insert_statement_edge(
                    conn, new_stmt_id, match->matched_statement_id,
                    effective.holder_tenant_id, "adjacent",
                    match->conflict_key_hex);
                break;
        }
    }

    tx.commit();

    // 统一 post-write 泵: 5 subscriber 各 SAVEPOINT 隔离 (spec §11).
    const std::string now_iso = persistence::detail::iso8601_utc(std::chrono::system_clock::now());
    SubscriberPump::run_post_write(adapter_, conn, now_iso);

    return outcome;
}

}  // namespace starling::bus
