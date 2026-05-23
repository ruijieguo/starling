#include <gtest/gtest.h>
#include <sqlite3.h>
#include "starling/persistence/migration_runner.hpp"

#include <set>
#include <string>

namespace {

std::set<std::string> column_names(sqlite3* db, const std::string& table) {
    std::set<std::string> out;
    sqlite3_stmt* stmt = nullptr;
    const std::string sql = "PRAGMA table_info(" + table + ");";
    EXPECT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        out.emplace(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1)));
    }
    sqlite3_finalize(stmt);
    return out;
}

bool has_index(sqlite3* db, const std::string& name) {
    sqlite3_stmt* stmt = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(db,
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?;",
        -1, &stmt, nullptr), SQLITE_OK);
    sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT);
    const bool exists = sqlite3_step(stmt) == SQLITE_ROW;
    sqlite3_finalize(stmt);
    return exists;
}

}  // namespace

TEST(Migration0003, AddsM03ColumnsAndUniqueIndex) {
    sqlite3* db = nullptr;
    ASSERT_EQ(sqlite3_open(":memory:", &db), SQLITE_OK);
    starling::persistence::MigrationRunner(db).migrate_to_latest();

    auto cols = column_names(db, "engrams");
    EXPECT_TRUE(cols.count("adapter_name"));
    EXPECT_TRUE(cols.count("adapter_version"));
    EXPECT_TRUE(cols.count("source_item_id"));
    EXPECT_TRUE(cols.count("source_version"));
    EXPECT_TRUE(cols.count("chunk_index"));
    EXPECT_TRUE(cols.count("declared_transformations_json"));
    EXPECT_TRUE(cols.count("byte_preserving"));
    EXPECT_TRUE(cols.count("redacted_content"));
    EXPECT_TRUE(cols.count("key_ref"));
    EXPECT_TRUE(cols.count("audit_trail_json"));

    EXPECT_TRUE(has_index(db, "idx_engrams_source_identity"));
    sqlite3_close(db);
}

TEST(Migration0003, ReRunningMigrationsIsIdempotent) {
    sqlite3* db = nullptr;
    ASSERT_EQ(sqlite3_open(":memory:", &db), SQLITE_OK);
    starling::persistence::MigrationRunner(db).migrate_to_latest();
    starling::persistence::MigrationRunner(db).migrate_to_latest();
    auto cols = column_names(db, "engrams");
    // Spot check: still exactly one of each new column
    EXPECT_EQ(cols.count("adapter_name"), 1u);
    EXPECT_EQ(cols.count("audit_trail_json"), 1u);
    sqlite3_close(db);
}

TEST(Migration0003, UniqueIndexEnforcesSourceIdentityTuple) {
    sqlite3* db = nullptr;
    ASSERT_EQ(sqlite3_open(":memory:", &db), SQLITE_OK);
    starling::persistence::MigrationRunner(db).migrate_to_latest();

    const char* insert_sql =
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, created_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index"
        ") VALUES ("
        "  ?, 't1', 'h', 'user_input', 'store', 'whole_record',"
        "  'internal', 'audit_retain', '2026-05-23T10:00:00Z',"
        "  'a', '1', 'item-1', 'v1', 0"
        ");";

    sqlite3_stmt* s = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, insert_sql, -1, &s, nullptr), SQLITE_OK);
    sqlite3_bind_text(s, 1, "id-1", -1, SQLITE_TRANSIENT);
    EXPECT_EQ(sqlite3_step(s), SQLITE_DONE);
    sqlite3_reset(s);
    sqlite3_bind_text(s, 1, "id-2", -1, SQLITE_TRANSIENT);
    // Same identity tuple, different id — must violate UNIQUE.
    EXPECT_EQ(sqlite3_step(s), SQLITE_CONSTRAINT);
    sqlite3_finalize(s);
    sqlite3_close(db);
}
