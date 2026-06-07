// test_reconsolidation_engine.cpp -- Tests for ReconsolidationEngine.
//
// TC-A5-001  tick_one_batch: belief.conflict event → window opened, checkpoint advances.
// TC-A5-002  close_due_windows: arbitrates expired window → window status=closed.
// TC-A5-003  commitment.fulfilled event → NOT opened (P2.c stub).
// TC-A5-004  TC-A5-002 fallback: deleted stmt → no throw, window still closed.

#include "starling/reconsolidation/reconsolidation_engine.hpp"
#include "starling/reconsolidation/plastic_window.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling::reconsolidation;
using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;
using starling::persistence::TransactionGuard;

namespace {

// ── Helpers ──────────────────────────────────────────────────────────────────

// Open a fresh in-memory DB with all migrations applied.
std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

// Seed a consolidated statement row.
void seed_stmt(sqlite3* db, const std::string& id,
               const std::string& tenant = "default",
               const std::string& modality = "believes") {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "confidence_history_json,created_at,updated_at) VALUES('" + id + "','" + tenant + "','alice',"
        "'first_person','cognizer','bob','knows','str','x','" + std::string(64,'a') + "','v1','"
        + modality + "','pos',0.7,'2026-05-27T09:00:00Z',0.5,'{}',0.0,"
        "'2026-05-27T09:00:00Z','user_input','consolidated','approved','[]',"
        "'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

// Append a bus event via OutboxWriter.
void append_bus_event(Connection& conn,
                      const std::string& event_type,
                      const std::string& primary_id,
                      const std::string& tenant_id,
                      const std::string& payload_json,
                      const std::string& ikey) {
    TransactionGuard tx(conn);
    OutboxWriter ow(conn);
    BusEvent ev;
    ev.tenant_id       = tenant_id;
    ev.event_type      = event_type;
    ev.primary_id      = primary_id;
    ev.aggregate_id    = primary_id;
    ev.idempotency_key = ikey;
    ev.payload_json    = payload_json;
    ow.append(ev);
    tx.commit();
}

// Read single text column.
std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const auto* txt = sqlite3_column_text(s, 0);
    std::string v = txt ? reinterpret_cast<const char*>(txt) : "";
    sqlite3_finalize(s);
    return v;
}

// Read single int column.
int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

// Read reconsolidation_checkpoint value.
int get_recon_checkpoint(Connection& conn) {
    return icol(conn.raw(),
        "SELECT last_processed_outbox_sequence "
        "FROM reconsolidation_checkpoint WHERE id=1");
}

}  // namespace

// ── TC-A5-001: belief.conflict event → window opened, checkpoint advances ──

TEST(ReconsolidationEngine, TickBeliefConflictOpensWindow) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    // Seed a consolidated statement.
    seed_stmt(conn.raw(), "stmt-1");

    // Emit a belief.conflict bus event for that statement.
    append_bus_event(conn, "belief.conflict", "stmt-1", "default",
                     "{}", "ikey-bc-1");

    // Run a tick.
    auto stats = engine.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(stats.events_processed, 1);
    EXPECT_EQ(stats.windows_opened, 1);

    // Window row should exist and be open.
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-1'"),
        "open");

    // Checkpoint should have advanced beyond 0.
    int chk = get_recon_checkpoint(conn);
    EXPECT_GT(chk, 0);
}

// ── TC-A5-001b: statement.recalled also opens a window ──────────────────────

TEST(ReconsolidationEngine, TickRecalledOpensWindow) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    seed_stmt(conn.raw(), "stmt-2");
    append_bus_event(conn, "statement.recalled", "stmt-2", "default",
                     "{}", "ikey-rec-1");

    auto stats = engine.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(stats.events_processed, 1);
    EXPECT_EQ(stats.windows_opened, 1);
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-2'"),
        "open");
}

