#include <gtest/gtest.h>

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/extracted_statement.hpp"

namespace starling::extractor {

TEST(ExtractedStatement, Defaults) {
    ExtractedStatement s;
    EXPECT_EQ(s.holder_id, "");
    EXPECT_EQ(s.confidence, 0.0);
    EXPECT_EQ(s.chunk_index, 0);
    EXPECT_TRUE(s.perceived_by.empty());
    EXPECT_EQ(s.review_status, schema::ReviewStatus::APPROVED);
    EXPECT_EQ(s.provenance, schema::StatementProvenance::USER_INPUT);
}

TEST(ExtractedStatement, AssignAllFields) {
    ExtractedStatement s;
    s.holder_id           = "cog-1";
    s.holder_tenant_id    = "default";
    s.holder_perspective  = schema::Perspective::FIRST_PERSON;
    s.subject_kind        = "cognizer";
    s.subject_id          = "cog-2";
    s.predicate           = "responsible_for";
    s.object_kind         = "str";
    s.object_value        = "auth";
    s.canonical_object_hash = "abc123";
    s.modality            = schema::Modality::BELIEVES;
    s.polarity            = schema::Polarity::POS;
    s.confidence          = 0.85;
    s.observed_at         = "2026-05-23T10:00:00Z";
    s.chunk_index         = 0;
    s.source_hash         = "fff";
    s.perceived_by        = {"cog-1", "cog-2"};
    s.provenance          = schema::StatementProvenance::USER_INPUT;
    s.review_status       = schema::ReviewStatus::APPROVED;
    EXPECT_EQ(s.predicate, "responsible_for");
    EXPECT_EQ(s.perceived_by.size(), 2u);
    EXPECT_EQ(s.confidence, 0.85);
}

TEST(ExistingRefMap, EmptyByDefault) {
    ExistingRefMap m;
    EXPECT_TRUE(m.empty());
}

TEST(ExistingRefMap, ResolveShortId) {
    ExistingRefMap m;
    m["s1"] = "stmt-uuid-aaa";
    m["s2"] = "stmt-uuid-bbb";
    EXPECT_EQ(m.size(), 2u);
    auto it = m.find("s1");
    ASSERT_NE(it, m.end());
    EXPECT_EQ(it->second, "stmt-uuid-aaa");
    EXPECT_EQ(m.find("missing"), m.end());
}

}  // namespace starling::extractor
