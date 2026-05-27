#include "starling/tom/depth_estimator.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <string>

namespace starling::tom::depth_estimator {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Insert a statement row directly, allowing control over nesting_depth,
// consolidation_state, and observed_at.
void insert_raw_statement(persistence::Connection& conn,
                          const std::string& id,
                          const std::string& tenant_id,
                          const std::string& holder_id,
                          const std::string& subject_id,
                          const std::string& predicate,
                          const std::string& consolidation_state,
                          int nesting_depth,
                          const std::string& observed_at) {
    sqlite3* db = conn.raw();
    const std::string sql =
        "INSERT INTO statements("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate, object_kind, object_value,"
        "  canonical_object_hash, canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at,"
        "  salience, affect_json, activation, last_accessed,"
        "  provenance, evidence_json, source_spans_json, perceived_by_json,"
        "  consolidation_state, review_status,"
        "  derived_from_json, derived_depth,"
        "  nesting_depth,"
        "  created_at, updated_at"
        ") VALUES ("
        "  ?, ?, ?, 'first_person',"
        "  'cognizer', ?, ?, 'str', 'some-value',"
        "  'hash-abc', 'v1',"
        "  'believes', 'pos', 0.9, ?,"
        "  0.0, '{}', 0.0, ?,"
        "  'observed', '[]', '[]', '[]',"
        "  ?, 'approved',"
        "  '[]', 0,"
        "  ?,"
        "  ?, ?"
        ")";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h(raw);

    auto bind_str = [&](int idx, const std::string& v) {
        sqlite3_bind_text(h.get(), idx, v.c_str(), -1, SQLITE_TRANSIENT);
    };

    bind_str(1,  id);
    bind_str(2,  tenant_id);
    bind_str(3,  holder_id);
    bind_str(4,  subject_id);
    bind_str(5,  predicate);
    bind_str(6,  observed_at);    // observed_at
    bind_str(7,  observed_at);    // last_accessed
    bind_str(8,  consolidation_state);
    sqlite3_bind_int(h.get(), 9, nesting_depth);
    bind_str(10, observed_at);    // created_at
    bind_str(11, observed_at);    // updated_at

    ASSERT_EQ(sqlite3_step(h.get()), SQLITE_DONE) << sqlite3_errmsg(db);
}

}  // namespace

// ----- Tests ---------------------------------------------------------------

