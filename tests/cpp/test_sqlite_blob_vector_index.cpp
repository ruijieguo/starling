// tests/cpp/test_sqlite_blob_vector_index.cpp
#include "starling/vector/vector_index.hpp"
#include "starling/vector/vector_math.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <set>
#include <string>
#include <vector>
using namespace starling::vector;
using starling::persistence::SqliteAdapter;

namespace {
void seed_stmt(sqlite3* db, const std::string& id,
               const std::string& state="consolidated",
               const std::string& tenant="default",
               const std::string& holder="alice") {
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','"+tenant+"','"+holder+"','first_person','cognizer',"
      "'bob','knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','"+state+
      "','approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
}

TEST(SqliteBlobVectorIndex, InsertSearchRanking) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "a"); seed_stmt(conn.raw(), "b"); seed_stmt(conn.raw(), "c");
    SqliteBlobVectorIndex idx;
    idx.insert(conn, "a", "default", {1,0,0});
    idx.insert(conn, "b", "default", {0,1,0});
    idx.insert(conn, "c", "default", {0.9f,0.1f,0});
    SearchScope scope{"default", std::nullopt, std::nullopt, true};
    auto top = idx.search_topk(conn, {1,0,0}, 2, scope);
    ASSERT_EQ(top.size(), 2u);
    EXPECT_EQ(top[0].stmt_id, "a");   // 最相似
    EXPECT_EQ(top[1].stmt_id, "c");   // 次相似
}

TEST(SqliteBlobVectorIndex, VisibleOnlyExcludesPendingReview) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "vis", "consolidated");
    seed_stmt(conn.raw(), "hidden", "consolidated");
    sqlite3_exec(conn.raw(), "UPDATE statements SET review_status='pending_review' WHERE id='hidden'", nullptr,nullptr,nullptr);
    SqliteBlobVectorIndex idx;
    idx.insert(conn, "vis", "default", {1,0,0});
    idx.insert(conn, "hidden", "default", {1,0,0});
    auto top = idx.search_topk(conn, {1,0,0}, 10, {"default", std::nullopt, std::nullopt, true});
    ASSERT_EQ(top.size(), 1u);
    EXPECT_EQ(top[0].stmt_id, "vis");
}

TEST(SqliteBlobVectorIndex, RemoveDeletesRow) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "a");
    SqliteBlobVectorIndex idx;
    idx.insert(conn, "a", "default", {1,0,0});
    idx.remove(conn, "a", "default");
    auto top = idx.search_topk(conn, {1,0,0}, 10, {"default", std::nullopt, std::nullopt, true});
    EXPECT_TRUE(top.empty());
}

TEST(SqliteBlobVectorIndex, RemoveIsTenantScoped) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "shared", "consolidated", "tenant-a");
    seed_stmt(conn.raw(), "shared", "consolidated", "tenant-b");
    SqliteBlobVectorIndex idx;
    idx.insert(conn, "shared", "tenant-a", {1,0,0});
    idx.insert(conn, "shared", "tenant-b", {0,1,0});

    idx.remove(conn, "shared", "tenant-a");

    auto a_top = idx.search_topk(conn, {1,0,0}, 10,
                                 {"tenant-a", std::nullopt, std::nullopt, true});
    auto b_top = idx.search_topk(conn, {0,1,0}, 10,
                                 {"tenant-b", std::nullopt, std::nullopt, true});
    EXPECT_TRUE(a_top.empty());
    ASSERT_EQ(b_top.size(), 1u);
    EXPECT_EQ(b_top[0].stmt_id, "shared");
}

// include_volatile 只放宽巩固状态这一段:默认不见 volatile,放宽后见;
// review 守卫(pending_review)与 holder 谓词两种都照旧;其他状态(forgotten)不放宽。
TEST(SqliteBlobVectorIndex, IncludeVolatileWidensOnlyConsolidationState) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "con", "consolidated");
    seed_stmt(conn.raw(), "vol", "volatile");
    seed_stmt(conn.raw(), "vol_pending", "volatile");
    // holder_id 有不可变触发器(0007),只能在插入时给。
    seed_stmt(conn.raw(), "vol_other_holder", "volatile", "default", "carol");
    seed_stmt(conn.raw(), "forgot", "forgotten");
    ASSERT_EQ(sqlite3_exec(conn.raw(),
                           "UPDATE statements SET review_status='pending_review' WHERE id='vol_pending'",
                           nullptr, nullptr, nullptr), SQLITE_OK);
    SqliteBlobVectorIndex idx;
    for (const char* id : {"con", "vol", "vol_pending", "vol_other_holder", "forgot"})
        idx.insert(conn, id, "default", {1,0,0});

    auto ids = [](const std::vector<ScoredId>& rows) {
        std::set<std::string> s;
        for (const auto& r : rows) s.insert(r.stmt_id);
        return s;
    };

    SearchScope scope;
    scope.tenant_id = "default";
    scope.holder_id = "alice";
    scope.visible_only = true;
    EXPECT_FALSE(scope.include_volatile);   // 默认关
    EXPECT_EQ(ids(idx.search_topk(conn, {1,0,0}, 10, scope)),
              (std::set<std::string>{"con"}));

    scope.include_volatile = true;
    EXPECT_EQ(ids(idx.search_topk(conn, {1,0,0}, 10, scope)),
              (std::set<std::string>{"con", "vol"}));
}
