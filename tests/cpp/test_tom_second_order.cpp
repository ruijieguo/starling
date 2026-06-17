// P3.a2 二阶信念生产端 + 双限流(Phase 4:任意多阶嵌套生产)。
//
// 钉住:①自动路径 = grounded mirroring(他者 depth-k 信念 → self 的
// depth-(k+1) 嵌套建模,tom_inferred,置信折减;k 任意,不受估计器拦)
// ;②永久幂等(同元组二次 → skip);③自我/推断源跳过(self-holder skip
// 防自级联,user_input provenance 要求);④双限流:derived_depth>=3 拒,
// causation_chain_len 已与 nesting_depth 解耦(恒 0,深度由 NestingDepthWriter
// 结构守);⑤显式 persist_meta_belief = depth-N,受 ToMDepthEstimator order
// gate(estimate(partner) < src.nesting_depth+1 → gated_order;否则把
// depth-k 源包成 depth-(k+1) 落库)。
#include "starling/tom/second_order.hpp"
#include "starling/tom/limiting.hpp"
#include "starling/tom/depth_estimator.hpp"

#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling::tom;
using starling::persistence::SqliteAdapter;

namespace {

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

void exec(sqlite3* db, const std::string& s) {
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(db, s.c_str(), nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const auto* txt = sqlite3_column_text(s, 0);
    std::string v = txt ? reinterpret_cast<const char*>(txt) : "";
    sqlite3_finalize(s);
    return v;
}

int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

void seed_self(sqlite3* db) {
    exec(db,
        "INSERT INTO cognizers(id,tenant_id,kind,canonical_name,"
        "canonical_name_normalized,external_id,created_at,last_seen_at) VALUES"
        "('cog-self','default','self','Sam','sam','','2026-06-01T00:00:00Z',"
        "'2026-06-01T00:00:00Z')");
}

void seed_statement(sqlite3* db, const std::string& id, const std::string& holder,
                    int nesting_depth = 0, const std::string& provenance = "user_input",
                    const std::string& observed = "2026-06-12T09:00:00Z") {
    exec(db,
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES('" + id +
        "','default','" + holder + "','FIRST_PERSON','entity','proj','status',"
        "'str','on track','h-" + id + "','v1','BELIEVES','POS',0.8,'" + observed +
        "',0.5,'{}',0.0,'" + observed + "','" + provenance +
        "','[{\"engram_id\":\"eng-" + id + "\"}]','consolidated','approved'," +
        std::to_string(nesting_depth) + ",'" + observed + "','" + observed + "')");
}

// Seed a structurally-real nested statement: object_kind='statement' pointing at
// a child statement `child_id`, with stored nesting_depth=1. Used where the
// NestingDepthWriter's ancestor walk must see a genuine chain (not a flat row
// carrying a manually-set depth).
void seed_nested_statement(sqlite3* db, const std::string& id,
                           const std::string& holder, const std::string& child_id,
                           const std::string& observed = "2026-06-12T09:00:00Z") {
    exec(db,
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES('" + id +
        "','default','" + holder + "','FIRST_PERSON','cognizer','peer','believes',"
        "'statement','" + child_id + "','h-" + id + "','v1','BELIEVES','POS',0.8,'" +
        observed + "',0.5,'{}',0.0,'" + observed + "','user_input'"
        ",'[{\"engram_id\":\"eng-" + id + "\"}]','consolidated','approved',1,'" +
        observed + "','" + observed + "')");
}

// Seed a statement that wraps another `object_kind='statement'` row (`child_id`)
// one level deeper, with an explicit stored `nesting_depth`. Stacking
// seed_statement(flat) <- seed_nested_statement(depth1) <- this(depth2) builds a
// structurally-real depth-2 chain whose StatementWriter walk yields the right
// depth for an auto deep-mirror over it.
void seed_nested_over_statement(sqlite3* db, const std::string& id,
                                const std::string& holder,
                                const std::string& child_id, int nesting_depth,
                                const std::string& observed = "2026-06-12T09:00:00Z") {
    exec(db,
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES('" + id +
        "','default','" + holder + "','FIRST_PERSON','cognizer','peer','believes',"
        "'statement','" + child_id + "','h-" + id + "','v1','BELIEVES','POS',0.8,'" +
        observed + "',0.5,'{}',0.0,'" + observed + "','user_input'"
        ",'[{\"engram_id\":\"eng-" + id + "\"}]','consolidated','approved'," +
        std::to_string(nesting_depth) + ",'" + observed + "','" + observed + "')");
}

}  // namespace

TEST(TomSecondOrder, AutoPersistsDepthOneForOtherHolder) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    seed_statement(db, "P1", "alice");

    exec(db, "BEGIN IMMEDIATE");
    const auto out = second_order::maybe_persist_second_order(conn, "default", "P1");
    exec(db, "COMMIT");

    ASSERT_TRUE(out.persisted) << out.reason;
    EXPECT_EQ(scol(db, "SELECT holder_id FROM statements WHERE id='" + out.stmt_id + "'"),
              "cog-self");
    EXPECT_EQ(scol(db, "SELECT subject_id FROM statements WHERE id='" + out.stmt_id + "'"),
              "alice");
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + out.stmt_id + "'"), 1);
    EXPECT_EQ(scol(db, "SELECT provenance FROM statements WHERE id='" + out.stmt_id + "'"),
              "tom_inferred");
    EXPECT_EQ(scol(db, "SELECT object_value FROM statements WHERE id='" + out.stmt_id + "'"),
              "P1");

    // 永久幂等:再来一次 → skip。
    exec(db, "BEGIN IMMEDIATE");
    const auto again = second_order::maybe_persist_second_order(conn, "default", "P1");
    exec(db, "COMMIT");
    EXPECT_FALSE(again.persisted);
    EXPECT_EQ(again.reason, "skip_already_modeled");
}

TEST(TomSecondOrder, SkipsSelfAndInferredButMirrorsNested) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    seed_statement(db, "MINE", "cog-self");
    seed_statement(db, "DERIVED", "alice", 0, "tom_inferred");
    // A structurally-real depth-1 nested source held by a partner: flat leaf NL0
    // + NESTED(object_kind='statement' -> NL0). Phase 4 drops skip_nested_source,
    // so this now MIRRORS to a self depth-2 meta-belief rather than skipping.
    seed_statement(db, "NL0", "alice", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "NESTED", "alice", "NL0", "2026-06-12T09:01:00Z");

