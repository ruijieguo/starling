#include <gtest/gtest.h>
#include <sqlite3.h>
#include "starling/persistence/migration_runner.hpp"

namespace {

void open_memory(sqlite3*& db) {
    db = nullptr;
    ASSERT_EQ(sqlite3_open(":memory:", &db), SQLITE_OK);
}

int count_rows(sqlite3* db, const char* sql) {
    sqlite3_stmt* stmt = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr), SQLITE_OK);
    EXPECT_EQ(sqlite3_step(stmt), SQLITE_ROW);
    const int n = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return n;
}

}  // namespace

TEST(MigrationRunner, AppliesEveryMigrationOnce) {
    sqlite3* db;
    ASSERT_NO_FATAL_FAILURE(open_memory(db));
    starling::persistence::MigrationRunner r(db);
    r.migrate_to_latest();
    const auto applied = r.applied();
    EXPECT_FALSE(applied.empty());
    EXPECT_EQ(applied.front().version, 1);
    sqlite3_close(db);
}

TEST(MigrationRunner, IdempotentSecondRun) {
    sqlite3* db;
    ASSERT_NO_FATAL_FAILURE(open_memory(db));
    starling::persistence::MigrationRunner r(db);
    r.migrate_to_latest();
    const auto first = r.applied().size();
    r.migrate_to_latest();
    EXPECT_EQ(r.applied().size(), first);
    sqlite3_close(db);
}

TEST(MigrationRunner, P1MandatoryIndexExists) {
    sqlite3* db;
    ASSERT_NO_FATAL_FAILURE(open_memory(db));
    starling::persistence::MigrationRunner(db).migrate_to_latest();
    EXPECT_EQ(count_rows(db,
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='index' AND name='idx_statement_id_tenant'"), 1);
    sqlite3_close(db);
}

TEST(MigrationRunner, DetectsChecksumDrift) {
    sqlite3* db;
    ASSERT_NO_FATAL_FAILURE(open_memory(db));
    starling::persistence::MigrationRunner(db).migrate_to_latest();
    // Tamper: rewrite the recorded checksum so the next migrate sees drift.
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(db,
        "UPDATE schema_migrations SET checksum='deadbeef' WHERE version=1",
        nullptr, nullptr, &err), SQLITE_OK);
    EXPECT_THROW(
        starling::persistence::MigrationRunner(db).migrate_to_latest(),
        starling::persistence::MigrationDriftError);
    sqlite3_close(db);
}
