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
    // subject_kind now READ from LLM JSON (not hardcoded). This fixture omits the
    // field, so under the new safe-default semantics it parses as "entity".
    // Explicitly carrying subject_kind:"cognizer" is exercised by
    // CarriesCognizerKindAdvisory below.
    EXPECT_EQ(s.subject_kind, "entity");
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

// ---- subject_kind / cognizer_kind (认知体过度注册修复 Task 1) ----

TEST(JsonParser, ReadsSubjectKindFromLlm) {
    // 合法 entity:不再无条件 cognizer。
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","subject":"Postgres","predicate":"is_a",)"
        R"("object":"database","subject_kind":"entity"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "entity");
}

TEST(JsonParser, DefaultsToEntityWhenSubjectKindMissing) {
    // fallback=entity(安全侧:漏字段宁可不注册)。parser 本就 lenient,
    // 缺失 → 默认 entity,语句照常产出(不 skip、不 error)。
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","subject":"H800 memory","predicate":"has_value","object":"80GB"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "entity");
}

TEST(JsonParser, DefaultsToEntityOnInvalidSubjectKind) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","subject":"x","predicate":"p","object":"o","subject_kind":"garbage"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "entity");
}

TEST(JsonParser, IgnoresInvalidCognizerKind) {
    // cognizer_kind 值域外(如 "robot")→ advisory 置空,由下游回退 human,
    // 绝不让非法串流到 cognizer_kind_from_string(它对未知串 throw)。
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","subject":"X","predicate":"p","object":"o",)"
        R"("subject_kind":"cognizer","cognizer_kind":"robot"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "cognizer");
    EXPECT_EQ(r.statements[0].llm_cognizer_kind, "");  // 非法 → 空 → 下游默认 human
}

TEST(JsonParser, CarriesCognizerKindAdvisory) {
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","subject":"Alice","predicate":"responsible_for","object":"auth",)"
        R"("subject_kind":"cognizer","cognizer_kind":"human"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "cognizer");
    EXPECT_EQ(r.statements[0].llm_cognizer_kind, "human");
}

TEST(JsonParser, EntitySubjectIgnoresCognizerKind) {
    // subject_kind=entity 时忽略任何 cognizer_kind(entity 不是认知体)。
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"self","subject":"Postgres","predicate":"is_a","object":"database",)"
        R"("subject_kind":"entity","cognizer_kind":"human"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].subject_kind, "entity");
    EXPECT_EQ(r.statements[0].llm_cognizer_kind, "");
}

TEST(JsonParser, AcceptsSelfCognizerKind) {
    // self 是合法 cognizer_kind(一等认知主体);下游(extractor)消解到 holder_id。
    ExistingRefMap refs;
    const std::string raw =
        R"([{"holder":"Alice","subject":"me","predicate":"is","object":"reliable",)"
        R"("subject_kind":"cognizer","cognizer_kind":"self"}])";
    ParseResult r = parse_extractor_json(raw, refs);
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].llm_cognizer_kind, "self");
}

}  // namespace starling::extractor