    exec(db, "BEGIN IMMEDIATE");
    // self-holder skip stays (stops auto-production cascading on self output).
    EXPECT_EQ(second_order::maybe_persist_second_order(conn, "default", "MINE").reason,
              "skip_self_holder");
    // tom_inferred provenance still skipped.
    EXPECT_EQ(second_order::maybe_persist_second_order(conn, "default", "DERIVED").reason,
              "skip_provenance");
    // Formerly skip_nested_source — now grounded-mirrored to self depth-2.
    const auto mirror = second_order::maybe_persist_second_order(conn, "default", "NESTED");
    exec(db, "COMMIT");
    ASSERT_TRUE(mirror.persisted) << mirror.reason;
    EXPECT_NE(mirror.reason, "skip_nested_source");
    EXPECT_EQ(scol(db, "SELECT holder_id FROM statements WHERE id='" + mirror.stmt_id + "'"),
              "cog-self");
    EXPECT_EQ(scol(db, "SELECT subject_id FROM statements WHERE id='" + mirror.stmt_id + "'"),
              "alice");
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + mirror.stmt_id + "'"), 2);
    // Exactly one self-authored tom_inferred row produced (the mirror), nothing
    // else cascaded.
    EXPECT_EQ(icol(db, "SELECT COUNT(*) FROM statements WHERE provenance='tom_inferred' "
                       "AND holder_id='cog-self'"), 1);
}

