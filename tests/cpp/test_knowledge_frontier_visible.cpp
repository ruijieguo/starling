#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

using starling::cognizer::KnowledgeFrontier;
using starling::persistence::SqliteAdapter;

TEST(KnowledgeFrontierVisible, EmptyWhenNothingRecorded) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v.empty());
}

TEST(KnowledgeFrontierVisible, PresenceLogContributes) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-A",
        "2026-05-26T09:00:00Z", adapter->connection());
    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_EQ(v.size(), 1u);
    EXPECT_TRUE(v.count("engram-A"));
}

TEST(KnowledgeFrontierVisible, FiveWayUnionExcept) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    auto& conn = adapter->connection();

    // 1: presence_log
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-presence",
        "2026-05-26T09:00:00Z", conn);
    // 2: explicit_told
    frontier.record_explicit_told(
        "default", {"alice"}, "stmt-told", "engram-told",
        "2026-05-26T09:00:00Z", conn);
    // 3: accessible_source
    frontier.record_accessible_source(
        "default", "alice", "slack_adapter", "engram-source",
        "2026-05-26T09:00:00Z", conn);
    // 4: membership doesn't carry source_engram_id (it's group-level, not
    //    engram-level) — skip for engram visibility tests; metadata records
    //    membership itself.

    // 5: explicit_not_told blocks engram-source-blocked
    frontier.record_explicit_told(
        "default", {"alice"}, "stmt-blocked", "engram-source-blocked",
        "2026-05-26T09:00:00Z", conn);
    frontier.record_explicit_negation(
        "default", "alice", "stmt-blocked", "engram-source-blocked",
        "2026-05-26T09:30:00Z", conn);

    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v.count("engram-presence"));
    EXPECT_TRUE(v.count("engram-told"));
    EXPECT_TRUE(v.count("engram-source"));
    EXPECT_FALSE(v.count("engram-source-blocked")) << "explicit_not_told must subtract";
}

TEST(KnowledgeFrontierVisible, AsOfFiltersOutLaterRecords) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-late",
        "2026-05-26T15:00:00Z", adapter->connection());
    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v.empty());
}

TEST(KnowledgeFrontierVisible, TenantIsolation) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "tenant-a", {"alice"}, "engram-1",
        "2026-05-26T09:00:00Z", adapter->connection());
    auto v_b = frontier.visible_engrams_at(
        "tenant-b", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v_b.empty()) << "cross-tenant must isolate";
}
