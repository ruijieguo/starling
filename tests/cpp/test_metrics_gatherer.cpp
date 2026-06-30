// Task 5.2: MetricsGatherer — outbox_lag_sequence from real schema.
//
// Schema (migrations/0001_initial_schema.sql):
//   bus_events.outbox_sequence          — monotonic outbox counter
//   consumer_checkpoint.consumer_id     — PRIMARY KEY text
//   consumer_checkpoint.last_delivered_sequence — delivered cursor
//
// Consumer: 'in_process' (memory_ops.cpp:255; tick_all's OutboxDispatcher).
//
// outbox_lag_sequence = MAX(bus_events.outbox_sequence)
//                     - consumer_checkpoint.last_delivered_sequence
//                       WHERE consumer_id = 'in_process'
// (missing checkpoint → treated as delivered=0; no events → 0.)
#include <gtest/gtest.h>

#include "starling/governance/metrics_gatherer.hpp"
#include "starling/governance/runtime_health_event.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <sqlite3.h>
#include <stdexcept>
#include <string>

using starling::governance::MetricsGatherer;
using starling::governance::MetricsSnapshot;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;

namespace {

// Open an in-memory DB with all migrations applied — mirrors sibling tests.
Connection fresh_db() {
    auto conn = Connection::open(":memory:");
    MigrationRunner(conn.raw()).migrate_to_latest();
    return conn;
}

// Insert one bus_events row with the given outbox_sequence.
// Only the columns needed for the lag query are populated; the rest use
// their schema DEFAULTs or a minimal non-null placeholder.
void insert_event(sqlite3* dbh, int64_t seq, const std::string& event_id) {
    const std::string sql =
        "INSERT INTO bus_events"
        "(event_id,tenant_id,event_type,primary_id,aggregate_id,"
        " outbox_sequence,idempotency_key,payload_json,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error("insert_event: prepare failed");
    }
    const std::string idem = "idem-" + event_id;
    sqlite3_bind_text(raw, 1, event_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, "tenant-1",       -1, SQLITE_STATIC);
    sqlite3_bind_text(raw, 3, "test.event",     -1, SQLITE_STATIC);
    sqlite3_bind_text(raw, 4, "primary-1",      -1, SQLITE_STATIC);
    sqlite3_bind_text(raw, 5, "agg-1",          -1, SQLITE_STATIC);
    sqlite3_bind_int64(raw, 6, seq);
    sqlite3_bind_text(raw, 7, idem.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 8, "{}",             -1, SQLITE_STATIC);
    sqlite3_bind_text(raw, 9, "2026-06-30T00:00:00Z", -1, SQLITE_STATIC);
    if (sqlite3_step(raw) != SQLITE_DONE) {
        sqlite3_finalize(raw);
        throw std::runtime_error("insert_event: step failed");
    }
    sqlite3_finalize(raw);
}

// Insert (or upsert) a consumer_checkpoint row.
void set_checkpoint(sqlite3* dbh, const std::string& consumer_id,
                    int64_t delivered_seq) {
    const std::string sql =
        "INSERT INTO consumer_checkpoint(consumer_id,last_delivered_sequence,updated_at)"
        " VALUES(?,?,?)"
        " ON CONFLICT(consumer_id) DO UPDATE SET"
        "   last_delivered_sequence=excluded.last_delivered_sequence,"
        "   updated_at=excluded.updated_at";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error("set_checkpoint: prepare failed");
    }
    sqlite3_bind_text(raw, 1, consumer_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(raw, 2, delivered_seq);
    sqlite3_bind_text(raw, 3, "2026-06-30T00:00:00Z", -1, SQLITE_STATIC);
    if (sqlite3_step(raw) != SQLITE_DONE) {
        sqlite3_finalize(raw);
        throw std::runtime_error("set_checkpoint: step failed");
    }
    sqlite3_finalize(raw);
}

}  // namespace

// ── 1. Empty DB → lag = 0 ───────────────────────────────────────────────────

TEST(MetricsGatherer, EmptyDbReturnsZeroLag) {
    auto conn = fresh_db();
    MetricsGatherer gatherer;

    const MetricsSnapshot snap = gatherer.gather(conn);

    EXPECT_EQ(snap.outbox_lag_sequence, 0LL);
}

