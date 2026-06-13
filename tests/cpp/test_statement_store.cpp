// P3.b1 phase 2:StatementStore —— statements 六态机转换 + 局部修正收编。
// 逐法钉 WHERE 守卫语义(从源写点逐字迁入,行为不变)。fixtures 直接 SQL 种行。
#include "starling/store/sqlite_statement_store.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <cstdio>
#include <memory>
#include <string>

namespace starling::store {
namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void seed(persistence::Connection& conn, const char* id, const char* state,
          int replay_count = 0, double salience = 0.5) {
    char sql[1200];
    std::snprintf(sql, sizeof(sql),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,consolidation_state,review_status,replay_count,access_count,"
        "nesting_depth,created_at,updated_at) VALUES("
        "'%s','default','cog-self','FIRST_PERSON','cognizer','Bob','knows','str',"
        "'x','h-%s','v1','KNOWS','POS',0.9,'2026-06-10T00:00:00Z',%f,'{}',0.0,"
        "'2026-06-10T00:00:00Z','user_input','%s','approved',%d,0,0,"
        "'2026-06-10T00:00:00Z','2026-06-10T00:00:00Z')",
        id, id, salience, state, replay_count);
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql, nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

std::string scol(persistence::Connection& conn, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn.raw(), q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const auto* t = sqlite3_column_text(s, 0);
    std::string v = t ? reinterpret_cast<const char*>(t) : "";
    sqlite3_finalize(s);
    return v;
}

double dcol(persistence::Connection& conn, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn.raw(), q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    double v = sqlite3_column_double(s, 0);
    sqlite3_finalize(s);
    return v;
}

std::string state_of(persistence::Connection& c, const char* id) {
    return scol(c, std::string("SELECT consolidation_state FROM statements WHERE id='") + id + "'");
}

}  // namespace

TEST(StatementStore, MarkConsolidatedOnlyFromVolatile) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "volatile");
    seed(a->connection(), "s2", "consolidated");   // 守卫:非 volatile 不动

    EXPECT_EQ(st.mark_consolidated({"s1", "s2"}, "default", "batch-1"), 1);
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");
    EXPECT_EQ(scol(a->connection(),
        "SELECT last_replay_batch_id FROM statements WHERE id='s1'"), "batch-1");
    EXPECT_EQ(dcol(a->connection(),
        "SELECT replay_count FROM statements WHERE id='s1'"), 1.0);
}

TEST(StatementStore, ReinforceNoStateGuard) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "archived");   // reinforce 无状态守卫
    EXPECT_EQ(st.reinforce({"s1"}, "default", "b1"), 1);
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");
    EXPECT_EQ(dcol(a->connection(),
        "SELECT access_count FROM statements WHERE id='s1'"), 1.0);
}

TEST(StatementStore, BumpReplayCountNoStateChange) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "volatile");
    EXPECT_EQ(st.bump_replay_count({"s1"}, "default", "b1"), 1);
    EXPECT_EQ(state_of(a->connection(), "s1"), "volatile");   // 状态不变
    EXPECT_EQ(dcol(a->connection(),
        "SELECT replay_count FROM statements WHERE id='s1'"), 1.0);
}

TEST(StatementStore, EnterReconsolidatingOnlyFromConsolidated) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "consolidated");
    seed(a->connection(), "s2", "volatile");
    EXPECT_EQ(st.enter_reconsolidating("s1", "default"), 1);
    EXPECT_EQ(st.enter_reconsolidating("s2", "default"), 0);
    EXPECT_EQ(state_of(a->connection(), "s1"), "replaying_reconsolidating");
    EXPECT_EQ(state_of(a->connection(), "s2"), "volatile");
}

TEST(StatementStore, RestoreConsolidatedOnlyFromReconsolidating) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "replaying_reconsolidating");
    seed(a->connection(), "s2", "volatile");
    EXPECT_EQ(st.restore_consolidated("s1", "default"), 1);
    EXPECT_EQ(st.restore_consolidated("s2", "default"), 0);
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");
}

TEST(StatementStore, ForceConsolidateOnHighReplayCount) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "hot", "volatile", /*replay_count=*/5);
    seed(a->connection(), "cold", "volatile", /*replay_count=*/4);
    EXPECT_GE(st.force_consolidate_pending_review(), 1);
    EXPECT_EQ(state_of(a->connection(), "hot"), "consolidated");
    EXPECT_EQ(state_of(a->connection(), "cold"), "volatile");
    EXPECT_EQ(scol(a->connection(),
        "SELECT review_status FROM statements WHERE id='hot'"), "pending_review");
}

