// test_projection_incremental.cpp -- Tests for ProjectionMaintainer::tick_one_batch.
//
// TC-P1-001  ConsolidatedStatementProjected:
//   seed stmt + statement.consolidated event → tick → 4 projection tables have row.
// TC-P1-002  ArchivedStatementPurgedFromProjections:
//   project a stmt, then archive it + emit statement.archived → tick → rows deleted.
// TC-P1-003  CheckpointAdvancesIdempotent:
//   second tick with no new events → events_processed=0, no duplicate rows.

#include "starling/projection/projection_maintainer.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling::projection;
using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;
using starling::persistence::TransactionGuard;

namespace {

// ── Helpers ──────────────────────────────────────────────────────────────────

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

// Seed a statement row with the given consolidation_state and holder_id.
void seed_stmt(sqlite3* db, const std::string& id,
               const std::string& consolidation_state = "consolidated",
               const std::string& tenant = "default",
               const std::string& holder_id = "alice",
               const std::string& modality = "believes",
               double salience = 0.5) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "confidence_history_json,created_at,updated_at) VALUES('"
        + id + "','" + tenant + "','" + holder_id + "',"
        "'first_person','cognizer','bob','knows','str','x','"
        + std::string(64, 'a') + "','v1','" + modality
        + "','pos',0.7,'2026-05-27T09:00:00Z',"
        + std::to_string(salience) + ",'{}',0.0,"
        "'2026-05-27T09:00:00Z','user_input','" + consolidation_state
        + "','approved','[]',"
        "'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    int rc = sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
    (void)rc;
}

// Emit a statement.* event via OutboxWriter (robust path matching reconsolidation tests).
void emit_stmt_event(Connection& conn,
                     const std::string& event_type,
                     const std::string& stmt_id,
                     const std::string& ikey) {
    TransactionGuard tx(conn);
    OutboxWriter ow(conn);
    BusEvent ev;
    ev.tenant_id       = "default";
    ev.event_type      = event_type;
    ev.primary_id      = stmt_id;
    ev.aggregate_id    = stmt_id;
    ev.idempotency_key = ikey;
    ev.payload_json    = "{}";
    ow.append(ev);
    tx.commit();
}

// Read a single int column.
int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

// Read the projection_subscriber_checkpoint value.
int get_proj_checkpoint(Connection& conn) {
    return icol(conn.raw(),
        "SELECT last_processed_outbox_sequence "
        "FROM projection_subscriber_checkpoint WHERE id=1");
}

}  // namespace

// ── TC-P1-001: ConsolidatedStatementProjected ────────────────────────────────

TEST(ProjectionIncremental, ConsolidatedStatementProjected) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ProjectionMaintainer pm(*adapter);

    seed_stmt(conn.raw(), "stmt-c1", "consolidated");
    emit_stmt_event(conn, "statement.consolidated", "stmt-c1", "ikey-c1");

    auto stats = pm.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(stats.events_processed, 1);
    EXPECT_GT(stats.rows_upserted, 0);

    // proj_holder_state_time
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_holder_state_time WHERE stmt_id='stmt-c1'"), 1);

    // proj_holder_subgraph
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_holder_subgraph WHERE stmt_id='stmt-c1'"), 1);

    // proj_entity_statement
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_entity_statement WHERE stmt_id='stmt-c1'"), 1);

    // proj_salience_hot
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_salience_hot WHERE stmt_id='stmt-c1'"), 1);

    // checkpoint advanced
    EXPECT_GT(get_proj_checkpoint(conn), 0);
}

// ── TC-P1-002: ArchivedStatementPurgedFromProjections ───────────────────────

TEST(ProjectionIncremental, ArchivedStatementPurgedFromProjections) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ProjectionMaintainer pm(*adapter);

    // Step 1: seed + project.
    seed_stmt(conn.raw(), "stmt-arch", "consolidated");
    emit_stmt_event(conn, "statement.consolidated", "stmt-arch", "ikey-arch-1");
    auto s1 = pm.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(s1.events_processed, 1);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_holder_state_time WHERE stmt_id='stmt-arch'"), 1);

    // Step 2: archive the statement.
    sqlite3_exec(conn.raw(),
        "UPDATE statements SET consolidation_state='archived' WHERE id='stmt-arch'",
        nullptr, nullptr, nullptr);
    emit_stmt_event(conn, "statement.archived", "stmt-arch", "ikey-arch-2");

    auto s2 = pm.tick_one_batch(conn, "2026-05-27T10:01:00Z");
    EXPECT_EQ(s2.events_processed, 1);

    // All 5 projection rows must be gone.
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_holder_state_time WHERE stmt_id='stmt-arch'"), 0);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_holder_subgraph WHERE stmt_id='stmt-arch'"), 0);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_entity_statement WHERE stmt_id='stmt-arch'"), 0);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_salience_hot WHERE stmt_id='stmt-arch'"), 0);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_commitment_due WHERE stmt_id='stmt-arch'"), 0);
}

// ── TC-P1-003: CheckpointAdvancesIdempotent ──────────────────────────────────

TEST(ProjectionIncremental, CheckpointAdvancesIdempotent) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ProjectionMaintainer pm(*adapter);

    seed_stmt(conn.raw(), "stmt-idem", "consolidated");
    emit_stmt_event(conn, "statement.written", "stmt-idem", "ikey-idem-1");

    // First tick processes 1 event.
    auto s1 = pm.tick_one_batch(conn, "2026-05-27T10:00:00Z");
    EXPECT_EQ(s1.events_processed, 1);
    int chk1 = get_proj_checkpoint(conn);
    EXPECT_GT(chk1, 0);

    // Count rows after first tick.
    int rows_after_first = icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_holder_state_time WHERE stmt_id='stmt-idem'");
    EXPECT_EQ(rows_after_first, 1);

    // Second tick: no new events.
    auto s2 = pm.tick_one_batch(conn, "2026-05-27T10:01:00Z");
    EXPECT_EQ(s2.events_processed, 0);
    EXPECT_EQ(s2.rows_upserted, 0);

    // Checkpoint stays the same.
    int chk2 = get_proj_checkpoint(conn);
    EXPECT_EQ(chk1, chk2);

    // Row count unchanged.
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM proj_holder_state_time WHERE stmt_id='stmt-idem'"),
        rows_after_first);
}

// ── TC-P1-004: RebuildProjectionThrowsNotImplemented ────────────────────────

TEST(ProjectionIncremental, RebuildProjectionThrowsNotImplemented) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    ProjectionMaintainer pm(*adapter);

    EXPECT_THROW(
        pm.rebuild_projection(conn, "proj_holder_state_time", "2026-05-27T10:00:00Z"),
        std::runtime_error
    );
}