// ── 2. Seeded events + matched checkpoint → exact lag ───────────────────────
//
// 3 events at sequences 1,2,3; checkpoint at delivered=1 → lag = 3-1 = 2.

TEST(MetricsGatherer, SeededEventsAndCheckpointReturnCorrectLag) {
    auto conn = fresh_db();
    MetricsGatherer gatherer;

    insert_event(conn.raw(), 1, "evt-1");
    insert_event(conn.raw(), 2, "evt-2");
    insert_event(conn.raw(), 3, "evt-3");
    set_checkpoint(conn.raw(), "in_process", 1);

    const MetricsSnapshot snap = gatherer.gather(conn);

    EXPECT_EQ(snap.outbox_lag_sequence, 2LL);  // MAX(3) - delivered(1)
}

// ── 3. Checkpoint fully caught up → lag = 0 ─────────────────────────────────

TEST(MetricsGatherer, CheckpointAtMaxSequenceReturnsZeroLag) {
    auto conn = fresh_db();
    MetricsGatherer gatherer;

    insert_event(conn.raw(), 5, "evt-5");
    insert_event(conn.raw(), 6, "evt-6");
    set_checkpoint(conn.raw(), "in_process", 6);

    const MetricsSnapshot snap = gatherer.gather(conn);

    EXPECT_EQ(snap.outbox_lag_sequence, 0LL);
}

// ── 4. Events but NO in_process checkpoint → lag = MAX(seq) (all undelivered)

TEST(MetricsGatherer, EventsWithNoCheckpointReturnsMaxSequence) {
    auto conn = fresh_db();
    MetricsGatherer gatherer;

    // Seed two events; no consumer_checkpoint row for 'in_process'.
    insert_event(conn.raw(), 10, "evt-10");
    insert_event(conn.raw(), 20, "evt-20");

    const MetricsSnapshot snap = gatherer.gather(conn);

    // Missing checkpoint → delivered treated as 0. lag = MAX(20) - 0 = 20.
    EXPECT_EQ(snap.outbox_lag_sequence, 20LL);
}

// ── 5. Checkpoint for a DIFFERENT consumer doesn't affect in_process lag ─────

TEST(MetricsGatherer, OtherConsumerCheckpointDoesNotAffectLag) {
    auto conn = fresh_db();
    MetricsGatherer gatherer;

    insert_event(conn.raw(), 7, "evt-7");
    insert_event(conn.raw(), 8, "evt-8");
    // Set checkpoint for a different consumer; in_process has none.
    set_checkpoint(conn.raw(), "belief_tracker", 8);

    const MetricsSnapshot snap = gatherer.gather(conn);

    // in_process still at 0 → lag = 8.
    EXPECT_EQ(snap.outbox_lag_sequence, 8LL);
}

// ── 6. Other 6 MetricsSnapshot fields remain at default (0 / 0.0) ────────────

TEST(MetricsGatherer, NonLagMetricsAreDefault) {
    auto conn = fresh_db();
    MetricsGatherer gatherer;

    insert_event(conn.raw(), 1, "evt-x");
    set_checkpoint(conn.raw(), "in_process", 0);

    const MetricsSnapshot snap = gatherer.gather(conn);

    EXPECT_EQ(snap.subscriber_failure_rate,       0.0);
    EXPECT_EQ(snap.extraction_queue_depth,        0LL);
    EXPECT_EQ(snap.projection_lag_seconds,        0.0);
    EXPECT_EQ(snap.runtime_event_loop_lag_ms,     0.0);
    EXPECT_EQ(snap.vector_delete_lag,             0LL);
    EXPECT_EQ(snap.erased_evidence_visible_count, 0LL);
}

// ── 7. Single event, checkpoint at same sequence → lag = 0 ───────────────────

TEST(MetricsGatherer, SingleEventCheckpointAtSameSeqReturnsZero) {
    auto conn = fresh_db();
    MetricsGatherer gatherer;

    insert_event(conn.raw(), 42, "evt-42");
    set_checkpoint(conn.raw(), "in_process", 42);

    const MetricsSnapshot snap = gatherer.gather(conn);

    EXPECT_EQ(snap.outbox_lag_sequence, 0LL);
}
