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

// Gap 1 (headline / decouple proof): a partner's REAL depth-3 chain auto-mirrors
// to a self depth-4 meta-belief. Pre-decouple, write_nested set
// causation_chain_len = src.nesting_depth (=3), tripping the kChainMax=3 causation
// guard and REJECTING the write; now causation_chain_len is hard-pinned to 0
// (depth is structurally guarded by NestingDepthWriter), so a depth-3 source must
// succeed and the StatementWriter ancestor walk over object=G3 yields depth 4.
TEST(TomSecondOrder, AutoMirrorsDepthThreeToDepthFour) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // Structurally-real depth-3 chain held by grace: flat leaf GL0(d0) <- G1(d1)
    // <- G2(d2) <- G3(d3).
    seed_statement(db, "GL0", "grace", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "G1", "grace", "GL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "G2", "grace", "G1", 2, "2026-06-12T09:02:00Z");
    seed_nested_over_statement(db, "G3", "grace", "G2", 3, "2026-06-12T09:03:00Z");
    // Sanity: the source row really is stored at depth 3.
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='G3'"), 3);

    exec(db, "BEGIN IMMEDIATE");
    const auto out = second_order::maybe_persist_second_order(conn, "default", "G3");
    exec(db, "COMMIT");
    ASSERT_TRUE(out.persisted)
        << "depth-3 source must mirror (causation_chain_len decoupled to 0); reason="
        << out.reason;
    EXPECT_NE(out.reason, "gated_limiting");
    EXPECT_EQ(scol(db, "SELECT holder_id FROM statements WHERE id='" + out.stmt_id + "'"),
              "cog-self");
    EXPECT_EQ(scol(db, "SELECT subject_id FROM statements WHERE id='" + out.stmt_id + "'"),
              "grace");
    EXPECT_EQ(scol(db, "SELECT object_value FROM statements WHERE id='" + out.stmt_id + "'"),
              "G3");
    // The headline assertion: depth-3 source -> self depth-4 belief.
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + out.stmt_id + "'"), 4);
    EXPECT_EQ(scol(db, "SELECT provenance FROM statements WHERE id='" + out.stmt_id + "'"),
              "tom_inferred");
}

// Gap 6: idempotency holds at depth >= 2. After an auto depth-2 mirror, re-running
// the auto path on the same source returns skip_already_modeled and leaves exactly
// one nested row for that (holder, subject, object).
TEST(TomSecondOrder, AutoDeepMirrorIsIdempotent) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // Structurally-real depth-2 chain held by ivan: IL0(d0) <- I1(d1) <- I2(d2).
    seed_statement(db, "IL0", "ivan", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "I1", "ivan", "IL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "I2", "ivan", "I1", 2, "2026-06-12T09:02:00Z");

    exec(db, "BEGIN IMMEDIATE");
    const auto first = second_order::maybe_persist_second_order(conn, "default", "I2");
    exec(db, "COMMIT");
    ASSERT_TRUE(first.persisted) << first.reason;
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + first.stmt_id + "'"), 3);

    // Re-run on the same source -> permanent idempotency dedup.
    exec(db, "BEGIN IMMEDIATE");
    const auto again = second_order::maybe_persist_second_order(conn, "default", "I2");
    exec(db, "COMMIT");
    EXPECT_FALSE(again.persisted);
    EXPECT_EQ(again.reason, "skip_already_modeled");
    // Exactly one self-authored nested row about ivan persisted.
    EXPECT_EQ(icol(db, "SELECT COUNT(*) FROM statements WHERE holder_id='cog-self' "
                       "AND subject_id='ivan' AND object_kind='statement' "
                       "AND provenance='tom_inferred'"), 1);
}

