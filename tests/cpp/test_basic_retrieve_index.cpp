#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>
#include <unordered_set>

namespace starling::persistence {
namespace {

// Returns the comma-joined column list (no spaces) of an index in declaration
// order using PRAGMA index_info(<index>). Inlined here per M0.6 plan: do NOT
// promote this to a public starling_core helper.
std::string index_columns(sqlite3* db, const std::string& index_name) {
    sqlite3_stmt* stmt = nullptr;
    const std::string sql = "PRAGMA index_info(" + index_name + ");";
    EXPECT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    std::string joined;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        // PRAGMA index_info columns: seqno (0), cid (1), name (2). Rows are
        // already returned in seqno order.
        const auto* name = reinterpret_cast<const char*>(
            sqlite3_column_text(stmt, 2));
        if (!joined.empty()) joined.push_back(',');
        joined.append(name ? name : "");
    }
    sqlite3_finalize(stmt);
    return joined;
}

std::unordered_set<std::string> indices_on_table(
    sqlite3* db, const std::string& table) {
    std::unordered_set<std::string> names;
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?";
    EXPECT_EQ(sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr), SQLITE_OK);
    sqlite3_bind_text(stmt, 1, table.c_str(), -1, SQLITE_STATIC);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        names.insert(reinterpret_cast<const char*>(
            sqlite3_column_text(stmt, 0)));
    }
    sqlite3_finalize(stmt);
    return names;
}

TEST(MigrationBasicRetrieveIndex, ComposesExpectedColumnOrder) {
    auto adapter = SqliteAdapter::open(":memory:");
    MigrationRunner(adapter->connection().raw()).migrate_to_latest();

    EXPECT_EQ(
        index_columns(adapter->connection().raw(),
                      "idx_statements_basic_retrieve"),
        "tenant_id,holder_id,consolidation_state,predicate,valid_from,valid_to");
}

TEST(MigrationBasicRetrieveIndex, PriorIndicesNotRegressed) {
    auto adapter = SqliteAdapter::open(":memory:");
    MigrationRunner(adapter->connection().raw()).migrate_to_latest();
    auto idx = indices_on_table(adapter->connection().raw(), "statements");

    // 0001
    EXPECT_TRUE(idx.count("idx_statement_id_tenant") > 0)
        << "missing idx_statement_id_tenant from 0001";
    EXPECT_TRUE(idx.count("idx_statements_holder_predicate") > 0)
        << "missing idx_statements_holder_predicate from 0001";
    EXPECT_TRUE(idx.count("idx_statements_subject") > 0)
        << "missing idx_statements_subject from 0001";
    // 0004
    EXPECT_TRUE(idx.count("idx_conflict_lookup") > 0)
        << "missing idx_conflict_lookup from 0004";
    EXPECT_TRUE(idx.count("idx_temporal_overlap") > 0)
        << "missing idx_temporal_overlap from 0004";
}

}  // namespace
}  // namespace starling::persistence