TEST(ToMDepthEstimatorCache, ZeroNestingDepthOneStatementsReturnsZero) {
    auto a = make_adapter();
    auto& conn = a->connection();

    const int depth = estimate(conn, "partner-1", "tenant-1",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(depth, 0);
}

TEST(ToMDepthEstimatorCache, OneToTwoStatementsReturnsOne) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert 1 qualifying statement: holder=partner, nesting_depth=1,
    // observed_at within 7d, consolidation_state=consolidated.
    insert_raw_statement(conn,
        "stmt-001", "tenant-1", "partner-1", "some-subject",
        "predicate-a", "consolidated", 1,
        "2026-05-26T10:00:00Z");

    const int depth = estimate(conn, "partner-1", "tenant-1",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(depth, 1);
}

TEST(ToMDepthEstimatorCache, ThreeOrMoreReturnsTwo) {
    auto a = make_adapter();
    auto& conn = a->connection();

    insert_raw_statement(conn,
        "stmt-001", "tenant-1", "partner-1", "subject-1",
        "pred-a", "consolidated", 1,
        "2026-05-26T10:00:00Z");
    insert_raw_statement(conn,
        "stmt-002", "tenant-1", "partner-1", "subject-2",
        "pred-b", "consolidated", 1,
        "2026-05-26T10:01:00Z");
    insert_raw_statement(conn,
        "stmt-003", "tenant-1", "partner-1", "subject-3",
        "pred-c", "archived", 1,
        "2026-05-26T10:02:00Z");

    const int depth = estimate(conn, "partner-1", "tenant-1",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(depth, 2);
}

TEST(ToMDepthEstimatorCache, OnlyCountsWithinSevenDays) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // observed_at = as_of - 8 days: outside the 7-day window.
    insert_raw_statement(conn,
        "stmt-old", "tenant-1", "partner-1", "subject-1",
        "pred-a", "consolidated", 1,
        "2026-05-18T12:00:00Z");  // 2026-05-26 - 8d = 2026-05-18

    const int depth = estimate(conn, "partner-1", "tenant-1",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(depth, 0);
}

TEST(ToMDepthEstimatorCache, OnlyCountsConsolidatedOrArchived) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // volatile consolidation_state — should NOT be counted.
    insert_raw_statement(conn,
        "stmt-vol", "tenant-1", "partner-1", "subject-1",
        "pred-a", "volatile", 1,
        "2026-05-26T10:00:00Z");

    const int depth = estimate(conn, "partner-1", "tenant-1",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(depth, 0);
}

TEST(ToMDepthEstimatorCache, CacheHitReturnsStaleResult) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // First call: DB empty → depth=0, cached at as_of.
    const int first = estimate(conn, "partner-1", "tenant-1",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(first, 0);

    // Now add 3 qualifying statements to the DB.
    insert_raw_statement(conn,
        "stmt-001", "tenant-1", "partner-1", "subject-1",
        "pred-a", "consolidated", 1,
        "2026-05-26T10:00:00Z");
    insert_raw_statement(conn,
        "stmt-002", "tenant-1", "partner-1", "subject-2",
        "pred-b", "consolidated", 1,
        "2026-05-26T10:01:00Z");
    insert_raw_statement(conn,
        "stmt-003", "tenant-1", "partner-1", "subject-3",
        "pred-c", "consolidated", 1,
        "2026-05-26T10:02:00Z");

    // Second call: same as_of (within 1h of last_recomputed_at=as_of) → cache hit → stale 0.
    const int second = estimate(conn, "partner-1", "tenant-1",
                                 "2026-05-26T12:00:00Z");
    EXPECT_EQ(second, 0);  // Stale cache value
}

TEST(ToMDepthEstimatorCache, CacheMissAfterTTLRecomputes) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert 3 qualifying statements.
    insert_raw_statement(conn,
        "stmt-001", "tenant-1", "partner-1", "subject-1",
        "pred-a", "consolidated", 1,
        "2026-05-26T10:00:00Z");
    insert_raw_statement(conn,
        "stmt-002", "tenant-1", "partner-1", "subject-2",
        "pred-b", "consolidated", 1,
        "2026-05-26T10:01:00Z");
    insert_raw_statement(conn,
        "stmt-003", "tenant-1", "partner-1", "subject-3",
        "pred-c", "consolidated", 1,
        "2026-05-26T10:02:00Z");

    // First call: computes count=3, depth=2, caches at 12:00:00.
    const int first = estimate(conn, "partner-1", "tenant-1",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(first, 2);

    // Forge last_recomputed_at to be > 1h in the past relative to new as_of.
    {
        sqlite3* db = conn.raw();
        sqlite3_stmt* raw = nullptr;
        ASSERT_EQ(sqlite3_prepare_v2(db,
            "UPDATE tom_depth_estimator_cache"
            " SET last_recomputed_at = '2026-05-26T10:00:00Z'"
            " WHERE tenant_id = 'tenant-1' AND partner_id = 'partner-1'",
            -1, &raw, nullptr), SQLITE_OK);
        persistence::StmtHandle h(raw);
        ASSERT_EQ(sqlite3_step(h.get()), SQLITE_DONE);
    }

    // Remove all statements so the recomputed count drops to 0.
    {
        sqlite3* db = conn.raw();
        sqlite3_stmt* raw = nullptr;
        ASSERT_EQ(sqlite3_prepare_v2(db,
            "DELETE FROM statements WHERE tenant_id = 'tenant-1'",
            -1, &raw, nullptr), SQLITE_OK);
        persistence::StmtHandle h(raw);
        ASSERT_EQ(sqlite3_step(h.get()), SQLITE_DONE);
    }

    // Second call at 12:30:00 with last_recomputed_at=10:00:00 → expired (>1h) → recompute.
    const int second = estimate(conn, "partner-1", "tenant-1",
                                 "2026-05-26T12:30:00Z");
    EXPECT_EQ(second, 0);  // Recomputed value
}

TEST(ToMDepthEstimatorCache, TenantIsolation) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert 3 qualifying statements in tenant-a.
    insert_raw_statement(conn,
        "stmt-001", "tenant-a", "partner-1", "subject-1",
        "pred-a", "consolidated", 1,
        "2026-05-26T10:00:00Z");
    insert_raw_statement(conn,
        "stmt-002", "tenant-a", "partner-1", "subject-2",
        "pred-b", "consolidated", 1,
        "2026-05-26T10:01:00Z");
    insert_raw_statement(conn,
        "stmt-003", "tenant-a", "partner-1", "subject-3",
        "pred-c", "consolidated", 1,
        "2026-05-26T10:02:00Z");

    // Estimate for tenant-b — should return 0 (different tenant, no statements).
    const int depth = estimate(conn, "partner-1", "tenant-b",
                                "2026-05-26T12:00:00Z");
    EXPECT_EQ(depth, 0);
}

}  // namespace starling::tom::depth_estimator
