// 形态 S 写入路径（Task 4）：按 (session_id, 展开后的 audience) 分组、
// 组名写入时展开、单事务原子、确定性顺序保幂等。
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/retrieval/source_retriever.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <sqlite3.h>

namespace starling::retrieval {
namespace {
using Json = nlohmann::json;
constexpr auto tenant = "tenant";
constexpr auto at = "2026-01-01T00:00:00Z";

std::unique_ptr<persistence::SqliteAdapter> adapter() {
    return persistence::SqliteAdapter::open(":memory:");
}
long count(persistence::SqliteAdapter& db, const char* sql) {
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db.connection().raw(), sql, -1, &stmt, nullptr);
    sqlite3_step(stmt);
    const long n = sqlite3_column_int64(stmt, 0);
    sqlite3_finalize(stmt);
    return n;
}
Json turn(const char* speaker, const char* text, const char* session, int index,
          std::vector<std::string> audience, const char* observed = "2026-01-01T00:00:00Z") {
    return {{"speaker", speaker}, {"text", text}, {"session_id", session},
            {"turn_index", index}, {"audience", audience}, {"provenance", "source_time"},
            {"turn_id", nullptr}, {"observed_at", observed}};
}
}  // namespace

TEST(SourceTurnsWrite, SplitsEngramsByAudienceWithinOneScene) {
    auto db = adapter();
    // 同一场景、同一说话人、两组听众 → 必须拆成两个 engram。
    const auto payload = Json::array({
        turn("alice", "the code is 4321", "s1", 0, {"alice", "bob"}),
        turn("alice", "meet me at noon", "s1", 1, {"alice", "carol"}),
    });
    const auto out = Json::parse(retain_source_turns(*db, tenant, {"alice", "bob", "carol"},
                                                     payload.dump(), at));
    EXPECT_EQ(out["documents"], 2);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_meta"), 2);
}

TEST(SourceTurnsWrite, DoesNotMergeAcrossScenes) {
    auto db = adapter();
    const auto payload = Json::array({
        turn("alice", "first", "s1", 0, {"alice"}),
        turn("alice", "second", "s2", 0, {"alice"}),
    });
    const auto out = Json::parse(retain_source_turns(*db, tenant, {"alice"}, payload.dump(), at));
    EXPECT_EQ(out["documents"], 2);
}

TEST(SourceTurnsWrite, RegistersOneSourceDocumentPerAudienceMember) {
    auto db = adapter();
    const auto payload = Json::array({turn("alice", "hello all", "s1", 0, {"alice", "bob"})});
    const auto out = Json::parse(retain_source_turns(*db, tenant, {"alice", "bob"}, payload.dump(), at));
    EXPECT_EQ(out["audience_rows"], 2);
    EXPECT_EQ(count(*db, "SELECT COUNT(DISTINCT holder_id) FROM source_documents"), 2);
}

TEST(SourceTurnsWrite, RecordsPresenceForEveryAudienceMember) {
    auto db = adapter();
    const auto payload = Json::array({turn("alice", "hello all", "s1", 0, {"alice", "bob"})});
    retain_source_turns(*db, tenant, {"alice", "bob"}, payload.dump(), at);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM cognizer_presence_log"), 2);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM cognizer_presence_log WHERE cognizer_id='bob'"), 1);
}

TEST(SourceTurnsWrite, EnqueuesOnePendingVectorPerUnit) {
    auto db = adapter();
    const auto payload = Json::array({turn("alice", "hello all", "s1", 0, {"alice"})});
    retain_source_turns(*db, tenant, {"alice"}, payload.dump(), at);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_vectors WHERE status='pending'"), 1);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_vectors WHERE dim IS NOT NULL"), 0);
}

TEST(SourceTurnsWrite, ExpandsGroupToMembersAtThatMoment) {
    auto db = adapter();
    cognizer::KnowledgeFrontier frontier(*db);
    frontier.record_group_membership(tenant, "bob", "team", "2025-12-01T00:00:00Z", db->connection());
    // carol 在写入时刻之后才入组，不该看到这条。
    frontier.record_group_membership(tenant, "carol", "team", "2026-06-01T00:00:00Z", db->connection());

    // 说话人 alice 显式在听众里；组名展开出 bob（在场者）与 carol（当时尚未入组）。
    const auto payload = Json::array({turn("alice", "team only", "s1", 0, {"alice", "group:team"})});
    retain_source_turns(*db, tenant, {"alice", "bob", "carol"}, payload.dump(), at);

    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM cognizer_presence_log WHERE cognizer_id='alice'"), 1);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM cognizer_presence_log WHERE cognizer_id='bob'"), 1);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM cognizer_presence_log WHERE cognizer_id='carol'"), 0);
}