// Auto path = grounded mirroring, UNGATED by the estimator: a partner's real
// depth-k belief produces self depth-(k+1), even when estimate(partner) is low.
TEST(TomSecondOrder, AutoDeepMirrorIsUngated) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // carol authors ONE structurally-real depth-1 nested belief (flat leaf CL0 +
    // AN1 over it) and nothing else — so estimate(carol) is low (count_to_depth(1)
    // = 1 < 2). The auto path must still mirror it.
    seed_statement(db, "CL0", "carol", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "AN1", "carol", "CL0", "2026-06-12T09:01:00Z");

    // Sanity: the estimator would gate a depth-2 fabrication here.
    EXPECT_LT(depth_estimator::estimate(conn, "carol", "default", "2026-06-12T10:00:00Z"), 2);

    exec(db, "BEGIN IMMEDIATE");
    const auto out = second_order::maybe_persist_second_order(conn, "default", "AN1");
    exec(db, "COMMIT");
    ASSERT_TRUE(out.persisted) << out.reason;
    EXPECT_NE(out.reason, "skip_nested_source");
    EXPECT_EQ(scol(db, "SELECT holder_id FROM statements WHERE id='" + out.stmt_id + "'"),
              "cog-self");
    EXPECT_EQ(scol(db, "SELECT subject_id FROM statements WHERE id='" + out.stmt_id + "'"),
              "carol");
    EXPECT_EQ(scol(db, "SELECT object_value FROM statements WHERE id='" + out.stmt_id + "'"),
              "AN1");
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + out.stmt_id + "'"), 2);
    EXPECT_EQ(scol(db, "SELECT provenance FROM statements WHERE id='" + out.stmt_id + "'"),
              "tom_inferred");
}

// Auto path mirrors arbitrary depth: a partner depth-2 source -> self depth-3.
TEST(TomSecondOrder, AutoMirrorsDepthTwoToDepthThree) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // Structurally-real depth-2 chain held by dave: flat leaf DL0 <- D1(depth1)
    // <- D2(depth2). StatementWriter's ancestor walk over a meta-belief whose
    // object is D2 yields depth 3.
    seed_statement(db, "DL0", "dave", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "D1", "dave", "DL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "D2", "dave", "D1", 2, "2026-06-12T09:02:00Z");

    exec(db, "BEGIN IMMEDIATE");
    const auto out = second_order::maybe_persist_second_order(conn, "default", "D2");
    exec(db, "COMMIT");
    ASSERT_TRUE(out.persisted) << out.reason;
    EXPECT_EQ(scol(db, "SELECT subject_id FROM statements WHERE id='" + out.stmt_id + "'"),
              "dave");
    EXPECT_EQ(scol(db, "SELECT object_value FROM statements WHERE id='" + out.stmt_id + "'"),
              "D2");
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + out.stmt_id + "'"), 3);
    EXPECT_EQ(scol(db, "SELECT provenance FROM statements WHERE id='" + out.stmt_id + "'"),
              "tom_inferred");
}

TEST(TomLimiting, ChainLengthRejects) {
    auto a = open_fresh();
    auto& conn = a->connection();
    limiting::PersistGateInput in;
    in.tenant_id = "default"; in.holder_id = "cog-self";
    in.subject_id = "alice"; in.predicate = "believes";
    in.canonical_object_hash = "h"; in.as_of_iso8601 = "2026-06-12T09:00:00Z";

    in.derived_depth = 3;
    EXPECT_FALSE(limiting::should_persist_tom_statement(conn, in));
    in.derived_depth = 0; in.causation_chain_len = 3;
    EXPECT_FALSE(limiting::should_persist_tom_statement(conn, in));
    in.causation_chain_len = 0;
    EXPECT_TRUE(limiting::should_persist_tom_statement(conn, in));
}

