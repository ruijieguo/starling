// Tests for belief_tracker::tick_one_batch.
// Scenarios:
//   1. EmptyOutboxIsNoop           -- fresh DB, tick -> events_processed=0.
//   2. StatementWrittenWritesFrontierFacts -- statement.written event -> frontier_facts_written>=1.
//   3. EvidenceAppendedRecordsAccessibleSource -- evidence.appended event -> frontier fact created.
//   4. CheckpointAdvances          -- after processing, checkpoint = max event sequence.
//   5. IdempotentReprocess         -- second tick processes 0 events.
//   6. StatementArchivedIsNoOp     -- statement.archived -> events_processed+=1, no frontier writes.
//   7. BatchSizeRespected          -- 5 events, batch_size=2 -> processes 2/2/1 in 3 ticks.

#include "starling/tom/belief_tracker.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/connection.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

namespace starling::tom::belief_tracker {
namespace {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;
using starling::persistence::TransactionGuard;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

int count_rows(Connection& conn, const std::string& sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr));
    StmtHandle h(raw);
    EXPECT_EQ(SQLITE_ROW, sqlite3_step(h.get()));
    return sqlite3_column_int(h.get(), 0);
}

int get_checkpoint(Connection& conn) {
    const char* sql =
        "SELECT last_processed_outbox_sequence "
        "FROM tom_belief_tracker_checkpoint WHERE id = 1";
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    if (sqlite3_step(h.get()) == SQLITE_ROW) {
        return sqlite3_column_int(h.get(), 0);
    }
    return -1;
}

// Insert an engram row (bypasses EngramStore), returns outbox_sequence after appending
// an evidence.appended bus event.
void insert_engram(Connection& conn, const std::string& engram_id,
                   const std::string& tenant_id, const std::string& adapter_name) {
    const char* sql =
        "INSERT INTO engrams("
        "id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode, "
        "privacy_class, retention_mode, refcount, created_at, "
        "adapter_name, adapter_version, source_item_id, source_version, chunk_index, "
        "declared_transformations_json, byte_preserving, audit_trail_json"
        ") VALUES (?,?,?,?,?,?,?,?,0,?,?,?,?,?,0,'[]',0,'[]')";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    auto bs = [&](int i, const std::string& v) {
        sqlite3_bind_text(h.get(), i, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    bs(1, engram_id);
    bs(2, tenant_id);
    bs(3, "deadbeef");               // content_hash
    bs(4, "user_provided");          // source_kind
    bs(5, "allowed");                // ingest_policy
    bs(6, "standard");               // ingest_mode
    bs(7, "public");                 // privacy_class
    bs(8, "keep");                   // retention_mode
    bs(9, "2026-05-26T00:00:00Z");   // created_at
    bs(10, adapter_name);
    bs(11, "1.0.0");                 // adapter_version
    bs(12, "item-1");                // source_item_id
    bs(13, "v1");                    // source_version
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
}

// Insert a minimal statement row (bypasses StatementWriter).
void insert_statement_row(Connection& conn,
                          const std::string& stmt_id,
                          const std::string& tenant_id,
                          const std::string& holder_id,
                          const std::string& engram_id,
                          const std::string& perceived_by_json = "[\"cog-alice\"]") {
    const char* sql =
        "INSERT INTO statements("
        "id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,"
        "polarity,confidence,observed_at,salience,affect_json,activation,"
        "last_accessed,provenance,consolidation_state,review_status,"
        "perceived_by_json,"
        "created_at,updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    int i = 1;
    auto bs = [&](const std::string& v) {
        sqlite3_bind_text(h.get(), i++, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    auto bd = [&](double v) { sqlite3_bind_double(h.get(), i++, v); };
    bs(stmt_id);
    bs(tenant_id);
    bs(holder_id);
    bs("first_person");
    bs("entity");
    bs("subj-1");
    bs("knows");
    bs("str");
    bs("val");
    bs("aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222");
    bs("v1");
    bs("believes");
    bs("pos");
    bd(0.8);
    bs("2026-01-01T00:00:00Z");   // observed_at
    bd(0.5);
    bs("{}");
    bd(1.0);
    bs("2026-01-01T00:00:00Z");   // last_accessed
    bs("user_input");
    bs("consolidated");
    bs("approved");
    bs(perceived_by_json);
    bs("2026-01-01T00:00:00Z");   // created_at
    bs("2026-01-01T00:00:00Z");   // updated_at
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
    (void)engram_id;  // engram_id used to cross-reference; not stored in statements row here
}

// Append a bus event via OutboxWriter (inside a transaction).
void append_bus_event(Connection& conn,
                      const std::string& event_type,
                      const std::string& primary_id,
                      const std::string& tenant_id,
                      const std::string& payload_json,
                      const std::string& ikey) {
    TransactionGuard tx(conn);
    OutboxWriter ow(conn);
    BusEvent ev;
    ev.tenant_id      = tenant_id;
    ev.event_type     = event_type;
    ev.primary_id     = primary_id;
    ev.aggregate_id   = primary_id;
    ev.idempotency_key = ikey;
    ev.payload_json   = payload_json;
    ow.append(ev);
    tx.commit();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

TEST(BeliefTracker, EmptyOutboxIsNoop) {
    auto adapter = open_fresh();
    auto stats = tick_one_batch(*adapter);
    EXPECT_EQ(stats.events_processed, 0);
    EXPECT_EQ(stats.frontier_facts_written, 0);
    EXPECT_EQ(get_checkpoint(adapter->connection()), 0);
}

TEST(BeliefTracker, StatementWrittenWritesFrontierFacts) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    // Insert supporting data.
    insert_statement_row(conn, "stmt-1", "default", "holder-1", "engram-1");

    // Insert statement.written bus event with correct payload.
    const std::string payload =
        "{\"stmt_id\":\"stmt-1\","
        "\"tenant_id\":\"default\","
        "\"holder_id\":\"holder-1\","
        "\"holder_perspective\":\"first_person\","
        "\"predicate\":\"knows\","
        "\"canonical_object_hash\":\"aaaa\","
        "\"consolidation_state\":\"volatile\","
        "\"review_status\":\"approved\","
        "\"extraction_span_key\":\"span-1\","
        "\"engram_ref_id\":\"engram-1\"}";
    append_bus_event(conn, "statement.written", "stmt-1", "default", payload, "ikey-sw-1");

    auto stats = tick_one_batch(*adapter);
    EXPECT_EQ(stats.events_processed, 1);
    EXPECT_GE(stats.frontier_facts_written, 1);
}

TEST(BeliefTracker, EvidenceAppendedRecordsAccessibleSource) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    // Insert engram row.
    insert_engram(conn, "engram-2", "default", "test_adapter");

    // Insert evidence.appended bus event.
    const std::string payload =
        "{\"engram_id\":\"engram-2\","
        "\"content_hash\":\"deadbeef\","
        "\"retention_mode\":\"keep\","
        "\"source_kind\":\"user_provided\","
        "\"tenant_id\":\"default\"}";
    append_bus_event(conn, "evidence.appended", "engram-2", "default", payload, "ikey-ea-1");

    auto stats = tick_one_batch(*adapter);
    EXPECT_EQ(stats.events_processed, 1);

    // Verify accessible_source frontier fact was created.
    int n = count_rows(conn,
        "SELECT COUNT(*) FROM cognizer_frontier_facts "
        "WHERE fact_kind='accessible_source'");
    EXPECT_GE(n, 1);
}

TEST(BeliefTracker, CheckpointAdvances) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    EXPECT_EQ(get_checkpoint(conn), 0);

    // Insert two events.
    append_bus_event(conn, "statement.archived", "stmt-x", "default",
                     "{\"reason\":\"test\"}", "ikey-sa-1");
    append_bus_event(conn, "statement.archived", "stmt-y", "default",
                     "{\"reason\":\"test\"}", "ikey-sa-2");

    // Get the last outbox_sequence inserted.
    int max_seq = 0;
    {
        sqlite3_stmt* raw = nullptr;
        ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(),
            "SELECT MAX(outbox_sequence) FROM bus_events", -1, &raw, nullptr));
        StmtHandle h(raw);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            max_seq = sqlite3_column_int(h.get(), 0);
        }
    }
    EXPECT_GT(max_seq, 0);

    auto stats = tick_one_batch(*adapter);
    EXPECT_EQ(stats.events_processed, 2);
    EXPECT_EQ(get_checkpoint(conn), max_seq);
}