TEST(SourceTurnsWrite, RejectsAudienceMemberOutsideAllowedHolders) {
    auto db = adapter();
    const auto payload = Json::array({turn("alice", "x", "s1", 0, {"alice", "mallory"})});
    EXPECT_THROW(retain_source_turns(*db, tenant, {"alice"}, payload.dump(), at), std::invalid_argument);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_meta"), 0);
}

TEST(SourceTurnsWrite, RejectsSpeakerNotInAudience) {
    auto db = adapter();
    // 契约层（claim_source_turn_payload）先于写入层拦截，抛 ContractError（runtime_error 子类）。
    const auto payload = Json::array({turn("alice", "x", "s1", 0, {"bob"})});
    EXPECT_THROW(retain_source_turns(*db, tenant, {"alice", "bob"}, payload.dump(), at), std::runtime_error);
}

TEST(SourceTurnsWrite, RejectsMixedBatchWithAndWithoutAudience) {
    auto db = adapter();
    const auto payload = Json::array({
        turn("alice", "with audience", "s1", 0, {"alice"}),
        Json{{"speaker", "alice"}, {"text", "legacy"}, {"session_id", "s1"},
             {"turn_index", 1}, {"observed_at", "2026-01-01T00:00:00Z"}},
    });
    EXPECT_THROW(retain_source_turns(*db, tenant, {"alice"}, payload.dump(), at), std::invalid_argument);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_meta"), 0);
}

TEST(SourceTurnsWrite, LegacyPathUnchangedWithoutAudience) {
    auto db = adapter();
    const auto payload = Json::array({{
        {"speaker", "alice"}, {"text", "legacy turn"}, {"session_id", "s1"},
        {"turn_index", 0}, {"observed_at", "2026-01-01T00:00:00Z"}}});
    const auto out = Json::parse(retain_source_turns(*db, tenant, {"alice"}, payload.dump(), at));
    EXPECT_EQ(out["documents"], 1);
    // 旧路径不写新表。
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_meta"), 0);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_vectors"), 0);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_documents"), 1);
}

TEST(SourceTurnsWrite, IdempotentOnRepeatedWrite) {
    auto db = adapter();
    const auto payload = Json::array({turn("alice", "hello all", "s1", 0, {"alice", "bob"})});
    const auto first = Json::parse(retain_source_turns(*db, tenant, {"alice", "bob"}, payload.dump(), at));
    const auto second = Json::parse(retain_source_turns(*db, tenant, {"alice", "bob"}, payload.dump(), at));
    EXPECT_EQ(first["engram_refs"], second["engram_refs"]);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM source_unit_meta"), 1);
    EXPECT_EQ(count(*db, "SELECT COUNT(*) FROM cognizer_presence_log"), 2);
}

TEST(SourceTurnsWrite, UnitMetaCarriesSceneTimeAndAudience) {
    auto db = adapter();
    const auto payload = Json::array({turn("alice", "hello all", "scene-9", 7, {"alice", "bob"},
                                          "2025-05-05T07:00:00Z")});
    retain_source_turns(*db, tenant, {"alice", "bob"}, payload.dump(), at);
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db->connection().raw(),
        "SELECT session_id, speaker, audience_json, turn_index, observed_at, provenance"
        " FROM source_unit_meta", -1, &stmt, nullptr);
    ASSERT_EQ(sqlite3_step(stmt), SQLITE_ROW);
    EXPECT_EQ(std::string(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0))), "scene-9");
    EXPECT_EQ(std::string(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1))), "alice");
    EXPECT_EQ(Json::parse(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2))),
              Json::array({"alice", "bob"}));
    EXPECT_EQ(sqlite3_column_int(stmt, 3), 7);
    EXPECT_EQ(std::string(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4))),
              "2025-05-05T07:00:00Z");
    EXPECT_EQ(std::string(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5))), "source_time");
    sqlite3_finalize(stmt);
}

}  // namespace starling::retrieval