TEST(StatementStore, ArchiveHonorsFromStateGuardAndOptionalUpdatedAt) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "c1", "consolidated");
    seed(a->connection(), "v1", "volatile");
    // from_state='consolidated' + updated_at:只动 c1,且 updated_at 刷新。
    EXPECT_EQ(st.archive({"c1", "v1"}, "default", "consolidated",
                         std::string("2026-06-13T00:00:00Z")), 1);
    EXPECT_EQ(state_of(a->connection(), "c1"), "archived");
    EXPECT_EQ(scol(a->connection(),
        "SELECT updated_at FROM statements WHERE id='c1'"), "2026-06-13T00:00:00Z");
    EXPECT_EQ(state_of(a->connection(), "v1"), "volatile");
    // from_state='volatile' + 无 updated_at(TTL 路径):动 v1,updated_at 不变。
    EXPECT_EQ(st.archive({"v1"}, "default", "volatile", std::nullopt), 1);
    EXPECT_EQ(state_of(a->connection(), "v1"), "archived");
    EXPECT_EQ(scol(a->connection(),
        "SELECT updated_at FROM statements WHERE id='v1'"), "2026-06-10T00:00:00Z");
}

TEST(StatementStore, ApplyMildCorrectionSetsConfidenceHistoryNotProvenance) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "consolidated");
    st.apply_mild_correction("s1", "default", 0.77, R"([{"c":0.5}])",
                             "2026-06-13T01:00:00Z");
    EXPECT_NEAR(dcol(a->connection(),
        "SELECT confidence FROM statements WHERE id='s1'"), 0.77, 1e-9);
    EXPECT_EQ(scol(a->connection(),
        "SELECT confidence_history_json FROM statements WHERE id='s1'"),
        R"([{"c":0.5}])");
    EXPECT_EQ(scol(a->connection(),
        "SELECT provenance FROM statements WHERE id='s1'"), "user_input");  // 不动
}

TEST(StatementStore, ApplyMildContradictSetsStateConsolidatedNotUpdatedAt) {
    // arbitration:284 语义:改 confidence+history+state='consolidated',不动
    // updated_at(与 bus mild-correction 相反:那个改 updated_at 不改 state)。
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "replaying_reconsolidating");
    st.apply_mild_contradict("s1", "default", 0.66, R"([{"c":0.4}])");
    EXPECT_NEAR(dcol(a->connection(),
        "SELECT confidence FROM statements WHERE id='s1'"), 0.66, 1e-9);
    EXPECT_EQ(scol(a->connection(),
        "SELECT confidence_history_json FROM statements WHERE id='s1'"),
        R"([{"c":0.4}])");
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");   // state 改
    EXPECT_EQ(scol(a->connection(),
        "SELECT updated_at FROM statements WHERE id='s1'"),
        "2026-06-10T00:00:00Z");   // updated_at 不动
}

TEST(StatementStore, ArchiveNonterminalGuard) {
    // arbitration:452 语义:archived,除非已 archived/forgotten;刷新 updated_at。
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "live", "consolidated");
    seed(a->connection(), "vol", "volatile");        // 非终态:也归档
    seed(a->connection(), "done", "archived");       // 终态:守卫拦住
    EXPECT_EQ(st.archive_nonterminal("live", "default", "2026-06-13T02:00:00Z"), 1);
    EXPECT_EQ(st.archive_nonterminal("vol", "default", "2026-06-13T02:00:00Z"), 1);
    EXPECT_EQ(st.archive_nonterminal("done", "default", "2026-06-13T02:00:00Z"), 0);
    EXPECT_EQ(state_of(a->connection(), "live"), "archived");
    EXPECT_EQ(state_of(a->connection(), "vol"), "archived");
    EXPECT_EQ(scol(a->connection(),
        "SELECT updated_at FROM statements WHERE id='live'"), "2026-06-13T02:00:00Z");
}

TEST(StatementStore, SetConfidenceConsolidated) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "replaying_reconsolidating");
    st.set_confidence_consolidated("s1", "default", 0.88);
    EXPECT_NEAR(dcol(a->connection(),
        "SELECT confidence FROM statements WHERE id='s1'"), 0.88, 1e-9);
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");
}

TEST(StatementStore, InheritSalienceTakesMax) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "volatile", 0, /*salience=*/0.6);
    // 传入更低 → MAX 保留 0.6。
    st.inherit_salience("s1", "default", 0.3, R"({"valence":0.2})");
    EXPECT_NEAR(dcol(a->connection(),
        "SELECT salience FROM statements WHERE id='s1'"), 0.6, 1e-9);
    // 传入更高 → 抬到 0.9。
    st.inherit_salience("s1", "default", 0.9, R"({"valence":0.2})");
    EXPECT_NEAR(dcol(a->connection(),
        "SELECT salience FROM statements WHERE id='s1'"), 0.9, 1e-9);
    EXPECT_EQ(scol(a->connection(),
        "SELECT affect_json FROM statements WHERE id='s1'"), R"({"valence":0.2})");
}

}  // namespace starling::store