TEST(BeliefTracker, IdempotentReprocess) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    append_bus_event(conn, "statement.archived", "stmt-x", "default",
                     "{\"reason\":\"test\"}", "ikey-idem-1");

    auto stats1 = tick_one_batch(*adapter);
    EXPECT_EQ(stats1.events_processed, 1);

    // Second tick: checkpoint is already past the event.
    auto stats2 = tick_one_batch(*adapter);
    EXPECT_EQ(stats2.events_processed, 0);
}

TEST(BeliefTracker, StatementArchivedIsNoOp) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    append_bus_event(conn, "statement.archived", "stmt-z", "default",
                     "{\"reason\":\"superseding\"}", "ikey-archived-1");

    auto stats = tick_one_batch(*adapter);
    EXPECT_EQ(stats.events_processed, 1);
    EXPECT_EQ(stats.frontier_facts_written, 0);
    EXPECT_EQ(stats.presence_log_writes, 0);

    // No frontier facts should be written.
    EXPECT_EQ(count_rows(conn, "SELECT COUNT(*) FROM cognizer_frontier_facts"), 0);
}

TEST(BeliefTracker, BatchSizeRespected) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    // Insert 5 statement.archived events.
    for (int k = 0; k < 5; k++) {
        append_bus_event(conn, "statement.archived",
                         "stmt-b" + std::to_string(k), "default",
                         "{\"reason\":\"test\"}",
                         "ikey-batch-" + std::to_string(k));
    }

    // First tick: batch_size=2 -> processes 2.
    auto s1 = tick_one_batch(*adapter, /*batch_size=*/2);
    EXPECT_EQ(s1.events_processed, 2);

    // Second tick: processes next 2.
    auto s2 = tick_one_batch(*adapter, /*batch_size=*/2);
    EXPECT_EQ(s2.events_processed, 2);

    // Third tick: processes last 1.
    auto s3 = tick_one_batch(*adapter, /*batch_size=*/2);
    EXPECT_EQ(s3.events_processed, 1);

    // Fourth tick: nothing left.
    auto s4 = tick_one_batch(*adapter, /*batch_size=*/2);
    EXPECT_EQ(s4.events_processed, 0);
}

}  // namespace
}  // namespace starling::tom::belief_tracker
