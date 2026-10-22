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

    // 迁移 0037 起：写入 cognizer_group_membership 表（带时间维度）。
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(adapter->connection().raw(),
        "SELECT group_id, joined_at FROM cognizer_group_membership "
        " WHERE tenant_id='default' AND cognizer_id='alice'",
        -1, &stmt, nullptr);
    ASSERT_EQ(sqlite3_step(stmt), SQLITE_ROW);
    std::string gid(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    std::string eff(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1)));
    sqlite3_finalize(stmt);
    EXPECT_EQ(gid, "eng-team");
    EXPECT_EQ(eff, "2026-05-26T10:00:00Z");
}

TEST(KnowledgeFrontierRecord, GroupMembershipIdempotent) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    // 同一 (tenant, group, cognizer, joined_at) 重复写入应幂等（ON CONFLICT DO NOTHING）。
    frontier.record_group_membership("default", "alice", "eng-team", "2026-05-26T10:00:00Z",
                                      adapter->connection());
    frontier.record_group_membership("default", "alice", "eng-team", "2026-05-26T10:00:00Z",
                                      adapter->connection());
    const auto cnt = count_table(adapter->connection().raw(),
        "SELECT COUNT(*) FROM cognizer_group_membership "
        " WHERE tenant_id='default' AND cognizer_id='alice' AND group_id='eng-team'");
    EXPECT_EQ(cnt, 1);  // 只有一行，非两行
}

TEST(KnowledgeFrontierRecord, GetGroupMembersAt) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    // alice 在 T1 加入 eng-team，T2 加入 design-team。
    frontier.record_group_membership("default", "alice", "eng-team",    "2026-05-26T10:00:00Z",
                                      adapter->connection());
    frontier.record_group_membership("default", "alice", "design-team", "2026-05-27T12:00:00Z",
                                      adapter->connection());
    // bob 在 T1 加入 eng-team。
    frontier.record_group_membership("default", "bob", "eng-team", "2026-05-26T10:00:00Z",
                                      adapter->connection());

    // as-of 查询：alice 在 T1 之前无组，T1 后只有 eng-team，T2 后有两个。
    auto before = frontier.get_group_members_at("default", "alice", "2026-05-26T09:00:00Z");
    EXPECT_EQ(before.size(), 0);

    auto t1 = frontier.get_group_members_at("default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_EQ(t1.size(), 1);
    EXPECT_EQ(t1.count("eng-team"), 1);

    auto t2 = frontier.get_group_members_at("default", "alice", "2026-05-27T12:00:00Z");
    EXPECT_EQ(t2.size(), 2);
    EXPECT_EQ(t2.count("eng-team"), 1);
    EXPECT_EQ(t2.count("design-team"), 1);

    // bob 只在 eng-team。
    auto bob_t2 = frontier.get_group_members_at("default", "bob", "2026-05-27T12:00:00Z");
    EXPECT_EQ(bob_t2.size(), 1);
    EXPECT_EQ(bob_t2.count("eng-team"), 1);
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
