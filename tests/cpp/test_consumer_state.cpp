#include <gtest/gtest.h>
#include "starling/bus/consumer_state.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

using starling::bus::ConsumerCheckpoint;
using starling::bus::IdempotencyInbox;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;

namespace {
Connection fresh() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}
}

TEST(ConsumerCheckpoint, DefaultsToZero) {
    auto c = fresh();
    EXPECT_EQ(ConsumerCheckpoint(c).last_delivered("c1"), 0);
}

TEST(ConsumerCheckpoint, AdvanceMonotonic) {
    auto c = fresh();
    ConsumerCheckpoint cp(c);
    cp.advance("c1", 5);
    cp.advance("c1", 3);  // attempted regression
    EXPECT_EQ(cp.last_delivered("c1"), 5);
    cp.advance("c1", 10);
    EXPECT_EQ(cp.last_delivered("c1"), 10);
}

TEST(IdempotencyInbox, RecordIfNewDedups) {
    auto c = fresh();
    IdempotencyInbox inbox(c);
    const auto now = std::chrono::system_clock::now();
    EXPECT_TRUE (inbox.record_if_new("c1", "k1", now, std::chrono::hours(24*7)));
    EXPECT_FALSE(inbox.record_if_new("c1", "k1", now, std::chrono::hours(24*7)));
    EXPECT_TRUE (inbox.record_if_new("c2", "k1", now, std::chrono::hours(24*7)));
}

TEST(IdempotencyInbox, PurgeExpiredRemovesOldRows) {
    auto c = fresh();
    IdempotencyInbox inbox(c);
    const auto t0 = std::chrono::system_clock::now();
    inbox.record_if_new("c1", "old", t0, std::chrono::hours(1));
    inbox.record_if_new("c1", "new", t0, std::chrono::hours(48));
    const auto later = t0 + std::chrono::hours(2);
    EXPECT_EQ(inbox.purge_expired(later), 1);
    // 'new' still present -> record_if_new returns false
    EXPECT_FALSE(inbox.record_if_new("c1", "new", later, std::chrono::hours(48)));
}
