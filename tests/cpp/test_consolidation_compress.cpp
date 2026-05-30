#include "starling/replay/consolidation_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::replay;
using starling::persistence::SqliteAdapter;

namespace {
void seed_volatile(sqlite3* db, const std::string& id) {
    std::string sql =
      "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,"
      "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
      "confidence,observed_at,salience,affect_json,activation,last_accessed,"
      "provenance,consolidation_state,review_status,created_at,updated_at) "
      "VALUES('"+id+"','default','alice','first_person','cognizer','bob',"
      "'knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',"
      "0.9,'2026-05-27T09:00:00Z',0.5,'{}',0.0,'2026-05-27T09:00:00Z',"
      "'user_input','volatile','approved','2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr);
}
}  // namespace

TEST(ConsolidationCompress, VolatileToConsolidated) {
    auto a = SqliteAdapter::open(":memory:");
    auto& conn = a->connection();
    seed_volatile(conn.raw(), "s1");
    seed_volatile(conn.raw(), "s2");
    auto r = op_compress(conn, {"s1","s2"}, "default", "batch-1");
    EXPECT_EQ(r.affected, 2);
    sqlite3_stmt* st=nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='consolidated'",
        -1,&st,nullptr);
    sqlite3_step(st);
    EXPECT_EQ(sqlite3_column_int(st,0), 2);
    sqlite3_finalize(st);
}
TEST(ConsolidationCompress, OnlyTouchesVolatile) {
    auto a = SqliteAdapter::open(":memory:");
    auto& conn = a->connection();
    seed_volatile(conn.raw(), "s1");
    op_compress(conn, {"s1"}, "default", "b1");
    auto r2 = op_compress(conn, {"s1"}, "default", "b2");
    EXPECT_EQ(r2.affected, 0);
}
