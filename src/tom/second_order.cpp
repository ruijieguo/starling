#include "starling/tom/second_order.hpp"

#include <sqlite3.h>

#include <variant>

#include "starling/bus/statement_writer.hpp"
#include "starling/store/sqlite_statement_store.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/schema/canonicalize.hpp"
#include "starling/tom/depth_estimator.hpp"
#include "starling/tom/limiting.hpp"

namespace starling::tom::second_order {

using persistence::StmtHandle;
using persistence::detail::bind_sv;

namespace {

std::string col(sqlite3_stmt* h, int i) {
    const char* t = reinterpret_cast<const char*>(sqlite3_column_text(h, i));
    return t ? t : "";
}

struct SourceRow {
    bool found = false;
    std::string holder, subject, predicate, hash, observed_at, provenance;
    std::string evidence_json, affect_json;
    int nesting_depth = 0;
    int derived_depth = 0;
    double confidence = 0.0;
    double salience = 0.0;
};

SourceRow load_source(sqlite3* db, std::string_view tenant,
                      std::string_view stmt_id) {
    SourceRow r;
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
        "SELECT holder_id, subject_id, predicate, canonical_object_hash, "
        "observed_at, provenance, COALESCE(evidence_json,'[]'), nesting_depth, "
        "COALESCE(derived_depth,0), confidence, salience, "
        "COALESCE(affect_json,'{}') "
        "FROM statements WHERE id=? AND tenant_id=?",
        -1, &raw, nullptr) != SQLITE_OK) return r;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, stmt_id);
    bind_sv(h.get(), 2, tenant);
    if (sqlite3_step(h.get()) != SQLITE_ROW) return r;
    r.found = true;
    r.holder = col(h.get(), 0); r.subject = col(h.get(), 1);
    r.predicate = col(h.get(), 2); r.hash = col(h.get(), 3);
    r.observed_at = col(h.get(), 4); r.provenance = col(h.get(), 5);
    r.evidence_json = col(h.get(), 6);
    r.nesting_depth = sqlite3_column_int(h.get(), 7);
    r.derived_depth = sqlite3_column_int(h.get(), 8);
    r.confidence = sqlite3_column_double(h.get(), 9);
    r.salience = sqlite3_column_double(h.get(), 10);
    r.affect_json = col(h.get(), 11);
    return r;
}

std::string lookup_self(sqlite3* db, std::string_view tenant) {
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
        "SELECT id FROM cognizers WHERE tenant_id=? AND kind='self' LIMIT 1",
        -1, &raw, nullptr) != SQLITE_OK) return "";
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant);
    if (sqlite3_step(h.get()) == SQLITE_ROW) return col(h.get(), 0);
    return "";
}

std::string first_engram(const std::string& evidence_json) {
    const auto key = evidence_json.find("engram_id");
    if (key == std::string::npos) return "";
    const auto colon = evidence_json.find(':', key);
    const auto q1 = evidence_json.find('"', colon + 1);
    const auto q2 = evidence_json.find('"', q1 + 1);
    if (q1 == std::string::npos || q2 == std::string::npos) return "";
    return evidence_json.substr(q1 + 1, q2 - q1 - 1);
}

// 永久幂等:同 (holder, subject, predicate, object) 的 tom_inferred 已存在
// 即跳过(窗口限流之上的跨窗去重)。
bool already_modeled(sqlite3* db, std::string_view tenant,
                     std::string_view holder, std::string_view subject,
                     std::string_view object_hash) {
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
        "SELECT 1 FROM statements WHERE tenant_id=? AND holder_id=? AND "
        "subject_id=? AND predicate='believes' AND canonical_object_hash=? "
        "AND provenance='tom_inferred' LIMIT 1",
        -1, &raw, nullptr) != SQLITE_OK) return false;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant);
    bind_sv(h.get(), 2, holder);
    bind_sv(h.get(), 3, subject);
    bind_sv(h.get(), 4, object_hash);
    return sqlite3_step(h.get()) == SQLITE_ROW;
}

