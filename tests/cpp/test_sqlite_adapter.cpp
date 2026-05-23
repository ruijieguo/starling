#include <gtest/gtest.h>
#include <sqlite3.h>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/final_query_assertion.hpp"

using starling::persistence::SqliteAdapter;

TEST(SqliteAdapter, DeclaredCapabilityHasOutboxAndCheckpoint) {
    auto a = SqliteAdapter::open(":memory:");
    const auto cap = a->declare_capability();
    EXPECT_EQ(cap.profile_name, "local-store-sqlite");
    EXPECT_TRUE(cap.transactional_outbox);
    EXPECT_TRUE(cap.consumer_checkpoint);
    EXPECT_TRUE(cap.cross_partition_transaction);
    EXPECT_EQ(cap.tenant_isolation, "storage_enforced");
    EXPECT_FALSE(cap.engram_per_record_key);  // M0.3 will set this
    EXPECT_FALSE(cap.testing_helper_marker);
}

TEST(SqliteAdapter, FinalQueryPredicateRejectsMissingTenantClause) {
    auto a = SqliteAdapter::open(":memory:");
    // check_final_query is the bool predicate variant — false on missing
    // guards, true when tenant_id + holder_scope are both present.
    EXPECT_FALSE(a->check_final_query("SELECT * FROM statements"));
    EXPECT_TRUE(a->check_final_query(
        "SELECT * FROM statements WHERE tenant_id=? AND holder_scope=?"));
}

TEST(SqliteAdapter, MigrationsRunOnOpen) {
    auto a = SqliteAdapter::open(":memory:");
    sqlite3_stmt* s = nullptr;
    // Use ASSERT_EQ so a prepare failure doesn't silently mask the real
    // intent of the test (verifying the index exists post-migration).
    ASSERT_EQ(sqlite3_prepare_v2(a->connection().raw(),
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='index' AND name='idx_statement_id_tenant'",
        -1, &s, nullptr), SQLITE_OK);
    ASSERT_EQ(sqlite3_step(s), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(s, 0), 1);
    sqlite3_finalize(s);
}
