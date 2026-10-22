// 契约 v3（形态 S）：source turn 载荷新增必填 audience / session_id / turn_index /
// provenance；v1/v2 旧载荷仍可解析，audience 保守回填为 {speaker}。
#include "starling/extractor/claim_contract.hpp"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

namespace starling::extractor {
namespace {
using Json = nlohmann::json;

Json v3_turn() {
    return {{"speaker", "alice"},
            {"text", "I saw Bob at the station."},
            {"audience", Json::array({"alice", "bob"})},
            {"session_id", "scene-7"},
            {"turn_index", 3},
            {"provenance", "source_time"},
            {"turn_id", nullptr},
            {"observed_at", "2026-05-26T10:00:00Z"}};
}
}  // namespace

TEST(ClaimContractV3, RoundTripsThroughPayloadAndUnits) {
    const auto payload = claim_source_turn_payload(Json::array({v3_turn()}).dump(), false);
    EXPECT_EQ(payload.rfind("@starling/source-turn-v3 ", 0), 0u);

    const auto units = Json::parse(claim_source_units(payload));
    ASSERT_EQ(units.size(), 1u);
    const auto& unit = units[0];
    EXPECT_EQ(unit["speaker"], "alice");
    EXPECT_EQ(unit["utterance"], "I saw Bob at the station.");
    EXPECT_EQ(unit["session_id"], "scene-7");
    EXPECT_EQ(unit["turn_index"], 3);
    EXPECT_EQ(unit["provenance"], "source_time");
    ASSERT_EQ(unit["audience"].size(), 2u);
    EXPECT_EQ(unit["audience"][0], "alice");
    EXPECT_EQ(unit["audience"][1], "bob");
}

TEST(ClaimContractV3, RejectsEmptyAudience) {
    auto turn = v3_turn();
    turn["audience"] = Json::array();
    EXPECT_THROW(claim_source_turn_payload(Json::array({turn}).dump(), false), std::runtime_error);
}

TEST(ClaimContractV3, NoAudienceTakesLegacyPath) {
    // 无 audience 的 turn 走 v1 路径：不产生 v3 前缀。（v1 校验只允许其六个字段，
    // 故这里同时去掉 v3 专有字段，构成真正的旧形状载荷。）
    auto turn = v3_turn();
    for (const char* key : {"audience", "provenance"}) turn.erase(key);
    const auto payload = claim_source_turn_payload(Json::array({turn}).dump(), false);
    EXPECT_EQ(payload.rfind("@starling/source-turn-v3 ", 0), std::string::npos);
    EXPECT_EQ(payload.rfind("@starling/source-turn-v1 ", 0), 0u);
}

TEST(ClaimContractV3, RejectsBlankAudienceEntry) {
    auto turn = v3_turn();
    turn["audience"] = Json::array({"alice", "   "});
    EXPECT_THROW(claim_source_turn_payload(Json::array({turn}).dump(), false), std::runtime_error);
}

TEST(ClaimContractV3, RejectsEmptySessionId) {
    auto turn = v3_turn();
    turn["session_id"] = "";
    EXPECT_THROW(claim_source_turn_payload(Json::array({turn}).dump(), false), std::runtime_error);
}

TEST(ClaimContractV3, RejectsNegativeTurnIndex) {
    auto turn = v3_turn();
    turn["turn_index"] = -1;
    EXPECT_THROW(claim_source_turn_payload(Json::array({turn}).dump(), false), std::runtime_error);
}

TEST(ClaimContractV3, RejectsUnknownProvenance) {
    auto turn = v3_turn();
    turn["provenance"] = "guessed";
    EXPECT_THROW(claim_source_turn_payload(Json::array({turn}).dump(), false), std::runtime_error);
}

TEST(ClaimContractV3, RejectsTruncatedTimestampWithoutTolerance) {
    auto turn = v3_turn();
    turn["observed_at"] = "not-a-time";
    EXPECT_THROW(claim_source_turn_payload(Json::array({turn}).dump(), false), std::runtime_error);
}

TEST(ClaimContractV3, LegacyV1PayloadStillParsesWithSpeakerAudience) {
    // v1 载荷（无 audience）：解析成功，audience 保守回填为 {speaker}。
    const std::string legacy =
        "@starling/source-turn-v1 {\"speaker\":\"carol\",\"session_id\":\"s1\",\"text\":\"hello\","
        "\"turn_id\":null,\"turn_index\":0,\"observed_at\":\"2026-05-26T10:00:00Z\"}";
    const auto units = Json::parse(claim_source_units(legacy));
    ASSERT_EQ(units.size(), 1u);
    ASSERT_EQ(units[0]["audience"].size(), 1u);
    EXPECT_EQ(units[0]["audience"][0], "carol");
}

TEST(ClaimContractV3, MixedBatchEmitsPerTurnPrefix) {
    auto legacy = v3_turn();
    for (const char* key : {"audience", "provenance"}) legacy.erase(key);
    legacy["speaker"] = "dave";
    const auto payload = claim_source_turn_payload(Json::array({v3_turn(), legacy}).dump(), false);
    const auto lines = std::count(payload.begin(), payload.end(), '\n');
    ASSERT_EQ(lines, 1);  // 两行
    EXPECT_EQ(payload.rfind("@starling/source-turn-v3 ", 0), 0u);
    EXPECT_NE(payload.find("\n@starling/source-turn-v1 "), std::string::npos);
}

TEST(ClaimContractV3, AudienceEntriesAreStoredTrimmed) {
    // 校验用 trim、存储用原值会让 " alice " 永远匹配不上在场记录 → 必须存 trim 后的值。
    auto turn = v3_turn();
    turn["audience"] = Json::array({" alice ", "bob\t"});
    const auto payload = claim_source_turn_payload(Json::array({turn}).dump(), false);
    const auto units = Json::parse(claim_source_units(payload));
    ASSERT_EQ(units.size(), 1u);
    ASSERT_EQ(units[0]["audience"].size(), 2u);
    EXPECT_EQ(units[0]["audience"][0], "alice");
    EXPECT_EQ(units[0]["audience"][1], "bob");
}

TEST(ClaimContractV3, RejectsSpeakerNotInAudience) {
    // 不做隐式补全：存储的 audience 必须与调用方声明一致，否则审计前提被破坏。
    auto turn = v3_turn();
    turn["speaker"] = "carol";
    turn["audience"] = Json::array({"alice", "bob"});
    EXPECT_THROW(claim_source_turn_payload(Json::array({turn}).dump(), false), std::runtime_error);
}

TEST(ClaimContractV3, DuplicateAudienceMembersCollapsed) {
    auto turn = v3_turn();
    turn["audience"] = Json::array({"alice", "alice", "bob"});
    const auto payload = claim_source_turn_payload(Json::array({turn}).dump(), false);
    const auto units = Json::parse(claim_source_units(payload));
    EXPECT_EQ(units[0]["audience"].size(), 2u);
}

}  // namespace starling::extractor