Outcome write_nested(persistence::Connection& conn, std::string_view tenant,
                     std::string_view self_id, std::string_view subject_partner,
                     std::string_view object_stmt_id, const SourceRow& src) {
    Outcome out;
    const schema::CanonicalResult cr = schema::canonicalize_object(
        schema::CanonicalInput{std::string(object_stmt_id)});

    if (already_modeled(conn.raw(), tenant, self_id, subject_partner,
                        cr.sha256_hex)) {
        out.reason = "skip_already_modeled";
        return out;
    }
    limiting::PersistGateInput gate;
    gate.tenant_id = tenant;
    gate.holder_id = self_id;
    gate.subject_id = subject_partner;
    gate.predicate = "believes";
    gate.canonical_object_hash = cr.sha256_hex;
    gate.derived_depth = src.derived_depth;
    gate.causation_chain_len = src.nesting_depth;   // 嵌套层数即本链深度
    gate.as_of_iso8601 = src.observed_at;
    if (!limiting::should_persist_tom_statement(conn, gate)) {
        out.reason = "gated_limiting";
        return out;
    }

    extractor::ExtractedStatement st;
    st.holder_id = std::string(self_id);
    st.holder_tenant_id = std::string(tenant);
    st.holder_perspective = schema::Perspective::FIRST_PERSON;
    st.subject_kind = "cognizer";
    st.subject_id = std::string(subject_partner);
    st.predicate = "believes";
    st.object_kind = "statement";
    st.object_value = std::string(object_stmt_id);
    st.canonical_object_hash = cr.sha256_hex;
    st.modality = schema::Modality::BELIEVES;
    st.polarity = schema::Polarity::POS;
    st.confidence = src.confidence * 0.9;   // 对他者信念建模的置信折减
    st.observed_at = src.observed_at;
    st.perceived_by = {std::string(self_id)};
    st.provenance = schema::StatementProvenance::TOM_INFERRED;
    st.review_status = schema::ReviewStatus::APPROVED;
    st.derived_from = {std::string(object_stmt_id)};

    const std::string span_key =
        "tom2:" + std::string(subject_partner) + ":" + cr.sha256_hex;
    bus::StatementWriter writer(conn);
    const auto res = writer.write(st, first_engram(src.evidence_json), span_key,
                                  std::nullopt);
    if (const auto* acc = std::get_if<bus::StatementWriteAccepted>(&res)) {
        out.persisted = true;
        out.stmt_id = acc->stmt_id;
    } else if (const auto* dup =
                   std::get_if<bus::StatementWriteChunkDuplicate>(&res)) {
        out.persisted = true;   // 已有等价行(review_requested),视作完成
        out.stmt_id = dup->stmt_id;
        out.reason = "chunk_duplicate";
    }
    if (out.persisted) {
        // salience 继承(源 ×0.8,下限保留出生中性值):tom_inferred 的采样
        // provenance 因子是 0.25,若停留在中性 0.0144,权重 0.0036 < w_min
        // ——嵌套行永远不被 Replay 采样巩固,META_BELIEF 永远查空。
        // P3.b1 phase 2:写收编进 StatementStore(best-effort:失败不影响 persisted)。
        try {
            store::SqliteStatementStore(conn).inherit_salience(
                out.stmt_id, tenant, src.salience * 0.8,
                src.affect_json.empty() ? "{}" : src.affect_json);
        } catch (...) {}
    }
    return out;
}

}  // namespace

Outcome maybe_persist_second_order(persistence::Connection& conn,
                                   std::string_view tenant_id,
                                   std::string_view source_stmt_id) {
    Outcome out;
    try {
        sqlite3* db = conn.raw();
        const SourceRow src = load_source(db, tenant_id, source_stmt_id);
        if (!src.found)                    { out.reason = "skip_no_source"; return out; }
        if (src.provenance != "user_input"){ out.reason = "skip_provenance"; return out; }
        if (src.nesting_depth > 0)         { out.reason = "skip_nested_source"; return out; }
        const std::string self_id = lookup_self(db, tenant_id);
        if (self_id.empty())               { out.reason = "skip_no_self"; return out; }
        if (src.holder == self_id)         { out.reason = "skip_self_holder"; return out; }
        if (src.holder.empty())            { out.reason = "skip_empty_holder"; return out; }
        return write_nested(conn, tenant_id, self_id, src.holder,
                            source_stmt_id, src);
    } catch (const std::exception& e) {
        out.reason = std::string("error:") + e.what();
        return out;
    }
}

Outcome persist_meta_belief(persistence::Connection& conn,
                            std::string_view tenant_id,
                            std::string_view partner_id,
                            std::string_view nested_stmt_id,
                            std::string_view as_of_iso8601) {
    Outcome out;
    try {
        sqlite3* db = conn.raw();
        // Adaptive ToM Order(spec §主要流程-5):partner order < 2 不生成
        // depth=2 持久 Statement。
        if (depth_estimator::estimate(conn, partner_id, tenant_id,
                                      as_of_iso8601) < 2) {
            out.reason = "gated_order";
            return out;
        }
        const SourceRow src = load_source(db, tenant_id, nested_stmt_id);
        if (!src.found)            { out.reason = "skip_no_source"; return out; }
        if (src.nesting_depth < 1) { out.reason = "skip_not_nested"; return out; }
        if (src.holder != partner_id) { out.reason = "skip_holder_mismatch"; return out; }
        const std::string self_id = lookup_self(db, tenant_id);
        if (self_id.empty())       { out.reason = "skip_no_self"; return out; }
        return write_nested(conn, tenant_id, self_id, partner_id,
                            nested_stmt_id, src);
    } catch (const std::exception& e) {
        out.reason = std::string("error:") + e.what();
        return out;
    }
}

}  // namespace starling::tom::second_order
