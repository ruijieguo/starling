// Smoke tests for SubscriberPump::run_post_write.
// Verifies the pump can be invoked on a fresh in-memory DB without throwing and
// that repeated calls are idempotent. Full integration coverage lives in the
// P2.a/M0.8 pytest + ctest suites (belief_tracker, conflict_key_backfill, etc.).

#include "starling/bus/subscriber_pump.hpp"

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <string>

namespace starling::bus {
namespace {

using starling::persistence::SqliteAdapter;
using starling::persistence::Connection;

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

// 1. Run once on a fresh empty DB — must not throw.
TEST(SubscriberPump, RunPostWriteDoesNotThrow) {
    auto adapter = open_fresh();
    Connection& conn = adapter->connection();
    const std::string now_iso = "2026-05-29T12:00:00Z";
    EXPECT_NO_THROW(SubscriberPump::run_post_write(*adapter, conn, now_iso));
}

// 2. Run twice on an empty DB — must not throw either time (idempotent).
TEST(SubscriberPump, RunPostWriteIsIdempotentOnEmptyDB) {
    auto adapter = open_fresh();
    Connection& conn = adapter->connection();
    const std::string now_iso = "2026-05-29T12:00:00Z";
    EXPECT_NO_THROW(SubscriberPump::run_post_write(*adapter, conn, now_iso));
    EXPECT_NO_THROW(SubscriberPump::run_post_write(*adapter, conn, now_iso));
}

}  // namespace
}  // namespace starling::bus