TEST(ReconsolidationEngine, TickUsesEventTenantForSharedStmtId) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    seed_stmt(conn.raw(), "stmt-shared", "tenant-a");
    seed_stmt(conn.raw(), "stmt-shared", "tenant-b", "COMMITS");
    append_bus_event(conn, "statement.recalled", "stmt-shared", "tenant-b",
                     "{}", "ikey-rec-shared-b");

    auto stats = engine.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(stats.events_processed, 1);
    EXPECT_EQ(stats.windows_opened, 1);

    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM reconsolidation_windows WHERE stmt_id='stmt-shared'"), 1);
    EXPECT_EQ(scol(conn.raw(),
        "SELECT tenant_id FROM reconsolidation_windows WHERE stmt_id='stmt-shared'"), "tenant-b");
}

// ── TC-A5-001c: checkpoint idempotency — second tick sees 0 events ──────────

TEST(ReconsolidationEngine, CheckpointAdvancesAndIdempotent) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    seed_stmt(conn.raw(), "stmt-3");
    append_bus_event(conn, "belief.conflict", "stmt-3", "default",
                     "{}", "ikey-bc-idem");

    auto s1 = engine.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(s1.events_processed, 1);

    // Second tick: nothing new.
    auto s2 = engine.tick_one_batch(conn, "2026-05-27T10:01:00Z");
    EXPECT_EQ(s2.events_processed, 0);
    EXPECT_EQ(s2.windows_opened, 0);
}

// ── TC-A5-002: close_due_windows arbitrates expired window ──────────────────

TEST(ReconsolidationEngine, CloseDueWindowsArbitrates) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    // Open a window via the explicit API.
    seed_stmt(conn.raw(), "stmt-arb");
    engine.reconsolidate(conn, "stmt-arb", "belief.conflict", "hash-1", 1.0,
                         "2026-05-27T10:00:00Z");

    // Window is open; deadline is ~30 min out.
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-arb'"),
        "open");

    // Should not be due yet (10 minutes later).
    int closed_early = engine.close_due_windows(conn, "2026-05-27T10:10:00Z");
    EXPECT_EQ(closed_early, 0);

    // Past deadline (2 hours later) → should arbitrate and close.
    int closed = engine.close_due_windows(conn, "2026-05-27T12:00:00Z");
    EXPECT_EQ(closed, 1);

    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-arb'"),
        "closed");
}

// ── TC-A5-003: commitment.fulfilled → NOT opened ────────────────────────────

TEST(ReconsolidationEngine, CommitmentFulfilledIsSkipped) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    seed_stmt(conn.raw(), "stmt-c");
    append_bus_event(conn, "commitment.fulfilled", "stmt-c", "default",
                     "{}", "ikey-cf-1");
    append_bus_event(conn, "commitment.broken", "stmt-c", "default",
                     "{}", "ikey-cb-1");

    auto stats = engine.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(stats.events_processed, 2);
    EXPECT_EQ(stats.windows_opened, 0);

    // No window should have been opened.
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM reconsolidation_windows WHERE stmt_id='stmt-c'"), 0);
}

// ── TC-A5-004: deleted stmt → fallback, no throw, window still closed ───────

TEST(ReconsolidationEngine, FallbackDeletedStmtDoesNotThrow) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    // Open a window for a statement that will be deleted.
    seed_stmt(conn.raw(), "stmt-del");
    engine.reconsolidate(conn, "stmt-del", "belief.conflict", "hash-del", 1.0,
                         "2026-05-27T10:00:00Z");

    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-del'"),
        "open");

    // Delete the statement (simulates a race condition).
    sqlite3_exec(conn.raw(),
        "DELETE FROM statements WHERE id='stmt-del'",
        nullptr, nullptr, nullptr);

    // close_due_windows should NOT throw, and the window should end up closed.
    int closed = 0;
    EXPECT_NO_THROW(
        closed = engine.close_due_windows(conn, "2026-05-27T12:00:00Z")
    );
    EXPECT_EQ(closed, 1);

    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-del'"),
        "closed");
}

// ── reconsolidate explicit API: opens then appends on repeat call ─────────

