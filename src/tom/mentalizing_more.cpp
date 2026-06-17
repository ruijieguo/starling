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

// Fetch one statement's full StatementRow columns by id (tenant-scoped). Used to
// populate NestedBelief.inner preserving today's semantics: looked up by id with
// NO consolidation filter (the trusted outer already passed stable-state filters).
// Returns an empty row if the id is absent.
retrieval::StatementRow fetch_row_by_id(sqlite3* db, std::string_view tenant,
                                        const std::string& id) {
    const std::string sql = std::string("SELECT ") + kCols +
        " FROM statements WHERE id = ?1 AND tenant_id = ?2";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "what_does_X_think_Y_believes: prepare inner");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, id);
    bind_sv(h.get(), 2, tenant);
    retrieval::StatementRow r;
    if (sqlite3_step(h.get()) == SQLITE_ROW)
        r = row_from(h.get(), 0);
    return r;
}

}  // namespace

std::vector<NestedBelief> what_does_X_think_Y_believes(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view tenant,
    std::string_view as_of,
    int max_unwrap)
{
    auto& conn = adapter.connection();
    sqlite3* db = conn.raw();

    // ── Pass 1: anchor outer rows ────────────────────────────────────────────
    // holder=X 对 Y 的嵌套信念(stored nesting_depth>=1,object_kind='statement',
    // 过稳定态/时态过滤)。每个 outer 取全列以填 NestedBelief.outer。
    const std::string outer_sql =
        std::string("SELECT ") +
        "o.id, o.tenant_id, o.holder_id, o.holder_perspective, o.subject_kind, "
        "o.subject_id, o.predicate, o.object_kind, o.object_value, "
        "o.canonical_object_hash, o.modality, o.polarity, o.confidence, "
        "o.observed_at, o.valid_from, o.valid_to, o.consolidation_state, "
        "o.review_status, o.evidence_json "
        "FROM statements o "
        "WHERE o.tenant_id = ?1 AND o.holder_id = ?2 AND o.subject_id = ?3 "
        "  AND o.object_kind = 'statement' AND o.nesting_depth >= 1 "
        "  AND (o.valid_from IS NULL OR o.valid_from <= ?4) "
        "  AND (o.valid_to   IS NULL OR o.valid_to   >  ?4) "
        "  AND o.consolidation_state IN ('consolidated','archived') "
        "  AND o.review_status NOT IN ('rejected','pending_review') "
        "ORDER BY o.observed_at DESC";

    std::vector<NestedBelief> out;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, outer_sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "what_does_X_think_Y_believes: prepare outer");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, tenant);
        bind_sv(h.get(), 2, x);
        bind_sv(h.get(), 3, y);
        bind_sv(h.get(), 4, as_of);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            NestedBelief nb;
            nb.outer = row_from(h.get(), 0);
            out.push_back(std::move(nb));
        }
    }

    // ── Pass 2: per-outer recursive unwrap of the nested-belief chain ────────
    // WITH RECURSIVE walks outer.object_value -> next.id, incrementing level,
    // stopping at a non-statement leaf or when level >= max_unwrap. id is the PK
    // so the join is indexed; the level<max bound keeps it cycle-safe.
    // .inner = the level-1 row (immediate inner); inner 不限 consolidation——外层
    // 可信即可展示内层内容(向后兼容今天的 .inner 语义)。
    const int cap = max_unwrap > 0 ? max_unwrap
                                   : nesting_depth_writer::kDefaultMaxNestingDepth;
    const std::string chain_sql =
        "WITH RECURSIVE chain(level, id, holder_id, subject_id, predicate, "
        "                     object_kind, object_value) AS ("
        "  SELECT 1, n.id, n.holder_id, n.subject_id, n.predicate, "
        "         n.object_kind, n.object_value "
        "  FROM statements n "
        "  WHERE n.id = ?1 AND n.tenant_id = ?2 "
        "  UNION ALL "
        "  SELECT c.level + 1, n.id, n.holder_id, n.subject_id, n.predicate, "
        "         n.object_kind, n.object_value "
        "  FROM chain c JOIN statements n "
        "    ON n.id = c.object_value AND n.tenant_id = ?2 "
        "  WHERE c.object_kind = 'statement' AND c.level < ?3 "
        ") SELECT level, id, holder_id, subject_id, predicate, object_kind, "
        "         object_value FROM chain ORDER BY level ASC";

    sqlite3_stmt* craw = nullptr;
    if (sqlite3_prepare_v2(db, chain_sql.c_str(), -1, &craw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "what_does_X_think_Y_believes: prepare chain");
    StmtHandle ch(craw);

    for (auto& nb : out) {
        sqlite3_reset(ch.get());
        sqlite3_clear_bindings(ch.get());
        bind_sv(ch.get(), 1, nb.outer.object_value);  // first inner = outer.object_value
        bind_sv(ch.get(), 2, tenant);
        sqlite3_bind_int(ch.get(), 3, cap);
        bool inner_set = false;
        while (sqlite3_step(ch.get()) == SQLITE_ROW) {
            ChainLevel cl;
            cl.level        = sqlite3_column_int(ch.get(), 0);
            auto col = [&](int i) -> std::string {
                const unsigned char* p = sqlite3_column_text(ch.get(), i);
                return p ? std::string(reinterpret_cast<const char*>(p)) : std::string{};
            };
            cl.id           = col(1);
            cl.holder_id    = col(2);
            cl.subject_id   = col(3);
            cl.predicate    = col(4);
            cl.object_kind  = col(5);
            cl.object_value = col(6);
            if (cl.level == 1 && !inner_set) {
                // Populate .inner from the level-1 row, full columns, preserving
                // today's exact semantics (lookup by id, no consolidation filter).
                nb.inner = fetch_row_by_id(db, tenant, cl.id);
                inner_set = true;
            }
            nb.chain.push_back(std::move(cl));
        }
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
