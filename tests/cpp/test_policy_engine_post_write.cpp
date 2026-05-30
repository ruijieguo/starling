// test_policy_engine_post_write.cpp -- P2.c PolicyEngine.run_post_write (Task 8).
//
// CreatesActiveCommitmentFromWrittenEvent: statement.written(COMMITS) →
//   ACTIVE commitment + a 'time' trigger registered.
// CheckpointAdvancesNoDoubleProcess: a second run_post_write processes 0 new
//   events — no duplicate commitment / trigger.

#include "starling/prospective/policy_engine.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <string>

using namespace starling::prospective;
using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::TransactionGuard;

namespace {

// Seed a COMMITS statement (copied from test_commitment_engine.cpp). observed_at
// doubles as the deadline source (event_time_end is also set here).
void seed_commits_stmt(sqlite3* db, const std::string& id) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,"
        "event_time_end,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('" + id + "','default','alice','first_person','cognizer',"
        "'bob','will_send','str','report','" + std::string(64, 'a') + "','v1','COMMITS','pos',0.9,"
        "'2026-05-30T09:00:00Z','2026-05-30T18:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','consolidated',"
        "'approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

// Append a bus event via OutboxWriter (auto-assigns outbox_sequence).
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

std::string scol(sqlite3* db, const std::string& q) {
    std::string out;
    sqlite3_exec(db, q.c_str(),
        [](void* p, int, char** v, char**) { *(std::string*)p = v[0] ? v[0] : ""; return 0; },
        &out, nullptr);
    return out;
}

int icol(sqlite3* db, const std::string& q) {
    int n = 0;
    sqlite3_exec(db, q.c_str(),
        [](void* p, int, char** v, char**) { *(int*)p = v[0] ? atoi(v[0]) : 0; return 0; },
        &n, nullptr);
    return n;
}

}  // namespace

TEST(PolicyEnginePostWrite, CreatesActiveCommitmentFromWrittenEvent) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    append_bus_event(c, "statement.written", "c1", "default", "{}", "ikey-sw-1");

    PolicyEngine(*a).run_post_write(c, "2026-05-30T10:00:00Z");

    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='c1'"), "ACTIVE");
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM commitment_triggers WHERE commitment_stmt_id='c1' AND kind='time'"),
        1);
}

TEST(PolicyEnginePostWrite, CheckpointAdvancesNoDoubleProcess) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    append_bus_event(c, "statement.written", "c1", "default", "{}", "ikey-sw-1");

    PolicyEngine eng(*a);
    eng.run_post_write(c, "2026-05-30T10:00:00Z");

    const int commitments_after_first =
        icol(c.raw(), "SELECT COUNT(*) FROM commitments");
    const int triggers_after_first =
        icol(c.raw(), "SELECT COUNT(*) FROM commitment_triggers WHERE commitment_stmt_id='c1'");

    // Second run: checkpoint already past the only event → no new processing.
    eng.run_post_write(c, "2026-05-30T11:00:00Z");

    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM commitments"), commitments_after_first);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM commitment_triggers WHERE commitment_stmt_id='c1'"),
        triggers_after_first);
}

// Regression (final-review): commitment.fulfilled must NOT feedback-loop through
// run_post_write. fulfill() is the sole emitter of commitment.fulfilled;
// run_post_write consuming it must not re-fulfill (already terminal) and re-emit,
// else bus_events floods across window buckets.
TEST(PolicyEnginePostWrite, FulfilledEventDoesNotFeedbackLoop) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    append_bus_event(c, "statement.written", "c1", "default", "{}", "ikey-sw-1");
    PolicyEngine eng(*a);
    eng.run_post_write(c, "2026-05-30T10:00:00Z");  // → ACTIVE
    CommitmentEngine(*a).fulfill(c, "c1", "2026-05-30T10:05:00Z");  // emits commitment.fulfilled
    const int after_fulfill = icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.fulfilled' AND primary_id='c1'");
    // Multiple run_post_write in DISTINCT window buckets — must not grow the count.
    eng.run_post_write(c, "2026-05-30T10:10:00Z");
    eng.run_post_write(c, "2026-05-30T10:20:00Z");
    eng.run_post_write(c, "2026-05-30T10:30:00Z");
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.fulfilled' AND primary_id='c1'"),
        after_fulfill);  // no feedback growth
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM commitments WHERE stmt_id='c1' AND state='FULFILLED'"), 1);
}
