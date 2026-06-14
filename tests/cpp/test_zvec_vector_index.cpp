// P3.b1 phase 5 Task 5.2: ZvecVectorIndex parity vs SqliteBlobVectorIndex。
// 仅 STARLING_VECTOR_ZVEC=ON 编译/链接(见 tests/cpp/CMakeLists.txt)。验证 zvec
// 后端的 insert/search_topk/remove 与 SQLite 后端 scope 过滤 + 召回一致。
#include "starling/vector/zvec_vector_index.hpp"
#include "starling/vector/vector_index.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <cstdio>
#include <filesystem>
#include <memory>
#include <set>
#include <string>
#include <unistd.h>

namespace starling::vector {
namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// 种一行 statements(覆盖 scope 关心的 holder/perspective/state/review)。
void seed_stmt(persistence::Connection& conn, const char* id, const char* holder,
               const char* state, const char* review = "approved") {
    char sql[1200];
    std::snprintf(sql, sizeof(sql),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,nesting_depth,"
        "created_at,updated_at) VALUES("
        "'%s','default','%s','FIRST_PERSON','cognizer','subj','knows','str','o-%s',"
        "'h-%s','v1','KNOWS','POS',0.9,'2026-06-10T00:00:00Z',0.5,'{}',0.3,"
        "'2026-06-10T00:00:00Z','user_input','[]','%s','%s',0,"
        "'2026-06-10T00:00:00Z','2026-06-10T00:00:00Z')",
        id, holder, id, id, state, review);
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql, nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

std::string temp_coll(const char* name) {
    return std::string("/tmp/starling_zvec_") + name + "_" +
           std::to_string(::getpid());
}

std::set<std::string> id_set(const std::vector<ScoredId>& rows) {
    std::set<std::string> s;
    for (const auto& r : rows) s.insert(r.stmt_id);
    return s;
}

}  // namespace

// scope 过滤 + 召回 parity:两后端都过滤 volatile,返回相同 consolidated 集合。
TEST(ZvecVectorIndex, ParityScopeVisibilityAndRecall) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_stmt(conn, "s1", "cog-self", "consolidated");
    seed_stmt(conn, "s2", "cog-self", "consolidated");
    seed_stmt(conn, "s3", "cog-self", "volatile");  // visible_only 过滤掉

    SqliteBlobVectorIndex sqlite_idx;
    const std::string coll = temp_coll("parity");
    std::filesystem::remove_all(coll);
    auto zvp = std::make_unique<ZvecVectorIndex>(coll, 4);
    auto& zvec_idx = *zvp;

    const std::vector<float> v1{1.0f, 0.0f, 0.0f, 0.0f};
    const std::vector<float> v2{0.0f, 1.0f, 0.0f, 0.0f};
    const std::vector<float> v3{1.0f, 0.0f, 0.0f, 0.0f};  // 近 query 但 volatile
    for (VectorIndex* idx : {static_cast<VectorIndex*>(&sqlite_idx),
                             static_cast<VectorIndex*>(&zvec_idx)}) {
        idx->insert(conn, "s1", "default", v1);
        idx->insert(conn, "s2", "default", v2);
        idx->insert(conn, "s3", "default", v3);
    }

    SearchScope scope;
    scope.tenant_id = "default";
    scope.visible_only = true;

    const std::vector<float> q{1.0f, 0.0f, 0.0f, 0.0f};
    const auto sq = sqlite_idx.search_topk(conn, q, 10, scope);
    const auto zv = zvec_idx.search_topk(conn, q, 10, scope);

    // parity:都返回 {s1,s2}(s3 volatile 被 scope 精过滤),集合一致。
    EXPECT_EQ(id_set(sq), id_set(zv));
    EXPECT_EQ(id_set(zv), (std::set<std::string>{"s1", "s2"}));
    // s1(=query)最相似,两后端 top1 都是 s1。
    ASSERT_FALSE(sq.empty());
    ASSERT_FALSE(zv.empty());
    EXPECT_EQ(sq.front().stmt_id, "s1");
    EXPECT_EQ(zv.front().stmt_id, "s1");

    zvp.reset();  // 先析构(flush rocksdb)再删目录,避免 flush-after-delete 噪音
    std::filesystem::remove_all(coll);
}

// holder scope parity:别的 holder 的向量被过滤。
TEST(ZvecVectorIndex, ParityScopeHolderFilter) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_stmt(conn, "mine", "cog-self", "consolidated");
    seed_stmt(conn, "other", "cog-bob", "consolidated");

    SqliteBlobVectorIndex sqlite_idx;
    const std::string coll = temp_coll("holder");
    std::filesystem::remove_all(coll);
    auto zvp = std::make_unique<ZvecVectorIndex>(coll, 4);
    auto& zvec_idx = *zvp;

    const std::vector<float> v{1.0f, 0.0f, 0.0f, 0.0f};
    for (VectorIndex* idx : {static_cast<VectorIndex*>(&sqlite_idx),
                             static_cast<VectorIndex*>(&zvec_idx)}) {
        idx->insert(conn, "mine", "default", v);
        idx->insert(conn, "other", "default", v);
    }

    SearchScope scope;
    scope.tenant_id = "default";
    scope.holder_id = "cog-self";
    scope.visible_only = true;

    const auto sq = sqlite_idx.search_topk(conn, v, 10, scope);
    const auto zv = zvec_idx.search_topk(conn, v, 10, scope);
    EXPECT_EQ(id_set(sq), id_set(zv));
    EXPECT_EQ(id_set(zv), (std::set<std::string>{"mine"}));  // 仅自己 holder

    zvp.reset();  // 先析构(flush rocksdb)再删目录,避免 flush-after-delete 噪音
    std::filesystem::remove_all(coll);
}

// remove parity:删除后两后端都查不到。
TEST(ZvecVectorIndex, ParityRemove) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_stmt(conn, "x", "cog-self", "consolidated");

    SqliteBlobVectorIndex sqlite_idx;
    const std::string coll = temp_coll("remove");
    std::filesystem::remove_all(coll);
    auto zvp = std::make_unique<ZvecVectorIndex>(coll, 4);
    auto& zvec_idx = *zvp;

    const std::vector<float> v{1.0f, 0.0f, 0.0f, 0.0f};
    sqlite_idx.insert(conn, "x", "default", v);
    zvec_idx.insert(conn, "x", "default", v);

    SearchScope scope;
    scope.tenant_id = "default";
    scope.visible_only = true;
    EXPECT_EQ(zvec_idx.search_topk(conn, v, 10, scope).size(), 1u);

    sqlite_idx.remove(conn, "x", "default");
    zvec_idx.remove(conn, "x", "default");
    EXPECT_TRUE(sqlite_idx.search_topk(conn, v, 10, scope).empty());
    EXPECT_TRUE(zvec_idx.search_topk(conn, v, 10, scope).empty());

    zvp.reset();  // 先析构(flush rocksdb)再删目录,避免 flush-after-delete 噪音
    std::filesystem::remove_all(coll);
}

}  // namespace starling::vector
