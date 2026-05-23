#include <gtest/gtest.h>

#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <string>

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::SqliteError;
using starling::persistence::TransactionGuard;

namespace {

Connection fresh_db() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

BusEvent make_event(const std::string& key) {
    return BusEvent{
        .tenant_id = "t1",
        .event_type = "statement.created",
        .primary_id = "stmt-1",
        .aggregate_id = "holder-1",
        .causation_chain = {},
        .idempotency_key = key,
        .payload_json = "{}",
    };
}

int count_rows(Connection& c, const char* sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(c.raw(), sql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(c.raw());
    starling::persistence::StmtHandle s(raw);
    EXPECT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    return sqlite3_column_int(s.get(), 0);
}

}  // namespace

TEST(OutboxWriter, AppendsAssignsSequenceAndPersists) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto ev = make_event("k1");
    {
        TransactionGuard g(c);
        w.append(ev);
        g.commit();
    }
    EXPECT_GT(ev.outbox_sequence, 0);
    EXPECT_FALSE(ev.event_id.empty());
    EXPECT_FALSE(ev.created_at.empty());
    EXPECT_EQ(
        count_rows(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='pending'"),
        1);
}

TEST(OutboxWriter, SequenceMonotonicAcrossAppends) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("k1");
    auto b = make_event("k2");
    {
        TransactionGuard g(c);
        w.append(a);
        w.append(b);
        g.commit();
    }
    EXPECT_EQ(b.outbox_sequence, a.outbox_sequence + 1);
}

TEST(OutboxWriter, RollbackDoesNotLeaveSequenceGaps) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("k1");
    {
        TransactionGuard g(c);
        w.append(a);
        // implicit rollback — guard's destructor calls Connection::rollback().
    }
    auto b = make_event("k2");
    {
        TransactionGuard g(c);
        w.append(b);
        g.commit();
    }
    // The rolled-back transaction's UPDATE on outbox_sequence_counter is also
    // rolled back, so b reuses a's would-be sequence. No gap.
    EXPECT_EQ(b.outbox_sequence, a.outbox_sequence);
    // And only b survived.
    EXPECT_EQ(count_rows(c, "SELECT COUNT(*) FROM bus_events"), 1);
}

TEST(OutboxWriter, RejectsDuplicateIdempotencyKey) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("dup");
    auto b = make_event("dup");
    {
        TransactionGuard g(c);
        w.append(a);
        EXPECT_THROW(w.append(b), SqliteError);
        // Guard rolls back on destruction (commit() not called).
    }
    EXPECT_EQ(count_rows(c, "SELECT COUNT(*) FROM bus_events"), 0);
}

TEST(OutboxWriter, AppendAlreadyDeliveredFlagSet) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("k1");
    {
        TransactionGuard g(c);
        w.append_already_delivered(a);
        g.commit();
    }
    EXPECT_EQ(
        count_rows(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='delivered'"),
        1);
}