// Gap 1 (explicit path): persist_meta_belief generalizes to a depth-3 source.
// target_order = src.nesting_depth + 1 = 4, so an order-4 partner (>= 3 depth-3
// statements) persists self depth-4; an order-3 partner is gated for a depth-3
// source.
TEST(TomSecondOrder, MetaBeliefDepthThreeGate) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);

    // gail: order 3 (>= 3 depth-2 rows) + a structurally-real depth-3 source GG3.
    // target_order for GG3 is 4, estimate=3 < 4 -> gated.
    seed_statement(db, "GGL0", "gail", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "GG1", "gail", "GGL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "GG2", "gail", "GG1", 2, "2026-06-12T09:02:00Z");
    seed_nested_over_statement(db, "GG3", "gail", "GG2", 3, "2026-06-12T09:03:00Z");
    // Two more depth-2 rows so the histogram credits exactly order 3 (counting GG2).
    seed_statement(db, "GGD2a", "gail", 2, "user_input", "2026-06-12T09:04:00Z");
    seed_statement(db, "GGD2b", "gail", 2, "user_input", "2026-06-12T09:05:00Z");
    EXPECT_EQ(depth_estimator::estimate(conn, "gail", "default", "2026-06-12T10:00:00Z"), 3);

    exec(db, "BEGIN IMMEDIATE");
    auto gated = second_order::persist_meta_belief(conn, "default", "gail", "GG3",
                                                   "2026-06-12T10:00:00Z");
    exec(db, "COMMIT");
    EXPECT_FALSE(gated.persisted);
    EXPECT_EQ(gated.reason, "gated_order");

    // hugo: order 4 (>= 3 depth-3 rows) + a structurally-real depth-3 source HH3.
    // target_order = 4, estimate=4 >= 4 -> persists self depth-4.
    seed_statement(db, "HHL0", "hugo", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "HH1", "hugo", "HHL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "HH2", "hugo", "HH1", 2, "2026-06-12T09:02:00Z");
    seed_nested_over_statement(db, "HH3", "hugo", "HH2", 3, "2026-06-12T09:03:00Z");
    // Two more depth-3 rows so the histogram credits order 4 (counting HH3).
    seed_statement(db, "HHD3a", "hugo", 3, "user_input", "2026-06-12T09:04:00Z");
    seed_statement(db, "HHD3b", "hugo", 3, "user_input", "2026-06-12T09:05:00Z");
    EXPECT_GE(depth_estimator::estimate(conn, "hugo", "default", "2026-06-12T10:00:00Z"), 4);

    exec(db, "BEGIN IMMEDIATE");
    auto ok = second_order::persist_meta_belief(conn, "default", "hugo", "HH3",
                                                "2026-06-12T10:00:00Z");
    exec(db, "COMMIT");
    ASSERT_TRUE(ok.persisted) << ok.reason;
    EXPECT_EQ(scol(db, "SELECT subject_id FROM statements WHERE id='" + ok.stmt_id + "'"),
              "hugo");
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + ok.stmt_id + "'"), 4);
}