TEST(ReconsolidationEngine, ReconsolidateOpensAndAppends) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    seed_stmt(conn.raw(), "stmt-r");

    // First call: opens window.
    engine.reconsolidate(conn, "stmt-r", "belief.conflict", "hash-r1", 1.0,
                         "2026-05-27T10:00:00Z");
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-r'"),
        "open");

    // Second call with a different hash (different event_id): appends.
    engine.reconsolidate(conn, "stmt-r", "belief.conflict", "hash-r2", 0.5,
                         "2026-05-27T10:01:00Z");

    // Window is still open (not yet closed) after two triggers.
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM reconsolidation_windows WHERE stmt_id='stmt-r'"),
        "open");

    // There should be 1 pending evidence entry (from the second call).
    EXPECT_GE(icol(conn.raw(),
        "SELECT COUNT(*) FROM reconsolidation_pending_evidence "
        "WHERE window_stmt_id='stmt-r'"), 1);
}

TEST(ReconsolidationEngine, ReconsolidateMissingStatementIsNoOp) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    EXPECT_NO_THROW(engine.reconsolidate(conn, "missing", "belief.conflict",
                                         "hash-missing", 1.0,
                                         "2026-05-27T10:00:00Z"));
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM reconsolidation_windows WHERE stmt_id='missing'"),
        0);
}

TEST(ReconsolidationEngine, ReconsolidateAmbiguousSharedStmtIdFailsClosed) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    seed_stmt(conn.raw(), "stmt-shared", "tenant-a");
    seed_stmt(conn.raw(), "stmt-shared", "tenant-b");

    EXPECT_THROW(engine.reconsolidate(conn, "stmt-shared", "belief.conflict",
                                      "hash-shared", 1.0,
                                      "2026-05-27T10:00:00Z"),
                 std::runtime_error);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM reconsolidation_windows WHERE stmt_id='stmt-shared'"),
        0);
}

// ── Regression: severe arbitration inside an outer SAVEPOINT (pump context) ──
//
// SubscriberPump::run_isolated wraps each subscriber in `SAVEPOINT sub_*`, so in
// production close_due_windows runs inside an active savepoint-transaction.
// apply_severe_contradict previously opened a persistence::TransactionGuard
// (BEGIN IMMEDIATE), which throws "cannot start a transaction within a
// transaction" inside that savepoint; close_due_windows' fallback then silently
// swallowed it and the severe fork was lost. With the SAVEPOINT-based guard the
// 4-item severe commit lands correctly in BOTH contexts. This test reproduces
// the pump context by wrapping close_due_windows in an explicit outer SAVEPOINT.
TEST(ReconsolidationEngine, SevereArbitrationWorksInsideOuterSavepoint) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ReconsolidationEngine engine(*adapter);

    seed_stmt(conn.raw(), "stmt-sev");
    // Accumulate high-weight contradicting evidence (first call opens the window
    // with no pending row; calls 2-5 append pending evidence) → strength 1.0
    // > 0.7 → severe. Mirrors the Python TC-A8-001 setup.
    for (int i = 0; i < 5; ++i) {
        engine.reconsolidate(conn, "stmt-sev", "belief.conflict",
                             "hash-sev-" + std::to_string(i), 1.0,
                             "2026-05-27T10:00:00Z");
    }

    // Simulate the pump: wrap close_due_windows in an outer SAVEPOINT.
    ASSERT_EQ(sqlite3_exec(conn.raw(), "SAVEPOINT sub_reconsolidation",
                           nullptr, nullptr, nullptr), SQLITE_OK);
    int closed = 0;
    EXPECT_NO_THROW(
        closed = engine.close_due_windows(conn, "2026-05-27T12:00:00Z"));
    ASSERT_EQ(sqlite3_exec(conn.raw(), "RELEASE sub_reconsolidation",
                           nullptr, nullptr, nullptr), SQLITE_OK);

    EXPECT_EQ(closed, 1);

    // The severe fork must have committed inside the outer savepoint:
    //  (1) a new reconsolidation_derived CONSOLIDATED statement exists,
    //  (2) the old statement is archived,
    //  (3) a SUPERSEDES edge new→old was created.
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM statements WHERE provenance='reconsolidation_derived' "
        "AND consolidation_state='consolidated'"), 1);
    EXPECT_EQ(scol(conn.raw(),
        "SELECT consolidation_state FROM statements WHERE id='stmt-sev'"), "archived");
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM statement_edges WHERE dst_id='stmt-sev' "
        "AND edge_kind='supersedes'"), 1);
}
