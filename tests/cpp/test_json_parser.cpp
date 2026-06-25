#include <gtest/gtest.h>

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/json_parser.hpp"

#include <string>

namespace starling::extractor {

TEST(JsonParser, ParsesSemanticCoreAndFillsBookkeeping) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",)"
        R"("predicate":"responsible_for","object":"auth","modality":"BELIEVES",)"
        R"("polarity":"POS","nesting_depth":0}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    const auto& s = r.statements[0];
    EXPECT_EQ(s.subject_kind, "cognizer");
    EXPECT_EQ(s.subject_id, "Bob");
    EXPECT_EQ(s.predicate, "responsible_for");
    EXPECT_EQ(s.object_kind, "str");
    EXPECT_FALSE(s.canonical_object_hash.empty());
    EXPECT_EQ(s.holder_perspective, schema::Perspective::FIRST_PERSON);
    EXPECT_EQ(s.modality, schema::Modality::BELIEVES);
    EXPECT_EQ(s.polarity, schema::Polarity::POS);
    EXPECT_DOUBLE_EQ(s.confidence, 0.7);
    EXPECT_FALSE(s.observed_at.empty());
}

TEST(JsonParser, NestedBeliefStaysTextObjectKind) {
    // Regression(原行为反转): depth>=2 曾映射 object_kind="statement",但
    // NestingDepthWriter 要求该 kind 的 object_value 是已存在语句 UUID——LLM
    // 给的是自由文本,导致任何二阶嵌套抽取整 run 抛
    // "parent statement not found"(dashboard remember 500)。抽取路径一律
    // "str";"statement" kind 留给程序化 ToM 写入。
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","holder_perspective":"INFERRED","subject":"Alice",)"
        R"("predicate":"thinks","object":"Bob trusts Carol","modality":"BELIEVES",)"
        R"("polarity":"POS","nesting_depth":2}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].object_kind, "str");
}

TEST(JsonParser, StripsCodeFence) {
    ExistingRefMap refs;
    const std::string raw =
        "```json\n[{\"holder\":\"self\",\"holder_perspective\":\"INFERRED\","
        "\"subject\":\"X\",\"predicate\":\"knows\",\"object\":\"y\","
        "\"modality\":\"KNOWS\",\"polarity\":\"POS\",\"nesting_depth\":0}]\n```";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    EXPECT_EQ(r.statements.size(), 1u);
}

TEST(JsonParser, NonArrayProducesError) {
    ExistingRefMap refs;
    ParseResult r = parse_extractor_json("not json at all", refs);
    EXPECT_FALSE(r.errors.empty());
    EXPECT_TRUE(r.statements.empty());
}

TEST(JsonParser, HonorsOptionalConfidence) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","holder_perspective":"INFERRED","subject":"Bob",)"
        R"("predicate":"p","object":"o","modality":"BELIEVES","polarity":"POS",)"
        R"("confidence":0.42,"nesting_depth":0}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_DOUBLE_EQ(r.statements[0].confidence, 0.42);
}

TEST(JsonParser, CarriesLlmHolderAndNestingDepthAdvisoryFields) {
    // The LLM emits a `holder` field (the narrated attitude bearer) and a
    // `nesting_depth`. The legacy semantic fields are unchanged (subject stays
    // the claim subject; holder_id is NOT set by the parser). These two advisory
    // fields are NEW: the parser now carries them so the orchestrator can make a
    // flag-gated re-attribution decision. Default-OFF behaviour is untouched.
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"Xiao Ming","holder_perspective":"FIRST_PERSON","subject":"computer",)"
        R"("predicate":"desires","object":"computer","modality":"DESIRES",)"
        R"("polarity":"POS","nesting_depth":0}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    const auto& s = r.statements[0];
    EXPECT_EQ(s.llm_holder, "Xiao Ming");
    EXPECT_EQ(s.llm_nesting_depth, 0);
    // Unchanged: holder_id is still empty out of the parser (orchestrator owns it).
    EXPECT_TRUE(s.holder_id.empty());
    EXPECT_EQ(s.subject_id, "computer");
    EXPECT_EQ(s.modality, schema::Modality::DESIRES);
}

TEST(JsonParser, LlmHolderDefaultsEmptyAndDepthDefaultsZeroWhenAbsent) {
    // A statement with no `holder` / `nesting_depth` keys parses with the
    // advisory fields at their defaults (empty / 0).
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder_perspective":"FIRST_PERSON","subject":"Bob",)"
        R"("predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_TRUE(r.statements[0].llm_holder.empty());
    EXPECT_EQ(r.statements[0].llm_nesting_depth, 0);
}

TEST(JsonParser, CarriesLlmNestingDepthForNestedBelief) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"Alice","holder_perspective":"INFERRED","subject":"Alice",)"
        R"("predicate":"believes","object":"Bob trusts Carol","modality":"BELIEVES",)"
        R"("polarity":"POS","nesting_depth":2}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].llm_holder, "Alice");
    EXPECT_EQ(r.statements[0].llm_nesting_depth, 2);
}

TEST(JsonParser, SkipsMalformedElementLeniently) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"subject":"","predicate":"p","object":"o","modality":"BELIEVES","polarity":"POS","holder_perspective":"INFERRED"},)"
        R"({"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])";
    ParseResult r = parse_extractor_json(raw, refs);
    EXPECT_TRUE(r.errors.empty());
    EXPECT_EQ(r.statements.size(), 1u);
}

}  // namespace starling::extractor