TEST(TomLimiting, ChainLengthRejects) {
    auto a = open_fresh();
    auto& conn = a->connection();
    limiting::PersistGateInput in;
    in.tenant_id = "default"; in.holder_id = "cog-self";
    in.subject_id = "alice"; in.predicate = "believes";
    in.canonical_object_hash = "h"; in.as_of_iso8601 = "2026-06-12T09:00:00Z";

    // Cascade ceiling raised 3 -> 8 (max_cascade_depth) for arbitrary multi-order
    // ToM: derived_depth=4 is now allowed (was rejected at the old cap of 3).
    in.derived_depth = 4;
    EXPECT_TRUE(limiting::should_persist_tom_statement(conn, in));
    // Gap 5: pin the >=8 cliff from below — derived_depth=7 is the last accepted
    // value just under the kDerivedDepthMax=8 cap.
    in.derived_depth = 7;
    EXPECT_TRUE(limiting::should_persist_tom_statement(conn, in));
    // At/above the new cap (8) the cascade guard still rejects.
    in.derived_depth = 8;
    EXPECT_FALSE(limiting::should_persist_tom_statement(conn, in));
    // causation chain guard (kChainMax) is unchanged at 3.
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

// ── Phase 5: 递归召回任意多阶嵌套链 ─────────────────────────────────────────────
//
// Seed a structurally-real depth-2 outer held by quinn about the partner "peer":
// flat leaf QL0(depth0,object_kind='str') <- Q1(depth1,object_kind='statement')
// <- Q2(depth2,object_kind='statement'). The anchor (holder=quinn, subject=peer,
// nesting_depth>=1) matches BOTH Q2 and Q1 (both are nested rows about peer);
// ordered observed_at DESC, Q2 is first. The recursive CTE must unwrap the depth-2
// outer Q2 -> Q1 -> QL0 (full chain to the depth-0 leaf).
TEST(TomMentalizingMore, RecursiveChainUnwrapsToLeaf) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    seed_statement(db, "QL0", "quinn", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "Q1", "quinn", "QL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "Q2", "quinn", "Q1", 2, "2026-06-12T09:02:00Z");

    const auto nested = mentalizing::what_does_X_think_Y_believes(
        *a, "quinn", "peer", "default", "2026-06-12T12:00:00Z");
    ASSERT_EQ(nested.size(), 2u);   // Q2 (depth-2) and Q1 (depth-1) both anchor.
    EXPECT_EQ(nested[0].outer.id, "Q2");  // most-recent observed_at first
    // .inner = level-1 immediate inner (Q1) — backward-compat semantics preserved.
    EXPECT_EQ(nested[0].inner.id, "Q1");
    EXPECT_EQ(nested[0].inner.object_value, "QL0");  // Q1 -> QL0
    // .chain = full unwrap from the depth-2 outer: level1=Q1, level2=QL0 (leaf).
    ASSERT_EQ(nested[0].chain.size(), 2u);
    EXPECT_EQ(nested[0].chain[0].level, 1);
    EXPECT_EQ(nested[0].chain[0].id, "Q1");
    EXPECT_EQ(nested[0].chain[0].object_kind, "statement");
    EXPECT_EQ(nested[0].chain[0].object_value, "QL0");
    EXPECT_EQ(nested[0].chain[1].level, 2);
    EXPECT_EQ(nested[0].chain[1].id, "QL0");
    EXPECT_EQ(nested[0].chain[1].object_kind, "str");      // leaf reached
    EXPECT_EQ(nested[0].chain[1].object_value, "on track");
    // The depth-1 anchor Q1 unwraps a single level to the leaf.
    EXPECT_EQ(nested[1].outer.id, "Q1");
    ASSERT_EQ(nested[1].chain.size(), 1u);
    EXPECT_EQ(nested[1].chain[0].id, "QL0");

    // max_unwrap=1 truncates the chain to the immediate inner only.
    const auto capped = mentalizing::what_does_X_think_Y_believes(
        *a, "quinn", "peer", "default", "2026-06-12T12:00:00Z", 1);
    ASSERT_EQ(capped.size(), 2u);
    EXPECT_EQ(capped[0].outer.id, "Q2");
    EXPECT_EQ(capped[0].inner.id, "Q1");
    ASSERT_EQ(capped[0].chain.size(), 1u);
    EXPECT_EQ(capped[0].chain[0].id, "Q1");
}

// Gap 2: deeper recall — a structurally-real depth-3 outer unwraps its full chain
// down to the str leaf. The chain starts at outer.object_value (the immediate
// inner) so a depth-3 outer yields 3 levels (R2 -> R1 -> RL0 leaf), matching the
// e2e contract (test_auto_mirror_recall_returns_three_deep_chain). max_unwrap=2
// truncates to 2 levels.
TEST(TomMentalizingMore, RecursiveChainDepthThreeUnwrapsToLeaf) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // ralph's depth-3 outer about "peer": RL0(d0,str) <- R1(d1) <- R2(d2) <- R3(d3).
    seed_statement(db, "RL0", "ralph", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "R1", "ralph", "RL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "R2", "ralph", "R1", 2, "2026-06-12T09:02:00Z");
    seed_nested_over_statement(db, "R3", "ralph", "R2", 3, "2026-06-12T09:03:00Z");

    const auto nested = mentalizing::what_does_X_think_Y_believes(
        *a, "ralph", "peer", "default", "2026-06-12T12:00:00Z");
    // R3 (d3), R2 (d2), R1 (d1) all anchor (holder=ralph, subject=peer, depth>=1);
    // ordered observed_at DESC, R3 first.
    ASSERT_EQ(nested.size(), 3u);
    EXPECT_EQ(nested[0].outer.id, "R3");
    // .inner = immediate inner = the level-1 row (R2).
    EXPECT_EQ(nested[0].inner.id, "R2");
    // .chain = full unwrap from the depth-3 outer: R2(L1) -> R1(L2) -> RL0(L3 leaf).
    ASSERT_EQ(nested[0].chain.size(), 3u);
    EXPECT_EQ(nested[0].chain[0].level, 1);
    EXPECT_EQ(nested[0].chain[0].id, "R2");
    EXPECT_EQ(nested[0].chain[0].object_kind, "statement");
    EXPECT_EQ(nested[0].chain[1].level, 2);
    EXPECT_EQ(nested[0].chain[1].id, "R1");
    EXPECT_EQ(nested[0].chain[1].object_kind, "statement");
    EXPECT_EQ(nested[0].chain[2].level, 3);
    EXPECT_EQ(nested[0].chain[2].id, "RL0");
    EXPECT_EQ(nested[0].chain[2].object_kind, "str");        // leaf reached
    EXPECT_EQ(nested[0].chain[2].object_value, "on track");

    // max_unwrap=2 truncates the depth-3 outer's chain to 2 levels (R2, R1).
    const auto capped = mentalizing::what_does_X_think_Y_believes(
        *a, "ralph", "peer", "default", "2026-06-12T12:00:00Z", 2);
    ASSERT_EQ(capped.size(), 3u);
    EXPECT_EQ(capped[0].outer.id, "R3");
    ASSERT_EQ(capped[0].chain.size(), 2u);
    EXPECT_EQ(capped[0].chain[0].id, "R2");
    EXPECT_EQ(capped[0].chain[1].id, "R1");
}

// Gap 7: max_unwrap=0 falls back to the default ceiling (32), recalling the FULL
// chain — identical to the implicit-default call — not zero levels.
TEST(TomMentalizingMore, RecallMaxUnwrapZeroUsesDefaultCeiling) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // sara's depth-2 outer about "peer": SL0(d0) <- S1(d1) <- S2(d2).
    seed_statement(db, "SL0", "sara", 0, "user_input", "2026-06-12T09:00:30Z");
    seed_nested_statement(db, "S1", "sara", "SL0", "2026-06-12T09:01:00Z");
    seed_nested_over_statement(db, "S2", "sara", "S1", 2, "2026-06-12T09:02:00Z");

    const auto deflt = mentalizing::what_does_X_think_Y_believes(
        *a, "sara", "peer", "default", "2026-06-12T12:00:00Z");
    const auto zero = mentalizing::what_does_X_think_Y_believes(
        *a, "sara", "peer", "default", "2026-06-12T12:00:00Z", 0);
    ASSERT_EQ(zero.size(), deflt.size());
    ASSERT_GE(zero.size(), 1u);
    // The depth-2 outer S2's chain is fully unwrapped (S1 -> SL0), not empty.
    ASSERT_EQ(zero[0].outer.id, "S2");
    ASSERT_EQ(zero[0].chain.size(), 2u);
    EXPECT_EQ(zero[0].chain[0].id, "S1");
    EXPECT_EQ(zero[0].chain[1].id, "SL0");
    EXPECT_EQ(zero[0].chain.size(), deflt[0].chain.size());
}

