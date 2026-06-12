// P3.a2:mentalizing 7 API 的后三个(二阶查询 / 预测依据 / 承诺查询)。
#include "starling/tom/mentalizing.hpp"

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

#include <sqlite3.h>
#include <string>
#include <vector>

namespace starling::tom::mentalizing {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

namespace {

constexpr const char* kCols =
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, modality, "
    "polarity, confidence, observed_at, valid_from, valid_to, "
    "consolidation_state, review_status, evidence_json";

retrieval::StatementRow row_from(sqlite3_stmt* raw, int base = 0) {
    auto t = [&](int i) -> std::string {
        const unsigned char* p = sqlite3_column_text(raw, base + i);
        return p ? std::string(reinterpret_cast<const char*>(p)) : std::string{};
    };
    retrieval::StatementRow r;
    r.id = t(0); r.tenant_id = t(1); r.holder_id = t(2);
    r.holder_perspective = t(3); r.subject_kind = t(4); r.subject_id = t(5);
    r.predicate = t(6); r.object_kind = t(7); r.object_value = t(8);
    r.canonical_object_hash = t(9); r.modality = t(10); r.polarity = t(11);
    r.confidence = sqlite3_column_double(raw, base + 12);
    r.observed_at = t(13); r.valid_from = t(14); r.valid_to = t(15);
    r.consolidation_state = t(16); r.review_status = t(17);
    r.evidence_json = t(18);
    return r;
}

constexpr const char* kStableTail =
    "   AND consolidation_state IN ('consolidated','archived')"
    "   AND review_status NOT IN ('rejected','pending_review')";

}  // namespace

std::vector<NestedBelief> what_does_X_think_Y_believes(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view tenant,
    std::string_view as_of)
{
    auto& conn = adapter.connection();
    sqlite3* db = conn.raw();
    // outer:holder=X 对 Y 的嵌套信念;inner:被引用的原语句(JOIN by
    // outer.object_value = inner.id)。inner 不限 consolidation——外层可信
    // 即可展示内层内容(外层已过稳定态过滤)。
    const std::string sql =
        std::string("SELECT ") +
        "o.id, o.tenant_id, o.holder_id, o.holder_perspective, o.subject_kind, "
        "o.subject_id, o.predicate, o.object_kind, o.object_value, "
        "o.canonical_object_hash, o.modality, o.polarity, o.confidence, "
        "o.observed_at, o.valid_from, o.valid_to, o.consolidation_state, "
        "o.review_status, o.evidence_json, "
        "i.id, i.tenant_id, i.holder_id, i.holder_perspective, i.subject_kind, "
        "i.subject_id, i.predicate, i.object_kind, i.object_value, "
        "i.canonical_object_hash, i.modality, i.polarity, i.confidence, "
        "i.observed_at, i.valid_from, i.valid_to, i.consolidation_state, "
        "i.review_status, i.evidence_json "
        "FROM statements o JOIN statements i "
        "  ON i.id = o.object_value AND i.tenant_id = o.tenant_id "
        "WHERE o.tenant_id = ?1 AND o.holder_id = ?2 AND o.subject_id = ?3 "
        "  AND o.object_kind = 'statement' AND o.nesting_depth >= 1 "
        "  AND (o.valid_from IS NULL OR o.valid_from <= ?4) "
        "  AND (o.valid_to   IS NULL OR o.valid_to   >  ?4) ";
    // 稳定态过滤限定 o. 前缀(kStableTail 是无前缀版,这里手写):
    const std::string full = sql +
        "  AND o.consolidation_state IN ('consolidated','archived') "
        "  AND o.review_status NOT IN ('rejected','pending_review') "
        "ORDER BY o.observed_at DESC";

    std::vector<NestedBelief> out;
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, full.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "what_does_X_think_Y_believes: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant);
    bind_sv(h.get(), 2, x);
    bind_sv(h.get(), 3, y);
    bind_sv(h.get(), 4, as_of);
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        NestedBelief nb;
        nb.outer = row_from(h.get(), 0);
        nb.inner = row_from(h.get(), 19);
        out.push_back(std::move(nb));
    }
    return out;
}

