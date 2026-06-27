#include <gtest/gtest.h>

#include "starling/schema/statement_enums.hpp"

namespace starling::schema {

TEST(StatementEnums, PerspectiveToString) {
    EXPECT_EQ(to_string(Perspective::FIRST_PERSON), "first_person");
    EXPECT_EQ(to_string(Perspective::QUOTED),       "quoted");
    EXPECT_EQ(to_string(Perspective::INFERRED),     "inferred");
    EXPECT_EQ(to_string(Perspective::HEARSAY),      "hearsay");
}

TEST(StatementEnums, PerspectiveFromString) {
    EXPECT_EQ(perspective_from_string("first_person"), Perspective::FIRST_PERSON);
    EXPECT_EQ(perspective_from_string("quoted"),       Perspective::QUOTED);
    EXPECT_EQ(perspective_from_string("inferred"),     Perspective::INFERRED);
    EXPECT_EQ(perspective_from_string("hearsay"),      Perspective::HEARSAY);
    EXPECT_THROW(perspective_from_string("default"), std::invalid_argument);
}

TEST(StatementEnums, ModalityToString) {
    EXPECT_EQ(to_string(Modality::BELIEVES),    "believes");
    EXPECT_EQ(to_string(Modality::KNOWS),       "knows");
    EXPECT_EQ(to_string(Modality::ASSUMES),     "assumes");
    EXPECT_EQ(to_string(Modality::DOUBTS),      "doubts");
    EXPECT_EQ(to_string(Modality::DESIRES),     "desires");
    EXPECT_EQ(to_string(Modality::INTENDS),     "intends");
    EXPECT_EQ(to_string(Modality::COMMITS),     "commits");
    EXPECT_EQ(to_string(Modality::PREFERS),     "prefers");
    EXPECT_EQ(to_string(Modality::NORM_OUGHT),  "norm_ought");
    EXPECT_EQ(to_string(Modality::NORM_FORBID), "norm_forbid");
    EXPECT_EQ(to_string(Modality::RECANTED),    "recanted");
}

TEST(StatementEnums, ModalityFromString) {
    EXPECT_EQ(modality_from_string("believes"),    Modality::BELIEVES);
    EXPECT_EQ(modality_from_string("commits"),     Modality::COMMITS);
    EXPECT_EQ(modality_from_string("norm_forbid"), Modality::NORM_FORBID);
    EXPECT_THROW(modality_from_string("believe"), std::invalid_argument);
    EXPECT_THROW(modality_from_string(""),        std::invalid_argument);
}

TEST(StatementEnums, PolarityToString) {
    EXPECT_EQ(to_string(Polarity::POS),     "pos");
    EXPECT_EQ(to_string(Polarity::NEG),     "neg");
    EXPECT_EQ(to_string(Polarity::UNKNOWN), "unknown");
}

TEST(StatementEnums, PolarityFromString) {
    EXPECT_EQ(polarity_from_string("pos"),     Polarity::POS);
    EXPECT_EQ(polarity_from_string("neg"),     Polarity::NEG);
    EXPECT_EQ(polarity_from_string("unknown"), Polarity::UNKNOWN);
    EXPECT_THROW(polarity_from_string("positive"), std::invalid_argument);
}

TEST(StatementEnums, ConsolidationStateToString) {
    EXPECT_EQ(to_string(ConsolidationState::VOLATILE),                  "volatile");
    EXPECT_EQ(to_string(ConsolidationState::REPLAYING_CONSOLIDATING),   "replaying_consolidating");
    EXPECT_EQ(to_string(ConsolidationState::REPLAYING_RECONSOLIDATING), "replaying_reconsolidating");
    EXPECT_EQ(to_string(ConsolidationState::CONSOLIDATED),              "consolidated");
    EXPECT_EQ(to_string(ConsolidationState::ARCHIVED),                  "archived");
    EXPECT_EQ(to_string(ConsolidationState::FORGOTTEN),                 "forgotten");
}

TEST(StatementEnums, ReviewStatusToString) {
    EXPECT_EQ(to_string(ReviewStatus::APPROVED),            "approved");
    EXPECT_EQ(to_string(ReviewStatus::PENDING_REVIEW),      "pending_review");
    EXPECT_EQ(to_string(ReviewStatus::INFERRED_UNREVIEWED), "inferred_unreviewed");
    EXPECT_EQ(to_string(ReviewStatus::REVIEW_REQUESTED),    "review_requested");
    EXPECT_EQ(to_string(ReviewStatus::REJECTED),            "rejected");
}

TEST(StatementEnums, ProvenanceToString) {
    EXPECT_EQ(to_string(StatementProvenance::USER_INPUT),              "user_input");
    EXPECT_EQ(to_string(StatementProvenance::REPLAY_DERIVED),          "replay_derived");
    EXPECT_EQ(to_string(StatementProvenance::TOM_INFERRED),            "tom_inferred");
    EXPECT_EQ(to_string(StatementProvenance::RECONSOLIDATION_DERIVED), "reconsolidation_derived");
    EXPECT_EQ(to_string(StatementProvenance::CONSOLIDATION_ABSTRACT),  "consolidation_abstract");
}

}  // namespace starling::schema