// Gap 8: recall against a partner with no nested beliefs returns an empty result
// (no anchor rows), without throwing.
TEST(TomMentalizingMore, RecallEmptyForPartnerWithNoBeliefs) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    // tom holds only a flat (non-nested) belief about peer — no object_kind=
    // 'statement' rows to anchor on.
    seed_statement(db, "FLAT", "cog-self", 0, "user_input", "2026-06-12T09:00:00Z");

    std::vector<mentalizing::NestedBelief> nested;
    ASSERT_NO_THROW({
        nested = mentalizing::what_does_X_think_Y_believes(
            *a, "cog-self", "nobody", "default", "2026-06-12T12:00:00Z");
    });
    EXPECT_EQ(nested.size(), 0u);
}

// Seed a cyclic nested pair A<->B (both object_kind='statement', nesting_depth>=1,
// holder=X, subject=peer, consolidated/approved) via direct INSERT — the
// NestingDepthWriter rejects cycles, so the writer can't build this. Used to prove
// the recall CTE's `level < cap` bound terminates on a cycle.
void seed_cyclic_nested(sqlite3* db, const std::string& holder,
                        const std::string& a_id, const std::string& b_id) {
    auto ins = [&](const std::string& id, const std::string& points_at,
                   const std::string& observed) {
        exec(db,
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,evidence_json,consolidation_state,review_status,"
            "nesting_depth,created_at,updated_at) VALUES('" + id +
            "','default','" + holder + "','FIRST_PERSON','cognizer','peer','believes',"
            "'statement','" + points_at + "','h-" + id + "','v1','BELIEVES','POS',0.8,'" +
            observed + "',0.5,'{}',0.0,'" + observed + "','user_input'"
            ",'[{\"engram_id\":\"eng-" + id + "\"}]','consolidated','approved',1,'" +
            observed + "','" + observed + "')");
    };
    ins(a_id, b_id, "2026-06-12T09:01:00Z");
    ins(b_id, a_id, "2026-06-12T09:02:00Z");
}

