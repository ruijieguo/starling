// test_projection_repair_guard.cpp -- TC-PROJECTION-REPAIR
//
// TC-REPAIR-001  HealthyRebuildReplacesActive:
//   seed 3 statements; rebuild_projection('proj_holder_state_time') →
//   report.truncation_suspected=false; proj_holder_state_time has 3 rows;
//   projection_rebuild_state.status='active'.
//
// TC-REPAIR-002  TruncationKeepsOldActive:
//   seed 3 statements; healthy rebuild first (proj has 3).
//   rebuild_projection_with_injected_count('proj_holder_state_time', injected=2) →
//   report.truncation_suspected=true; proj_holder_state_time STILL has 3 rows;
//   projection_rebuild_state.status='truncation_suspected';
//   a projection.rebuild_failed bus event exists.

#include "starling/projection/projection_maintainer.hpp"

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling::projection;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;

namespace {

// ── Helpers ──────────────────────────────────────────────────────────────────

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

// Seed a statement row.
void seed_stmt(sqlite3* db, const std::string& id,
               const std::string& tenant = "default",
               const std::string& holder_id = "alice") {
    std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,consolidation_state,review_status,confidence_history_json,"
        "created_at,updated_at) VALUES('"
        + id + "','" + tenant + "','" + holder_id + "',"
        "'first_person','cognizer','bob','knows','str','x','"
        + std::string(64, 'a') + "','v1','believes','pos',0.7,"
        "'2026-05-27T09:00:00Z',0.5,'{}',0.0,'2026-05-27T09:00:00Z',"
        "'user_input','consolidated','approved','[]',"
        "'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr);
}

// Read a single int column from a query.
int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

// Read a single text column from a query.
std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const char* t = reinterpret_cast<const char*>(sqlite3_column_text(s, 0));
    std::string v = t ? t : "";
    sqlite3_finalize(s);
    return v;
}

}  // namespace

// ── TC-REPAIR-001: HealthyRebuildReplacesActive ──────────────────────────────

TEST(ProjectionRepairGuard, HealthyRebuildReplacesActive) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ProjectionMaintainer pm(*adapter);

    // Seed 3 statements.
    seed_stmt(conn.raw(), "s1");
    seed_stmt(conn.raw(), "s2");
    seed_stmt(conn.raw(), "s3");

    // Full rebuild.
    RebuildReport r = pm.rebuild_projection(conn, "proj_holder_state_time",
                                            "2026-05-27T10:00:00Z");

    // Report: healthy.
    EXPECT_FALSE(r.truncation_suspected);
    EXPECT_EQ(r.ground_truth_count, 3);
    EXPECT_EQ(r.rebuilt_count, 3);

    // Projection table has 3 rows.
    EXPECT_EQ(icol(conn.raw(), "SELECT COUNT(*) FROM proj_holder_state_time"), 3);

    // projection_rebuild_state.status = 'active'.
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM projection_rebuild_state "
        "WHERE projection_name='proj_holder_state_time'"), "active");

    // ground_truth_count and index_count recorded.
    EXPECT_EQ(icol(conn.raw(),
        "SELECT ground_truth_count FROM projection_rebuild_state "
        "WHERE projection_name='proj_holder_state_time'"), 3);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT index_count FROM projection_rebuild_state "
        "WHERE projection_name='proj_holder_state_time'"), 3);
}

// ── TC-REPAIR-002: TruncationKeepsOldActive ─────────────────────────────────

TEST(ProjectionRepairGuard, TruncationKeepsOldActive) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ProjectionMaintainer pm(*adapter);

    // Seed 3 statements.
    seed_stmt(conn.raw(), "s1");
    seed_stmt(conn.raw(), "s2");
    seed_stmt(conn.raw(), "s3");

    // First: healthy rebuild → proj has 3 rows.
    RebuildReport r1 = pm.rebuild_projection(conn, "proj_holder_state_time",
                                             "2026-05-27T10:00:00Z");
    EXPECT_FALSE(r1.truncation_suspected);
    EXPECT_EQ(icol(conn.raw(), "SELECT COUNT(*) FROM proj_holder_state_time"), 3);

    // Now inject a low rebuilt count (2 < 3 → truncation).
    RebuildReport r2 = pm.rebuild_projection_with_injected_count(
        conn, "proj_holder_state_time", /*injected_rebuilt=*/2,
        "2026-05-27T10:01:00Z");

    // Report: truncation detected.
    EXPECT_TRUE(r2.truncation_suspected);
    EXPECT_EQ(r2.ground_truth_count, 3);
    EXPECT_EQ(r2.rebuilt_count, 2);

    // Old active projection is UNCHANGED — still 3 rows.
    EXPECT_EQ(icol(conn.raw(), "SELECT COUNT(*) FROM proj_holder_state_time"), 3);

    // projection_rebuild_state.status = 'truncation_suspected'.
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM projection_rebuild_state "
        "WHERE projection_name='proj_holder_state_time'"), "truncation_suspected");

    // A projection.rebuild_failed bus event must exist.
    EXPECT_GE(icol(conn.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='projection.rebuild_failed'"), 1);
}
