#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>
#include <unordered_set>

namespace starling::persistence {
namespace {

std::unordered_set<std::string> get_indices(sqlite3* db, const std::string& table) {
    std::unordered_set<std::string> names;
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?";
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);
    EXPECT_EQ(rc, SQLITE_OK);
    sqlite3_bind_text(stmt, 1, table.c_str(), -1, SQLITE_STATIC);
    while (sqlite3_step(stmt) == SQLITE_ROW)
        names.insert(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    sqlite3_finalize(stmt);
    return names;
}

TEST(ConflictProbeIndices, BothNewIndicesPresent) {
    auto adapter = SqliteAdapter::open(":memory:");
    MigrationRunner(adapter->connection().raw()).migrate_to_latest();
    auto idx = get_indices(adapter->connection().raw(), "statements");
    EXPECT_TRUE(idx.count("idx_conflict_lookup") > 0);
    EXPECT_TRUE(idx.count("idx_temporal_overlap") > 0);
}

TEST(ConflictProbeIndices, M0001IndicesNotRegressed) {
    auto adapter = SqliteAdapter::open(":memory:");
    MigrationRunner(adapter->connection().raw()).migrate_to_latest();
    auto idx = get_indices(adapter->connection().raw(), "statements");
    EXPECT_TRUE(idx.count("idx_statement_id_tenant") > 0);
    EXPECT_TRUE(idx.count("idx_statements_holder_predicate") > 0);
    EXPECT_TRUE(idx.count("idx_statements_subject") > 0);
}

TEST(ConflictProbeIndices, MigrationVersion4Recorded) {
    auto adapter = SqliteAdapter::open(":memory:");
    MigrationRunner(adapter->connection().raw()).migrate_to_latest();
    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(adapter->connection().raw(),
        "SELECT version FROM schema_migrations WHERE version=4",
        -1, &stmt, nullptr);
    EXPECT_EQ(rc, SQLITE_OK);
    EXPECT_EQ(sqlite3_step(stmt), SQLITE_ROW);
    sqlite3_finalize(stmt);
}

}  // namespace
}  // namespace starling::persistence