PredictionBasis predict_X_would(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view situation_keyword,
    std::string_view tenant,
    std::string_view as_of)
{
    auto& conn = adapter.connection();
    sqlite3* db = conn.raw();
    PredictionBasis basis;
    const std::string like = "%" + std::string(situation_keyword) + "%";

    auto run = [&](const std::string& extra,
                   std::vector<retrieval::StatementRow>& sink,
                   bool with_like) {
        const std::string sql = std::string("SELECT ") + kCols +
            " FROM statements WHERE tenant_id = ?1 AND holder_id = ?2 " +
            extra + kStableTail +
            "   AND (valid_from IS NULL OR valid_from <= ?3)"
            "   AND (valid_to   IS NULL OR valid_to   >  ?3)"
            " ORDER BY observed_at DESC LIMIT 20";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "predict_X_would: prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, tenant);
        bind_sv(h.get(), 2, x);
        bind_sv(h.get(), 3, as_of);
        if (with_like) bind_sv(h.get(), 4, like);
        while (sqlite3_step(h.get()) == SQLITE_ROW)
            sink.push_back(row_from(h.get()));
    };
    // 信念:situation 关键词命中 object_value 或 subject_id。
    run(" AND (object_value LIKE ?4 OR subject_id LIKE ?4) "
        " AND predicate NOT IN ('prefers') ", basis.beliefs, true);
    // 偏好:全量(行为预测的稳定底色)。
    run(" AND predicate = 'prefers' ", basis.preferences, false);
    // 活跃承诺语句。
    run(" AND id IN (SELECT stmt_id FROM commitments WHERE tenant_id = ?1 "
        "             AND state IN ('ACTIVE','created')) ",
        basis.commitments, false);
    return basis;
}

std::vector<CommitmentFact> who_committed(
    persistence::SqliteAdapter& adapter,
    std::string_view about,
    std::string_view tenant,
    std::string_view as_of)
{
    auto& conn = adapter.connection();
    sqlite3* db = conn.raw();
    const std::string like = "%" + std::string(about) + "%";
    const std::string sql = std::string("SELECT ") +
        "s.id, s.tenant_id, s.holder_id, s.holder_perspective, s.subject_kind, "
        "s.subject_id, s.predicate, s.object_kind, s.object_value, "
        "s.canonical_object_hash, s.modality, s.polarity, s.confidence, "
        "s.observed_at, s.valid_from, s.valid_to, s.consolidation_state, "
        "s.review_status, s.evidence_json, c.state, COALESCE(c.deadline,'') "
        "FROM commitments c JOIN statements s "
        "  ON s.id = c.stmt_id AND s.tenant_id = c.tenant_id "
        "WHERE c.tenant_id = ?1 AND c.state IN ('ACTIVE','created') "
        "  AND s.object_value LIKE ?2 "
        "  AND (s.valid_from IS NULL OR s.valid_from <= ?3) "
        "  AND (s.valid_to   IS NULL OR s.valid_to   >  ?3) "
        "ORDER BY c.deadline ASC";
    std::vector<CommitmentFact> out;
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "who_committed: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant);
    bind_sv(h.get(), 2, like);
    bind_sv(h.get(), 3, as_of);
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        CommitmentFact f;
        f.stmt = row_from(h.get(), 0);
        const unsigned char* st = sqlite3_column_text(h.get(), 19);
        const unsigned char* dl = sqlite3_column_text(h.get(), 20);
        f.state = st ? reinterpret_cast<const char*>(st) : "";
        f.deadline = dl ? reinterpret_cast<const char*>(dl) : "";
        out.push_back(std::move(f));
    }
    return out;
}

}  // namespace starling::tom::mentalizing
