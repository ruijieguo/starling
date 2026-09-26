#include "starling/extractor/claim_contract.hpp"

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

namespace starling::extractor {
namespace {
using Json = nlohmann::json;

Json nested_row() {
    return {{"confidence", nullptr},
            {"evidence", {{"holder", "Mina"}, {"holder_perspective", "FIRST_PERSON"},
                           {"subject", "Mina"}, {"subject_kind", "cognizer"},
                           {"predicate", "feels"}, {"object", "sad about leaving the team"},
                           {"modality", "BELIEVES"}, {"polarity", "POS"},
                           {"nesting_depth", 0}, {"clause_id", "c0"}, {"actor", "Mina"},
                           {"attributed_to", nullptr}, {"assertion_scope", "ASSERTED"},
                           {"scope_markers", Json::array({"ASSERTED"})}, {"time_text", ""},
                           {"topic", "leaving the team"}, {"event_time", nullptr}}}};
}

std::string nested_response() {
    return Json{{"schema_version", 2}, {"statements", Json::array({nested_row()})}}.dump();
}
}  // namespace

TEST(StructuredOutputPrompt, EndsWithUnambiguousTopLevelFieldReminder) {
    const auto prompt = claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina");
    const auto source = prompt.find("SOURCE_DATA_JSON:");
    ASSERT_NE(source, std::string::npos);
    const auto reminder = prompt.find("FINAL FORMAT CHECK:", source);
    ASSERT_NE(reminder, std::string::npos);
    EXPECT_NE(prompt.find("TOP-LEVEL fields", reminder), std::string::npos);
    EXPECT_NE(prompt.find("Never put statement fields inside evidence", reminder), std::string::npos);
    EXPECT_NE(prompt.find("Never omit holder_perspective", reminder), std::string::npos);
    EXPECT_GT(reminder, source);
}

TEST(StructuredOutputPrompt, ReminderDoesNotRelaxNestedWireRejection) {
    const auto parsed = parse_claim_response(nested_response(),
        "Mina: I am sad about leaving the team.", "Mina");
    ASSERT_FALSE(parsed.errors.empty());
    EXPECT_EQ(parsed.errors.front().kind, "schema_failure");
    EXPECT_TRUE(parsed.statements.empty());
}

TEST(StructuredOutputPrompt, ReminderDisallowsDuplicateJsonKeys) {
    const auto prompt = claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina");
    const auto reminder = prompt.find("FINAL FORMAT CHECK:");
    ASSERT_NE(reminder, std::string::npos);
    EXPECT_NE(prompt.find("Each JSON key must appear exactly once", reminder),
              std::string::npos);
}

TEST(StructuredOutputPrompt, ReminderShowsPlaceholderBadAndGoodLayouts) {
    const auto prompt = claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina");
    const auto reminder = prompt.find("FINAL FORMAT CHECK:");
    ASSERT_NE(reminder, std::string::npos);
    const auto bad = prompt.find("BAD:", reminder);
    const auto good = prompt.find("GOOD:", reminder);
    ASSERT_NE(bad, std::string::npos);
    ASSERT_NE(good, std::string::npos);
    EXPECT_LT(bad, good);
    EXPECT_NE(prompt.find("statement={...}, evidence={...}", bad), std::string::npos);
    EXPECT_NE(prompt.find("statement={...}, evidence={clause_id,...}", good),
              std::string::npos);
    EXPECT_EQ(prompt.find("Mina", bad), std::string::npos);
    EXPECT_EQ(prompt.find("leaving the team", bad), std::string::npos);
}

TEST(StructuredOutputPrompt, ReminderHasNoBenchmarkSpecificContent) {
    const auto prompt = claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina");
    EXPECT_EQ(prompt.find("SocialMemBench"), std::string::npos);
    EXPECT_EQ(prompt.find("Q1_"), std::string::npos);
    EXPECT_EQ(prompt.find("answer"), std::string::npos);
}

TEST(StructuredOutputPrompt, R32ReminderProvidesSeparateCanonicalShapes) {
    const auto prompt = claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina");
    const auto reminder = prompt.find("FINAL FORMAT CHECK:");
    ASSERT_NE(reminder, std::string::npos);
    const auto suffix = prompt.substr(reminder);
    EXPECT_NE(suffix.find("STATEMENT TOP-LEVEL SHAPE"), std::string::npos);
    EXPECT_NE(suffix.find("EVIDENCE NESTED SHAPE"), std::string::npos);
    EXPECT_NE(suffix.find("CANONICAL SKELETON"), std::string::npos);
    EXPECT_LT(suffix.find("STATEMENT TOP-LEVEL SHAPE"),
              suffix.find("EVIDENCE NESTED SHAPE"));
    EXPECT_LT(suffix.find("EVIDENCE NESTED SHAPE"),
              suffix.find("CANONICAL SKELETON"));
}

TEST(StructuredOutputPrompt, R32ReminderEnumeratesOwnershipWithoutBusinessExamples) {
    const auto prompt = claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina");
    const auto reminder = prompt.find("FINAL FORMAT CHECK:");
    ASSERT_NE(reminder, std::string::npos);
    const auto suffix = prompt.substr(reminder);
    for (const auto* field : {"holder", "holder_perspective", "subject_kind",
                              "predicate", "object", "modality", "polarity",
                              "nesting_depth", "confidence"}) {
        EXPECT_NE(suffix.find(field), std::string::npos) << field;
    }
    for (const auto* field : {"clause_id", "actor", "attributed_to",
                              "assertion_scope", "scope_markers", "time_text",
                              "topic", "event_time"}) {
        EXPECT_NE(suffix.find(field), std::string::npos) << field;
    }
    EXPECT_NE(suffix.find("only"), std::string::npos);
    EXPECT_EQ(suffix.find("Mina"), std::string::npos);
    EXPECT_EQ(suffix.find("leaving the team"), std::string::npos);
    EXPECT_EQ(suffix.find("SocialMemBench"), std::string::npos);
}

TEST(StructuredOutputPrompt, R32ReminderShowsOneTimeKeySkeleton) {
    const auto prompt = claim_extraction_prompt(
        "Mina: I am sad about leaving the team.", "Mina");
    const auto reminder = prompt.find("FINAL FORMAT CHECK:");
    ASSERT_NE(reminder, std::string::npos);
    const auto suffix = prompt.substr(reminder);
    EXPECT_NE(suffix.find("Each object key appears exactly once"), std::string::npos);
    EXPECT_NE(suffix.find("event_time:null"), std::string::npos);
    EXPECT_NE(suffix.find("holder_perspective"), std::string::npos);
    EXPECT_NE(suffix.find("evidence"), std::string::npos);
}
}  // namespace starling::extractor
