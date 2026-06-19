#include <gtest/gtest.h>
#include "starling/extractor/statement_validator.hpp"
#include "starling/schema/statement_enums.hpp"

#include <string>

using namespace starling::extractor;
using starling::schema::ReviewStatus;
using starling::schema::Modality;

namespace {
// Build a fully-populated, non-OCCURRED, confidence=0.9 belief statement with the
// given predicate. Replicates the field setup from valid_first_person() in
// tests/cpp/test_statement_validator.cpp (that helper is in an anonymous
// namespace, so it cannot be reused across translation units). FIRST_PERSON
// perspective + USER_INPUT provenance keep is_weak_inference() false at 0.9;
// modality defaults to BELIEVES (non-OCCURRED).
ExtractedStatement make_valid_belief(const std::string& predicate) {
    ExtractedStatement s;
    s.holder_id             = "cog-self";
    s.holder_tenant_id      = "default";
    s.holder_perspective    = starling::schema::Perspective::FIRST_PERSON;
    s.subject_kind          = "cognizer";
    s.subject_id            = "cog-self";
    s.object_kind           = "str";
    s.object_value          = "auth";
    s.canonical_object_hash = "deadbeef";
    s.modality              = Modality::BELIEVES;
    s.polarity              = starling::schema::Polarity::POS;
    s.observed_at           = "2026-05-23T10:00:00Z";
    s.chunk_index           = 0;
    s.source_hash           = "fff";
    s.perceived_by          = {"cog-self"};
    s.provenance            = starling::schema::StatementProvenance::USER_INPUT;
    s.review_status         = starling::schema::ReviewStatus::APPROVED;
    s.predicate             = predicate;
    s.confidence            = 0.9;
    return s;
}
}  // namespace

TEST(ValidationPolicy, ExtraPredicateNotReviewed) {
    auto s = make_valid_belief("annotates");
    ValidationPolicy pol; pol.extra_core_predicates = {"annotates"};
    auto out = validate_extracted_statement(s, pol);
    EXPECT_TRUE(out.accepted);
    EXPECT_FALSE(out.review_status_override.has_value());
}
TEST(ValidationPolicy, DefaultFlagsUnknownPredicate) {
    auto s = make_valid_belief("annotates");
    auto out = validate_extracted_statement(s);  // default policy
    EXPECT_TRUE(out.accepted);
    ASSERT_TRUE(out.review_status_override.has_value());
    EXPECT_EQ(*out.review_status_override, ReviewStatus::REVIEW_REQUESTED);
}
TEST(ValidationPolicy, LoweredDropFloorKeepsLowConfidence) {
    auto s = make_valid_belief("believes"); s.confidence = 0.2;
    ValidationPolicy pol; pol.confidence_drop_floor = 0.15;
    auto out = validate_extracted_statement(s, pol);
    EXPECT_TRUE(out.accepted);
}
TEST(ValidationPolicy, DefaultDropFloorDropsLowConfidence) {
    auto s = make_valid_belief("believes"); s.confidence = 0.25;
    auto out = validate_extracted_statement(s);  // default policy
    EXPECT_FALSE(out.accepted);
    EXPECT_EQ(out.error_kind, "below_minimum_confidence");
}
TEST(ValidationPolicy, RaisedWeakFloorFlagsModerateConfidence) {
    auto s = make_valid_belief("believes"); s.confidence = 0.6;  // core predicate so vocab gate doesn't overwrite the flag
    ValidationPolicy pol; pol.weak_inference_floor = 0.7;
    auto out = validate_extracted_statement(s, pol);
    EXPECT_TRUE(out.accepted);
    ASSERT_TRUE(out.review_status_override.has_value());
    EXPECT_EQ(*out.review_status_override, ReviewStatus::INFERRED_UNREVIEWED);
}
TEST(ValidationPolicy, OccurredUnknownPredicateKeptVerbatim) {
    auto s = make_valid_belief("teleported"); s.modality = Modality::OCCURRED;
    auto out = validate_extracted_statement(s);  // default policy
    EXPECT_TRUE(out.accepted);
    EXPECT_FALSE(out.review_status_override.has_value());
}