TEST(TomSecondOrder, MetaBeliefGatedByEstimatorOrder) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // partner alice 持有一条 depth=1 行(estimate=1,不足 2)。
    seed_statement(db, "N1", "alice", 1);

    exec(db, "BEGIN IMMEDIATE");
    auto gated = second_order::persist_meta_belief(conn, "default", "alice", "N1",
                                                   "2026-06-12T10:00:00Z");
    exec(db, "COMMIT");
    EXPECT_FALSE(gated.persisted);
    EXPECT_EQ(gated.reason, "gated_order");

    // 估计器缓存 TTL 1h:换个 partner(bob)避免缓存,3 条 depth=1 → order=2。
    // B1 是 persist_meta_belief 要包裹的源——做成结构真实的 depth=1 嵌套:
    // 一条 flat 叶子 L0(object_kind='str',depth=0)+ B1(object_kind='statement',
    // object_value='L0',stored depth=1)。NestingDepthWriter 对新 meta-belief
    // (object_value=B1)走链 B1→L0 得 depth=2。B2/B3 只供估计器计数(读 stored
    // nesting_depth 列,不触发结构走链),保留 helper 默认的 flat 形态即可。
    seed_statement(db, "L0", "bob", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "B1", "bob", "L0", "2026-06-12T09:01:00Z");
    seed_statement(db, "B2", "bob", 1, "user_input", "2026-06-12T09:02:00Z");
    seed_statement(db, "B3", "bob", 1, "user_input", "2026-06-12T09:03:00Z");
    exec(db, "BEGIN IMMEDIATE");
    auto ok = second_order::persist_meta_belief(conn, "default", "bob", "B1",
                                                "2026-06-12T10:00:00Z");
    exec(db, "COMMIT");
    ASSERT_TRUE(ok.persisted) << ok.reason;
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + ok.stmt_id + "'"), 2);
}

// Explicit path generalizes to depth-N: wrapping a depth-2 source needs
// estimate(partner) >= 3 (target_order = src.nesting_depth + 1 = 3). An order-2
// partner that would clear the old `< 2` gate is now gated for a depth-2 source.
TEST(TomSecondOrder, MetaBeliefDepthNGate) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);

    // frank: order 2 (3 flat depth-1 rows) + a structurally-real depth-2 source
    // F2 (FL0 <- F1 <- F2). target_order for F2 is 3, estimate=2 < 3 → gated.
    seed_statement(db, "FL0", "frank", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "F1", "frank", "FL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "F2", "frank", "F1", 2, "2026-06-12T09:02:00Z");
    seed_statement(db, "FD1a", "frank", 1, "user_input", "2026-06-12T09:03:00Z");
    seed_statement(db, "FD1b", "frank", 1, "user_input", "2026-06-12T09:04:00Z");
    seed_statement(db, "FD1c", "frank", 1, "user_input", "2026-06-12T09:05:00Z");
    EXPECT_EQ(depth_estimator::estimate(conn, "frank", "default", "2026-06-12T10:00:00Z"), 2);

    exec(db, "BEGIN IMMEDIATE");
    auto gated = second_order::persist_meta_belief(conn, "default", "frank", "F2",
                                                   "2026-06-12T10:00:00Z");
    exec(db, "COMMIT");
    EXPECT_FALSE(gated.persisted);
    EXPECT_EQ(gated.reason, "gated_order");

    // erin: order 3 (>= 3 statements at depth-2) + a structurally-real depth-2
    // source E2. target_order = 3, estimate=3 >= 3 → persists self depth-3.
    seed_statement(db, "EL0", "erin", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "E1", "erin", "EL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "E2", "erin", "E1", 2, "2026-06-12T09:02:00Z");
    // Two more depth-2 rows so the histogram credits order 3 (kMinCountForDepth=3
    // at depth-2, counting E2). These only feed the estimator's stored-depth count.
    seed_statement(db, "ED2a", "erin", 2, "user_input", "2026-06-12T09:03:00Z");
    seed_statement(db, "ED2b", "erin", 2, "user_input", "2026-06-12T09:04:00Z");
    EXPECT_GE(depth_estimator::estimate(conn, "erin", "default", "2026-06-12T10:00:00Z"), 3);

    exec(db, "BEGIN IMMEDIATE");
    auto ok = second_order::persist_meta_belief(conn, "default", "erin", "E2",
                                                "2026-06-12T10:00:00Z");
    exec(db, "COMMIT");
    ASSERT_TRUE(ok.persisted) << ok.reason;
    EXPECT_EQ(scol(db, "SELECT subject_id FROM statements WHERE id='" + ok.stmt_id + "'"),
              "erin");
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + ok.stmt_id + "'"), 3);
}

