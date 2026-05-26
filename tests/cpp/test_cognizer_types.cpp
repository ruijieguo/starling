#include "starling/cognizer/cognizer.hpp"

#include <gtest/gtest.h>

using namespace starling::cognizer;

TEST(CognizerKindEnum, RoundTripAllSix) {
    for (auto k : {CognizerKind::Self, CognizerKind::Human, CognizerKind::Agent,
                    CognizerKind::Group, CognizerKind::Role, CognizerKind::External}) {
        EXPECT_EQ(cognizer_kind_from_string(to_string(k)), k);
    }
}

TEST(CognizerKindEnum, RejectsUnknown) {
    EXPECT_THROW(cognizer_kind_from_string("alien"), std::invalid_argument);
}

TEST(FiskeModeEnum, RoundTripAllFour) {
    for (auto m : {FiskeMode::Communal, FiskeMode::Authority,
                    FiskeMode::Equality, FiskeMode::Market}) {
        EXPECT_EQ(fiske_mode_from_string(to_string(m)), m);
    }
}

TEST(ErrorTypes, AliasCollisionCarriesPayload) {
    try {
        throw AliasCollision("cog-123", "alice");
    } catch (const AliasCollision& e) {
        EXPECT_EQ(e.existing_id, "cog-123");
        EXPECT_EQ(e.alias, "alice");
    }
}

TEST(ErrorTypes, GroupTenantImplicitMessageMentionsSpec) {
    try {
        throw GroupTenantImplicit();
    } catch (const std::invalid_argument& e) {
        EXPECT_NE(std::string(e.what()).find("08_cognizer.md:139"), std::string::npos);
    }
}

TEST(ErrorTypes, FiskeWeightsInvalidDistinct) {
    EXPECT_THROW(throw FiskeWeightsInvalid(), std::invalid_argument);
}

TEST(ErrorTypes, CognizerNotFoundCarriesIds) {
    try {
        throw CognizerNotFound("cog-xyz", "default");
    } catch (const CognizerNotFound& e) {
        EXPECT_EQ(e.id, "cog-xyz");
        EXPECT_EQ(e.tenant_id, "default");
    }
}
