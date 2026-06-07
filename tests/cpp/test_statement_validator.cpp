#include <gtest/gtest.h>

#include "starling/extractor/statement_validator.hpp"

#include <optional>
#include <string>

namespace starling::extractor {

namespace {

ExtractedStatement valid_first_person() {
    ExtractedStatement s;
    s.holder_id            = "cog-self";
    s.holder_tenant_id     = "default";
    s.holder_perspective   = schema::Perspective::FIRST_PERSON;
    s.subject_kind         = "cognizer";
    s.subject_id           = "cog-self";
    s.predicate            = "responsible_for";
    s.object_kind          = "str";
    s.object_value         = "auth";
    s.canonical_object_hash = "deadbeef";
    s.modality             = schema::Modality::BELIEVES;
    s.polarity             = schema::Polarity::POS;
    s.confidence           = 0.85;
    s.observed_at          = "2026-05-23T10:00:00Z";
    s.chunk_index          = 0;
    s.source_hash          = "fff";
    s.perceived_by         = {"cog-self"};
    s.provenance           = schema::StatementProvenance::USER_INPUT;
    s.review_status        = schema::ReviewStatus::APPROVED;
    return s;
}

}  // namespace

TEST(StatementValidator, AcceptsValidFirstPerson) {
    auto outcome = validate_extracted_statement(valid_first_person());
    EXPECT_TRUE(outcome.ok());
    EXPECT_EQ(outcome.review_status_override, std::nullopt);
}

TEST(StatementValidator, RejectsEmptyHolder) {
    auto s = valid_first_person();
    s.holder_id = "";
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "missing_required_field");
    EXPECT_TRUE(outcome.detail.find("holder_id") != std::string::npos);
}

TEST(StatementValidator, RejectsEmptyPredicate) {
    auto s = valid_first_person();
    s.predicate = "";
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "missing_required_field");
}

TEST(StatementValidator, RejectsObjectKindList) {
    auto s = valid_first_person();
    s.object_kind = "list";
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "value_type_unsupported");
}

TEST(StatementValidator, RejectsObjectKindDict) {
    auto s = valid_first_person();
    s.object_kind = "dict";
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "value_type_unsupported");
}

TEST(StatementValidator, RejectsConfidenceBelowThreshold) {
    auto s = valid_first_person();
    s.confidence = 0.20;
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "below_minimum_confidence");
}

TEST(StatementValidator, RejectsConfidenceOutOfRangeHigh) {
    auto s = valid_first_person();
    s.confidence = 1.5;
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "confidence_out_of_range");
}

TEST(StatementValidator, RejectsConfidenceOutOfRangeNegative) {
    auto s = valid_first_person();
    s.confidence = -0.1;
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "confidence_out_of_range");
}

TEST(StatementValidator, ForcesInferredUnreviewedOnHearsay) {
    auto s = valid_first_person();
    s.holder_perspective = schema::Perspective::HEARSAY;
    s.confidence = 0.55;
    auto outcome = validate_extracted_statement(s);
    EXPECT_TRUE(outcome.ok());
    EXPECT_EQ(outcome.review_status_override,
              std::optional{schema::ReviewStatus::INFERRED_UNREVIEWED});
}

TEST(StatementValidator, ForcesInferredUnreviewedOnInferred) {
    auto s = valid_first_person();
    s.holder_perspective = schema::Perspective::INFERRED;
    s.confidence = 0.45;
    auto outcome = validate_extracted_statement(s);
    EXPECT_TRUE(outcome.ok());
    EXPECT_EQ(outcome.review_status_override,
              std::optional{schema::ReviewStatus::INFERRED_UNREVIEWED});
}

TEST(StatementValidator, ForcesInferredUnreviewedOnTomInferredProvenance) {
    auto s = valid_first_person();
    s.provenance = schema::StatementProvenance::TOM_INFERRED;
    s.confidence = 0.6;
    auto outcome = validate_extracted_statement(s);
    EXPECT_TRUE(outcome.ok());
    EXPECT_EQ(outcome.review_status_override,
              std::optional{schema::ReviewStatus::INFERRED_UNREVIEWED});
}

TEST(StatementValidator, FirstPersonAtThresholdConfidenceStaysApproved) {
    // First-person at 0.5 (the boundary): keeps APPROVED because perspective
    // is FIRST_PERSON AND provenance is USER_INPUT AND confidence >= 0.5.
    auto s = valid_first_person();
    s.confidence = 0.5;
    auto outcome = validate_extracted_statement(s);
    EXPECT_TRUE(outcome.ok());
    EXPECT_EQ(outcome.review_status_override, std::nullopt);
}

TEST(StatementValidator, RejectsEmptySourceHash) {
    auto s = valid_first_person();
    s.source_hash = "";
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "missing_required_field");
}

TEST(StatementValidator, RejectsEmptyTenant) {
    auto s = valid_first_person();
    s.holder_tenant_id = "";
    auto outcome = validate_extracted_statement(s);
    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "missing_required_field");
    EXPECT_TRUE(outcome.detail.find("holder_tenant_id") != std::string::npos);
}

TEST(StatementValidator, AcceptsConfidenceAtMaximum) {
    // Boundary: confidence == 1.0 is in-range, well above threshold,
    // and (with FIRST_PERSON + USER_INPUT) is not weak. Pin so a
    // future range check using > / >= can't quietly drop the boundary.
    auto s = valid_first_person();
    s.confidence = 1.0;
    auto outcome = validate_extracted_statement(s);
    EXPECT_TRUE(outcome.ok());
    EXPECT_EQ(outcome.review_status_override, std::nullopt);
}

TEST(StatementValidator, RejectsAmbiguousDerivedParent) {
    auto s = valid_first_person();
    s.derived_from = {"shared-parent"};

    auto outcome = validate_for_write(
        s, [](const std::string&) { return std::string("ambiguous:shared-parent"); });

    EXPECT_FALSE(outcome.ok());
    EXPECT_EQ(outcome.error_kind, "derived_parent_ambiguous");
}

}  // namespace starling::extractor
