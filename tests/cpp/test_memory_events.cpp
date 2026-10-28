// test_memory_events.cpp — events 表读侧(迁移 0038):next_seq 与 pending_events。
// 直接插行,不经写侧;零网络。写侧(remember_event / abandon_event)的用例随各自任务加入。

#include "starling/memory/memory_events.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/stmt.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <memory>
#include <string>
#include <string_view>

namespace starling::memoryops {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void insert_event(persistence::Connection& conn, std::string_view tenant, std::string_view key,
                  std::int64_t seq, std::string_view state, std::string_view interlocutor = "bob",
                  std::string_view failure_category = "") {
    persistence::Stmt s(conn.raw(),
        "INSERT INTO events(tenant_id,key,text,interlocutor,text_sha256,seq,state,"
        "failure_category) VALUES(?1,?2,?3,?4,'h',?5,?6,?7)");
    const std::string text = "text-" + std::string(key);
    s.bind(tenant, key, text, interlocutor, seq, state, failure_category);
    s.step_done();
}

}  // namespace

TEST(MemoryEvents, NextSeqIsMaxPlusOnePerTenant) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "a", 0, "committed");
    insert_event(conn, "default", "b", 1, "pending");
    insert_event(conn, "other", "c", 0, "committed");

    EXPECT_EQ(next_seq(conn, "default"), 2);
    EXPECT_EQ(next_seq(conn, "other"), 1);
    EXPECT_EQ(next_seq(conn, "none"), 0);
}

TEST(MemoryEvents, NextSeqCountsAbandonedRowsSoNumbersAreNeverReused) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "a", 0, "committed");
    insert_event(conn, "default", "b", 1, "abandoned");

    EXPECT_EQ(next_seq(conn, "default"), 2);
}

TEST(MemoryEvents, NextSeqOnEmptyLibraryIsZero) {
    auto adapter = make_adapter();
    EXPECT_EQ(next_seq(adapter->connection(), "default"), 0);
}

TEST(MemoryEvents, PendingEventsOrderedBySeqOnlyPending) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "late", 5, "pending", "carol", "timeout");
    insert_event(conn, "default", "done", 2, "committed");
    insert_event(conn, "default", "gone", 3, "abandoned");
    insert_event(conn, "default", "early", 1, "pending");
    insert_event(conn, "other", "foreign", 0, "pending");

    const auto rows = pending_events(conn, "default");
    ASSERT_EQ(rows.size(), 2U);
    EXPECT_EQ(rows[0].key, "early");
    EXPECT_EQ(rows[0].text, "text-early");
    EXPECT_EQ(rows[0].interlocutor, "bob");
    EXPECT_EQ(rows[0].seq, 1);
    EXPECT_EQ(rows[0].failure_category, "");
    EXPECT_EQ(rows[1].key, "late");
    EXPECT_EQ(rows[1].interlocutor, "carol");
    EXPECT_EQ(rows[1].seq, 5);
    EXPECT_EQ(rows[1].failure_category, "timeout");
}

TEST(MemoryEvents, PendingEventsEmptyForUnknownTenant) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "a", 0, "pending");

    EXPECT_TRUE(pending_events(conn, "none").empty());
}

}  // namespace starling::memoryops
