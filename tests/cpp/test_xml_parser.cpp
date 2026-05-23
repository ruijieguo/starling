#include <gtest/gtest.h>

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/xml_parser.hpp"

#include <algorithm>
#include <string>
#include <vector>

namespace starling::extractor {

namespace {

constexpr const char* kQ2_001 = R"XML(
<extraction>
  <statement>
    <holder ref="cog-self"/>
    <perspective>first_person</perspective>
    <subject kind="cognizer" id="cog-self"/>
    <predicate>responsible_for</predicate>
    <object kind="str" canonical_hash="hash-auth">auth</object>
    <modality>believes</modality>
    <polarity>pos</polarity>
    <confidence>0.85</confidence>
    <observed_at>2026-05-23T10:00:00Z</observed_at>
    <perceived_by ref="cog-self"/>
  </statement>
</extraction>
)XML";

constexpr const char* kQ2_002 = R"XML(
<extraction>
  <statement source_speaker="cog-bob">
    <holder ref="cog-self"/>
    <perspective>quoted</perspective>
    <subject kind="cognizer" id="cog-bob"/>
    <predicate>responsible_for</predicate>
    <object kind="str" canonical_hash="hash-auth">auth</object>
    <modality>believes</modality>
    <polarity>pos</polarity>
    <confidence>0.75</confidence>
    <observed_at>2026-05-23T10:00:00Z</observed_at>
    <perceived_by ref="cog-self"/>
    <perceived_by ref="cog-bob"/>
  </statement>
</extraction>
)XML";

constexpr const char* kQ2_003 = R"XML(
<extraction>
  <statement>
    <holder ref="cog-self"/>
    <perspective>hearsay</perspective>
    <subject kind="cognizer" id="cog-bob"/>
    <predicate>left_company</predicate>
    <object kind="bool" canonical_hash="hash-true">true</object>
    <modality>believes</modality>
    <polarity>pos</polarity>
    <confidence>0.55</confidence>
    <observed_at>2026-05-23T10:00:00Z</observed_at>
    <perceived_by ref="cog-self"/>
  </statement>
</extraction>
)XML";

constexpr const char* kQ2_004 = R"XML(
<extraction>
  <statement>
    <holder ref="cog-self"/>
    <perspective>inferred</perspective>
    <subject kind="cognizer" id="cog-bob"/>
    <predicate>upset_about</predicate>
    <object kind="str" canonical_hash="hash-x">scope_change</object>
    <modality>believes</modality>
    <polarity>pos</polarity>
    <confidence>0.40</confidence>
    <observed_at>2026-05-23T10:00:00Z</observed_at>
    <perceived_by ref="cog-self"/>
  </statement>
</extraction>
)XML";

}  // namespace

TEST(XmlParser, EmptyInputProducesError) {
    ExistingRefMap m;
    auto r = parse_extractor_xml("", m);
    EXPECT_TRUE(r.statements.empty());
    EXPECT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "empty_input");
}

TEST(XmlParser, WhitespaceOnlyProducesError) {
    ExistingRefMap m;
    auto r = parse_extractor_xml("   \n  ", m);
    EXPECT_FALSE(r.errors.empty());
}

TEST(XmlParser, FirstPersonFixture) {
    ExistingRefMap m;
    auto r = parse_extractor_xml(kQ2_001, m);
    ASSERT_TRUE(r.errors.empty()) << r.errors.front().kind;
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].holder_id, "cog-self");
    EXPECT_EQ(r.statements[0].holder_perspective, schema::Perspective::FIRST_PERSON);
    EXPECT_EQ(r.statements[0].subject_kind, "cognizer");
    EXPECT_EQ(r.statements[0].subject_id, "cog-self");
    EXPECT_EQ(r.statements[0].predicate, "responsible_for");
    EXPECT_EQ(r.statements[0].object_kind, "str");
    EXPECT_EQ(r.statements[0].object_value, "auth");
    EXPECT_EQ(r.statements[0].canonical_object_hash, "hash-auth");
    EXPECT_DOUBLE_EQ(r.statements[0].confidence, 0.85);
    EXPECT_EQ(r.statements[0].perceived_by, std::vector<std::string>{"cog-self"});
}

TEST(XmlParser, QuotedFixtureCarriesSourceSpeaker) {
    ExistingRefMap m;
    auto r = parse_extractor_xml(kQ2_002, m);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].holder_perspective, schema::Perspective::QUOTED);
    EXPECT_NE(std::find(r.statements[0].perceived_by.begin(),
                        r.statements[0].perceived_by.end(),
                        "cog-bob"),
              r.statements[0].perceived_by.end());
}

TEST(XmlParser, HearsayFixture) {
    ExistingRefMap m;
    auto r = parse_extractor_xml(kQ2_003, m);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].holder_perspective, schema::Perspective::HEARSAY);
    EXPECT_EQ(r.statements[0].object_kind, "bool");
    EXPECT_EQ(r.statements[0].object_value, "true");
}

