#include <gtest/gtest.h>

#include "starling/bus/outbox_dispatcher.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <string>

using starling::bus::BusEvent;
using starling::bus::Consumer;
using starling::bus::ConsumerDecision;
using starling::bus::DispatchOptions;
using starling::bus::OutboxDispatcher;
using starling::bus::OutboxWriter;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::TransactionGuard;

namespace {

Connection fresh() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

// Small wrapper so test code can run a no-arg SQL statement without naming
// Connection's method directly. Routed through the same Connection API as
// production code.
void run_sql(Connection& c, const char* sql) {
    c.exec(sql);
}

// Field order matches BusEvent's declaration in bus_event.hpp:
// tenant_id, event_type, primary_id, aggregate_id, idempotency_key,
// payload_json. event_id / outbox_sequence / created_at are filled in by
// OutboxWriter::append.
void seed(Connection& c, const std::string& aggregate, const std::string& key) {
    OutboxWriter w(c);
    BusEvent ev{
        .tenant_id = "t1",
        .event_type = "statement.created",
        .primary_id = "stmt-" + key,
        .aggregate_id = aggregate,
        .idempotency_key = key,
        .payload_json = "{}",
    };
    TransactionGuard g(c);
    w.append(ev);
    g.commit();
}

int count(Connection& c, const char* sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(c.raw(), sql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(c.raw());
    starling::persistence::StmtHandle s(raw);
    EXPECT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    return sqlite3_column_int(s.get(), 0);
}

}  // namespace

TEST(OutboxDispatcher, AcceptingConsumerDeliversAll) {
    auto c = fresh();
    seed(c, "h1", "k1");
    seed(c, "h1", "k2");
    seed(c, "h2", "k3");
    OutboxDispatcher d(c, [](const BusEvent&) { return ConsumerDecision::Accept; });
    auto stats = d.run_once();
    EXPECT_EQ(stats.delivered, 3);
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='delivered'"), 3);
}

TEST(OutboxDispatcher, PerAggregateOrderingHonoredOnRetry) {
    auto c = fresh();
    seed(c, "h1", "k1");  // will fail
    seed(c, "h1", "k2");  // must NOT deliver while k1 still pending
    seed(c, "h2", "k3");  // independent aggregate, should deliver
    int calls = 0;
    OutboxDispatcher d(c, [&](const BusEvent& ev) {
        ++calls;
        if (ev.idempotency_key == "k1") return ConsumerDecision::TransientError;
        return ConsumerDecision::Accept;
    });
    auto stats = d.run_once();
    EXPECT_EQ(stats.delivered, 1);             // only k3
    EXPECT_EQ(stats.retried, 1);                // k1
    EXPECT_EQ(stats.skipped_blocked, 1);        // k2 blocked by k1
}

TEST(OutboxDispatcher, DeadLetterAfterMaxRetries) {
    auto c = fresh();
    seed(c, "h1", "k1");
    OutboxDispatcher d(c, [](const BusEvent&) { return ConsumerDecision::TransientError; },
                      DispatchOptions{.max_retries = 3});
    int total_attempts = 0;
    for (int i = 0; i < 4; ++i) {
        auto s = d.run_once();
        total_attempts += s.retried + s.dead_lettered;
    }
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='dead_letter'"), 1);
    // system.delivery_failed appended with dispatch_status='delivered' (recursion guard)
    EXPECT_EQ(count(c,
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='system.delivery_failed' AND dispatch_status='delivered'"), 1);
}

TEST(OutboxDispatcher, IdempotencyInboxDedupsOnRedelivery) {
    auto c = fresh();
    seed(c, "h1", "k1");
    int delivered_count = 0;
    Consumer once = [&](const BusEvent&) {
        ++delivered_count;
        return ConsumerDecision::Accept;
    };
    OutboxDispatcher(c, once).run_once();
    // Simulate a forced redeliver by flipping the row back to pending.
    run_sql(c, "UPDATE bus_events SET dispatch_status='pending' WHERE idempotency_key='k1'");
    OutboxDispatcher(c, once).run_once();
    // The dispatcher does not dedup at delivery time; it just delivers. The
    // consumer is responsible for checking the inbox before doing side effects.
    // So: (a) consumer was called twice, and (b) inbox row stays at count=1
    // because INSERT OR IGNORE is idempotent on (consumer, idempotency_key).
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(c.raw(),
        "SELECT COUNT(*) FROM idempotency_inbox WHERE idempotency_key='k1'",
        -1, &raw, nullptr), SQLITE_OK);
    starling::persistence::StmtHandle s(raw);
    ASSERT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(s.get(), 0), 1);
    EXPECT_EQ(delivered_count, 2);
}

TEST(OutboxDispatcher, CrashRecoveryResetsInFlight) {
    auto c = fresh();
    seed(c, "h1", "k1");
    // Simulate crash mid-deliver: row stuck in_flight before consumer outcome.
    run_sql(c, "UPDATE bus_events SET dispatch_status='in_flight' WHERE idempotency_key='k1'");
    OutboxDispatcher d(c, [](const BusEvent&) { return ConsumerDecision::Accept; });
    auto stats = d.run_once();
    EXPECT_EQ(stats.delivered, 1);
}
