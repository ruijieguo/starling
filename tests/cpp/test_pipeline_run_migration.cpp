// Task 3a.2: migration 0029_governance_pipeline_run — schema + invariant tests.
// Tests run BEFORE the store exists (Task 3a.3); all inserts use raw sqlite3 SQL.
// Migration helper: mirrors test_migration_0003.cpp / test_pipeline_ledger.cpp.
#include <gtest/gtest.h>
#include <sqlite3.h>

#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <string>

using starling::persistence::Connection;
using starling::persistence::MigrationRunner;

namespace {

// Open an in-memory DB with all migrations applied — same pattern as sibling tests.
Connection fresh_db() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

// Helper: execute a single SQL statement; return the sqlite3 step result code.
int exec_step(sqlite3* db, const char* sql) {
    sqlite3_stmt* s = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &s, nullptr) != SQLITE_OK) {
        return SQLITE_ERROR;
    }
    const int rc = sqlite3_step(s);
    sqlite3_finalize(s);
    return rc;
}

// Helper: check whether a named object exists in sqlite_master.
bool master_has(sqlite3* db, const char* type, const char* name) {
    sqlite3_stmt* s = nullptr;
    const char* sql =
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?;";
    if (sqlite3_prepare_v2(db, sql, -1, &s, nullptr) != SQLITE_OK) {
        return false;
    }
    sqlite3_bind_text(s, 1, type, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(s, 2, name, -1, SQLITE_TRANSIENT);
    const bool found = (sqlite3_step(s) == SQLITE_ROW);
    sqlite3_finalize(s);
    return found;
}

// Helper: read the 'sql' column from sqlite_master for a named object.
std::string master_sql(sqlite3* db, const char* name) {
    sqlite3_stmt* s = nullptr;
    const char* query =
        "SELECT sql FROM sqlite_master WHERE name=?;";
    if (sqlite3_prepare_v2(db, query, -1, &s, nullptr) != SQLITE_OK) {
        return "";
    }
    sqlite3_bind_text(s, 1, name, -1, SQLITE_TRANSIENT);
    std::string result;
    if (sqlite3_step(s) == SQLITE_ROW) {
        const auto* txt = reinterpret_cast<const char*>(sqlite3_column_text(s, 0));
        if (txt != nullptr) {
            result = txt;
        }
    }
    sqlite3_finalize(s);
    return result;
}

// Valid filler INSERT — all NOT NULL cols; JSON-default cols omitted.
// Params: ?1=id, ?2=kind, ?3=aggregate_id, ?4=tenant_id, ?5=status
const char* kInsertSQL =
    "INSERT INTO governance_pipeline_run("
    "  id, kind, aggregate_id, tenant_id,"
    "  profile_name, input_hash, idempotency_key,"
    "  pipeline_name, pipeline_version, status,"
    "  started_at, updated_at"
    ") VALUES ("
    "  ?1, ?2, ?3, ?4,"
    "  'default', 'h', 'k',"
    "  'replay', '1', ?5,"
    "  '2026-06-29T00:00:00Z', '2026-06-29T00:00:00Z'"
    ");";

// Execute the filler insert with bound params; return sqlite3 step result.
int do_insert(sqlite3* db, const char* id, const char* kind,
              const char* agg, const char* tenant, const char* status) {
    sqlite3_stmt* s = nullptr;
    if (sqlite3_prepare_v2(db, kInsertSQL, -1, &s, nullptr) != SQLITE_OK) {
        return SQLITE_ERROR;
    }
    sqlite3_bind_text(s, 1, id,     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(s, 2, kind,   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(s, 3, agg,    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(s, 4, tenant, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(s, 5, status, -1, SQLITE_TRANSIENT);
    const int rc = sqlite3_step(s);
    sqlite3_finalize(s);
    return rc;
}

}  // namespace

// ── 1. Table + both indices exist ─────────────────────────────────────────────

TEST(PipelineRunMigration, TableExists) {
    auto c = fresh_db();
    EXPECT_TRUE(master_has(c.raw(), "table", "governance_pipeline_run"));
}

TEST(PipelineRunMigration, ActiveIndexExists) {
    auto c = fresh_db();
    EXPECT_TRUE(master_has(c.raw(), "index", "idx_governance_pipeline_run_active"));
}

TEST(PipelineRunMigration, LeaseIndexExists) {
    auto c = fresh_db();
    EXPECT_TRUE(master_has(c.raw(), "index", "idx_governance_pipeline_run_lease"));
}

// ── 2. Partial-index DEFINITION is correct (frozen shape) ────────────────────

TEST(PipelineRunMigration, ActiveIndexDefinitionContainsKeyColumns) {
    auto c = fresh_db();
    const std::string sql =
        master_sql(c.raw(), "idx_governance_pipeline_run_active");
    ASSERT_FALSE(sql.empty()) << "Index DDL not found in sqlite_master";
    // Four key columns in order
    EXPECT_NE(sql.find("kind"),        std::string::npos);
    EXPECT_NE(sql.find("tenant_id"),   std::string::npos);
    EXPECT_NE(sql.find("aggregate_id"),std::string::npos);
    EXPECT_NE(sql.find("input_hash"),  std::string::npos);
    // Partial-index WHERE clause
    EXPECT_NE(sql.find("QUEUED"),  std::string::npos);
    EXPECT_NE(sql.find("RUNNING"), std::string::npos);
}

// ── 3. CHECK(kind) rejects bad value ─────────────────────────────────────────

TEST(PipelineRunMigration, CheckKindRejectsBogus) {
    auto c = fresh_db();
    const int rc = do_insert(c.raw(), "id-kind-bad", "bogus",
                             "agg-1", "tenant-1", "QUEUED");
    EXPECT_EQ(rc, SQLITE_CONSTRAINT);
}

// ── 4. CHECK(status) rejects bad value ───────────────────────────────────────

TEST(PipelineRunMigration, CheckStatusRejectsBogus) {
    auto c = fresh_db();
    const int rc = do_insert(c.raw(), "id-status-bad", "extraction",
                             "agg-1", "tenant-1", "bogus");
    EXPECT_EQ(rc, SQLITE_CONSTRAINT);
}

// ── 5. Invariant-1 duplicate rejection (partial UNIQUE index) ────────────────

TEST(PipelineRunMigration, Invariant1DuplicateActiveRejected) {
    auto c = fresh_db();

    // First active row — must succeed.
    EXPECT_EQ(do_insert(c.raw(), "id-active-1", "extraction",
                        "agg-A", "tenant-1", "QUEUED"), SQLITE_DONE);

    // Second row — same (kind, tenant_id, aggregate_id, input_hash), both QUEUED
    // → partial UNIQUE index blocks it.
    EXPECT_EQ(do_insert(c.raw(), "id-active-2", "extraction",
                        "agg-A", "tenant-1", "QUEUED"), SQLITE_CONSTRAINT);

    // Terminal-status row with the same key — NOT covered by partial index → OK.
    EXPECT_EQ(do_insert(c.raw(), "id-terminal", "extraction",
                        "agg-A", "tenant-1", "COMPLETED"), SQLITE_DONE);

    // Different tenant_id, same kind/aggregate/hash, QUEUED → OK (tenant isolation).
    EXPECT_EQ(do_insert(c.raw(), "id-other-tenant", "extraction",
                        "agg-A", "tenant-2", "QUEUED"), SQLITE_DONE);
}

// ── 6. JSON1 probe ────────────────────────────────────────────────────────────

TEST(PipelineRunMigration, Json1IsAvailable) {
    auto c = fresh_db();
    // json_insert must succeed — proves JSON1 extension is compiled in.
    const int rc = exec_step(c.raw(), "SELECT json_insert('[]', '$[#]', 1);");
    // SQLITE_ROW means the SELECT returned a result → JSON1 worked.
    EXPECT_EQ(rc, SQLITE_ROW)
        << "JSON1 is NOT available in this build — record_stage_timing "
           "(Task 3a.6) will need a non-JSON1 fallback";
}