TEST(XmlParser, InferredFixture) {
    ExistingRefMap m;
    auto r = parse_extractor_xml(kQ2_004, m);
    ASSERT_TRUE(r.errors.empty());
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].holder_perspective, schema::Perspective::INFERRED);
    EXPECT_DOUBLE_EQ(r.statements[0].confidence, 0.40);
}

TEST(XmlParser, RejectsUnknownTag) {
    ExistingRefMap m;
    constexpr const char* bad = "<extraction><foo/></extraction>";
    auto r = parse_extractor_xml(bad, m);
    EXPECT_TRUE(r.statements.empty());
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "unknown_tag");
}

TEST(XmlParser, RejectsMissingRequiredAttribute) {
    ExistingRefMap m;
    constexpr const char* bad = R"XML(
        <extraction>
          <statement>
            <holder/>
            <perspective>first_person</perspective>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "missing_required_attribute");
}

TEST(XmlParser, RejectsUnbalancedTag) {
    ExistingRefMap m;
    constexpr const char* bad = "<extraction><statement>";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "unbalanced_tag");
}

TEST(XmlParser, RejectsValueTypeList) {
    ExistingRefMap m;
    constexpr const char* bad = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>first_person</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>likes</predicate>
            <object kind="list" canonical_hash="x">[1,2]</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.5</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "value_type_unsupported");
}

TEST(XmlParser, UnresolvedShortIdProducesError) {
    ExistingRefMap m;
    constexpr const char* xml = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>inferred</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>references</predicate>
            <object kind="statement" canonical_hash="h">
              <statement_ref id="s1"/>
            </object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.5</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(xml, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "unresolved_short_id");
}

TEST(XmlParser, ResolvedShortIdSucceeds) {
    ExistingRefMap m;
    m["s1"] = "stmt-uuid-aaa";
    constexpr const char* xml = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>inferred</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>references</predicate>
            <object kind="statement" canonical_hash="h">
              <statement_ref id="s1"/>
            </object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.5</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(xml, m);
    ASSERT_TRUE(r.errors.empty()) << r.errors.front().kind;
    ASSERT_EQ(r.statements.size(), 1u);
    EXPECT_EQ(r.statements[0].object_kind, "statement");
    EXPECT_EQ(r.statements[0].object_value, "stmt-uuid-aaa");
}

TEST(XmlParser, RejectsInvalidPerspective) {
    ExistingRefMap m;
    constexpr const char* bad = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>third_person</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>p</predicate>
            <object kind="str" canonical_hash="h">v</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.5</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "invalid_enum_value");
}

TEST(XmlParser, RejectsInvalidModality) {
    ExistingRefMap m;
    constexpr const char* bad = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>first_person</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>p</predicate>
            <object kind="str" canonical_hash="h">v</object>
            <modality>believees</modality>
            <polarity>pos</polarity>
            <confidence>0.5</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "invalid_enum_value");
}

TEST(XmlParser, RejectsInvalidConfidence) {
    ExistingRefMap m;
    constexpr const char* bad = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>first_person</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>p</predicate>
            <object kind="str" canonical_hash="h">v</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>not_a_number</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "invalid_number");
}

TEST(XmlParser, RejectsConfidenceTrailingGarbage) {
    ExistingRefMap m;
    constexpr const char* bad = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>first_person</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>p</predicate>
            <object kind="str" canonical_hash="h">v</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.5xyz</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "invalid_number");
}

TEST(XmlParser, RejectsObjectStrayChildElement) {
    ExistingRefMap m;
    constexpr const char* bad = R"XML(
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>first_person</perspective>
            <subject kind="cognizer" id="cog-self"/>
            <predicate>p</predicate>
            <object kind="str" canonical_hash="h"><stray/>auth</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.5</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>)XML";
    auto r = parse_extractor_xml(bad, m);
    ASSERT_FALSE(r.errors.empty());
    // Either unknown_tag (preferred — a stray element where none allowed)
    // or mixed_content (if our flush_text trips first). Accept either.
    const auto& kind = r.errors.front().kind;
    EXPECT_TRUE(kind == "unknown_tag" || kind == "mixed_content")
        << "got: " << kind;
}

TEST(XmlParser, RejectsExcessiveNestingDepth) {
    ExistingRefMap m;
    // Build "<extraction>" + N "<x>" + "</x>" * N + "</extraction>" for N=200 (>>64).
    // The cap of 64 must trigger nesting_too_deep.
    std::string xml = "<extraction>";
    constexpr int N = 200;
    for (int i = 0; i < N; ++i) xml += "<x>";
    for (int i = 0; i < N; ++i) xml += "</x>";
    xml += "</extraction>";
    auto r = parse_extractor_xml(xml, m);
    ASSERT_FALSE(r.errors.empty());
    EXPECT_EQ(r.errors.front().kind, "nesting_too_deep");
}

}  // namespace starling::extractor
