#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

using starling::cognizer::KnowledgeFrontier;
using starling::persistence::SqliteAdapter;

namespace {

int count_table(sqlite3* db, const std::string& sql) {
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr);
    sqlite3_step(stmt);
    int n = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return n;
}

}  // namespace

TEST(KnowledgeFrontierRecord, PresenceLogWritesOnePerCognizer) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice", "bob"}, "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());

    auto& conn = adapter->connection();
    EXPECT_EQ(count_table(conn.raw(),
        "SELECT COUNT(*) FROM cognizer_presence_log WHERE engram_id='engram-1'"), 2);
}

TEST(KnowledgeFrontierRecord, PresenceLogIdempotent) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    EXPECT_EQ(count_table(adapter->connection().raw(),
        "SELECT COUNT(*) FROM cognizer_presence_log WHERE cognizer_id='alice'"), 1);
}

TEST(KnowledgeFrontierRecord, ExplicitToldWritesFrontierFact) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_explicit_told(
        "default", {"alice"}, "stmt-1", "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    EXPECT_EQ(count_table(adapter->connection().raw(),
        "SELECT COUNT(*) FROM cognizer_frontier_facts "
        "WHERE fact_kind='explicit_told' AND cognizer_id='alice'"), 1);
}

TEST(KnowledgeFrontierRecord, AccessibleSourceCarriesAdapterName) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_accessible_source(
        "default", "alice", "slack_adapter", "engram-2",
        "2026-05-26T10:00:00Z", adapter->connection());

    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(adapter->connection().raw(),
        "SELECT metadata_json FROM cognizer_frontier_facts "
        " WHERE fact_kind='accessible_source' AND cognizer_id='alice'",
        -1, &stmt, nullptr);
    sqlite3_step(stmt);
    std::string m(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    sqlite3_finalize(stmt);
    EXPECT_NE(m.find("slack_adapter"), std::string::npos);
}

TEST(KnowledgeFrontierRecord, GroupMembershipWritesGroupId) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_group_membership(
        "default", "alice", "eng-team",
        "2026-05-26T10:00:00Z", adapter->connection());

    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(adapter->connection().raw(),
        "SELECT metadata_json FROM cognizer_frontier_facts "
        " WHERE fact_kind='membership' AND cognizer_id='alice'",
        -1, &stmt, nullptr);
    sqlite3_step(stmt);
    std::string m(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    sqlite3_finalize(stmt);
    EXPECT_NE(m.find("eng-team"), std::string::npos);
}

TEST(KnowledgeFrontierRecord, ExplicitNegationWritesNotTold) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_explicit_negation(
        "default", "alice", "stmt-X", "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    EXPECT_EQ(count_table(adapter->connection().raw(),
        "SELECT COUNT(*) FROM cognizer_frontier_facts "
        "WHERE fact_kind='explicit_not_told' AND cognizer_id='alice'"), 1);
}