// ── P3.a2: mentalizing 后三 API ──────────────────────────────────────────────

#include "starling/tom/mentalizing.hpp"

TEST(TomMentalizingMore, NestedQueryPredictionBasisAndWhoCommitted) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // alice 的一手语句 P1 → 自动二阶建模(self believes alice believes P1)。
    seed_statement(db, "P1", "alice");
    exec(db, "BEGIN IMMEDIATE");
    const auto so = second_order::maybe_persist_second_order(conn, "default", "P1");
    exec(db, "COMMIT");
    ASSERT_TRUE(so.persisted) << so.reason;
    // 嵌套行是 volatile 出生;查询要求稳定态 → 手动晋升(回放等价)。
    exec(db, "UPDATE statements SET consolidation_state='consolidated' "
             "WHERE id='" + so.stmt_id + "'");

    // 5. what_does_X_think_Y_believes(self, alice)→ 外层+内层成对。
    const auto nested = mentalizing::what_does_X_think_Y_believes(
        *a, "cog-self", "alice", "default", "2026-06-12T12:00:00Z");
    ASSERT_EQ(nested.size(), 1u);
    EXPECT_EQ(nested[0].outer.id, so.stmt_id);
    EXPECT_EQ(nested[0].inner.id, "P1");
    EXPECT_EQ(nested[0].inner.object_value, "on track");

    // 6. predict_X_would:alice 的 situation 相关信念 + 偏好 + 承诺。
    seed_statement(db, "PREF", "alice");
    exec(db, "UPDATE statements SET predicate='prefers', object_value='short standups' "
             "WHERE id='PREF'");
    const auto basis = mentalizing::predict_X_would(
        *a, "alice", "proj", "default", "2026-06-12T12:00:00Z");
    ASSERT_EQ(basis.beliefs.size(), 1u);     // P1(subject_id='proj' LIKE 命中)
    EXPECT_EQ(basis.beliefs[0].id, "P1");
    ASSERT_EQ(basis.preferences.size(), 1u);
    EXPECT_EQ(basis.preferences[0].id, "PREF");

    // 7. who_committed:挂一条活跃承诺。
    seed_statement(db, "CMT", "alice");
    exec(db, "UPDATE statements SET predicate='promises', "
             "object_value='ship the proj runbook' WHERE id='CMT'");
    exec(db, "INSERT INTO commitments(tenant_id,stmt_id,state,broken_count,"
             "deadline,created_at,updated_at) VALUES('default','CMT','ACTIVE',0,"
             "'2026-06-15T00:00:00Z','2026-06-12T00:00:00Z','2026-06-12T00:00:00Z')");
    const auto facts = mentalizing::who_committed(
        *a, "proj", "default", "2026-06-12T12:00:00Z");
    ASSERT_EQ(facts.size(), 1u);
    EXPECT_EQ(facts[0].stmt.holder_id, "alice");
    EXPECT_EQ(facts[0].state, "ACTIVE");
    EXPECT_EQ(facts[0].deadline, "2026-06-15T00:00:00Z");
}