// Gap 10: a cyclic nested chain (A.object_value=B, B.object_value=A) recalls within
// the `level < cap` bound — it terminates (does not hang/crash) and the unwrapped
// chain length is bounded by the ceiling.
TEST(TomMentalizingMore, RecallTerminatesOnCyclicChain) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    seed_cyclic_nested(db, "cog-self", "CYA", "CYB");

    std::vector<mentalizing::NestedBelief> nested;
    // A small explicit cap keeps the bounded walk obvious and fast.
    ASSERT_NO_THROW({
        nested = mentalizing::what_does_X_think_Y_believes(
            *a, "cog-self", "peer", "default", "2026-06-12T12:00:00Z", /*max_unwrap=*/5);
    });
    // Both CYA and CYB anchor (holder=self, subject=peer, depth>=1).
    ASSERT_EQ(nested.size(), 2u);
    // Each cyclic chain is bounded by the cap (5): it does not run away.
    for (const auto& nb : nested) {
        EXPECT_LE(nb.chain.size(), 5u)
            << "cyclic recall must be bounded by level<cap for outer " << nb.outer.id;
        EXPECT_GE(nb.chain.size(), 1u);
    }
    // Also bounded under the default ceiling (32) — terminates, no hang.
    std::vector<mentalizing::NestedBelief> deflt;
    ASSERT_NO_THROW({
        deflt = mentalizing::what_does_X_think_Y_believes(
            *a, "cog-self", "peer", "default", "2026-06-12T12:00:00Z");
    });
    ASSERT_EQ(deflt.size(), 2u);
    for (const auto& nb : deflt) {
        EXPECT_LE(nb.chain.size(),
                  static_cast<size_t>(nesting_depth_writer::kDefaultMaxNestingDepth));
    }
}
