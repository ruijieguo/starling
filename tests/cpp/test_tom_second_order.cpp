// P3.a2 二阶信念生产端 + 双限流。
//
// 钉住:①自动路径(他者一手语句 → self 的 depth=1 嵌套建模,tom_inferred,
// 置信折减);②永久幂等(同元组二次 → skip);③自我/嵌套源/推断源跳过;
// ④双限流链长半边(derived_depth>=3 拒);⑤显式 depth=2 受
// ToMDepthEstimator order gate(<2 → gated_order;>=2 → depth=2 落库)。
#include "starling/tom/second_order.hpp"
#include "starling/tom/limiting.hpp"

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

TEST(TomSecondOrder, SkipsSelfNestedAndInferredSources) {
    auto a = open_fresh();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    seed_self(db);
    seed_statement(db, "MINE", "cog-self");
    seed_statement(db, "NESTED", "alice", 1);
    seed_statement(db, "DERIVED", "alice", 0, "tom_inferred");

    exec(db, "BEGIN IMMEDIATE");
    EXPECT_EQ(second_order::maybe_persist_second_order(conn, "default", "MINE").reason,
              "skip_self_holder");
    EXPECT_EQ(second_order::maybe_persist_second_order(conn, "default", "NESTED").reason,
              "skip_nested_source");
    EXPECT_EQ(second_order::maybe_persist_second_order(conn, "default", "DERIVED").reason,
              "skip_provenance");
    exec(db, "COMMIT");
    EXPECT_EQ(icol(db, "SELECT COUNT(*) FROM statements WHERE provenance='tom_inferred' "
                       "AND id NOT IN ('DERIVED')"), 0);
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
    seed_statement(db, "B1", "bob", 1, "user_input", "2026-06-12T09:01:00Z");
    seed_statement(db, "B2", "bob", 1, "user_input", "2026-06-12T09:02:00Z");
    seed_statement(db, "B3", "bob", 1, "user_input", "2026-06-12T09:03:00Z");
    exec(db, "BEGIN IMMEDIATE");
    auto ok = second_order::persist_meta_belief(conn, "default", "bob", "B1",
                                                "2026-06-12T10:00:00Z");
    exec(db, "COMMIT");
    ASSERT_TRUE(ok.persisted) << ok.reason;
    EXPECT_EQ(icol(db, "SELECT nesting_depth FROM statements WHERE id='" + ok.stmt_id + "'"), 2);
}
