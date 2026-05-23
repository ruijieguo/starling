#include <gtest/gtest.h>

#include "starling/evidence/ingest_policy_resolver.hpp"

using starling::evidence::IngestPolicyResolver;
using starling::schema::IngestPolicy;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

TEST(IngestPolicyResolver, UserInputPublicStoreStaysStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::PUBLIC, IngestPolicy::STORE),
        IngestPolicy::STORE);
}

TEST(IngestPolicyResolver, UserInputSensitiveStoreStaysStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::SENSITIVE, IngestPolicy::STORE),
        IngestPolicy::STORE);
}

TEST(IngestPolicyResolver, UserInputRegulatedDowngradesToRequireReview) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::REGULATED, IngestPolicy::STORE),
        IngestPolicy::REQUIRE_REVIEW);
}

TEST(IngestPolicyResolver, ExternalDocPublicStoreStaysStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::EXTERNAL_DOC, PrivacyClass::PUBLIC, IngestPolicy::STORE),
        IngestPolicy::STORE);
}

TEST(IngestPolicyResolver, ExternalDocSensitiveDowngradesToRequireReview) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::EXTERNAL_DOC, PrivacyClass::SENSITIVE, IngestPolicy::STORE),
        IngestPolicy::REQUIRE_REVIEW);
}

TEST(IngestPolicyResolver, ExternalDocRegulatedDowngradesToRequireReview) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::EXTERNAL_DOC, PrivacyClass::REGULATED, IngestPolicy::STORE),
        IngestPolicy::REQUIRE_REVIEW);
}

TEST(IngestPolicyResolver, ToolObservationDowngradesStoreToMetadataOnly) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::TOOL_OBSERVATION, PrivacyClass::INTERNAL, IngestPolicy::STORE),
        IngestPolicy::STORE_METADATA_ONLY);
}

TEST(IngestPolicyResolver, ToolObservationKeepsMetadataOnly) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::TOOL_OBSERVATION, PrivacyClass::PUBLIC,
            IngestPolicy::STORE_METADATA_ONLY),
        IngestPolicy::STORE_METADATA_ONLY);
}

TEST(IngestPolicyResolver, ToolObservationProducerRequireReviewWins) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::TOOL_OBSERVATION, PrivacyClass::PUBLIC,
            IngestPolicy::REQUIRE_REVIEW),
        IngestPolicy::REQUIRE_REVIEW);
}

TEST(IngestPolicyResolver, SystemInternalAlwaysNoStore) {
    for (auto privacy : {PrivacyClass::PUBLIC, PrivacyClass::INTERNAL,
                         PrivacyClass::PERSONAL, PrivacyClass::SENSITIVE,
                         PrivacyClass::REGULATED}) {
        for (auto declared : {IngestPolicy::STORE,
                              IngestPolicy::STORE_METADATA_ONLY,
                              IngestPolicy::REQUIRE_REVIEW,
                              IngestPolicy::NO_STORE}) {
            EXPECT_EQ(
                IngestPolicyResolver::resolve(
                    SourceKind::SYSTEM_INTERNAL, privacy, declared),
                IngestPolicy::NO_STORE)
                << "privacy=" << static_cast<int>(privacy)
                << " declared=" << static_cast<int>(declared);
        }
    }
}

TEST(IngestPolicyResolver, ObserverAgentAlwaysNoStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::OBSERVER_AGENT, PrivacyClass::PUBLIC, IngestPolicy::STORE),
        IngestPolicy::NO_STORE);
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::OBSERVER_AGENT, PrivacyClass::REGULATED,
            IngestPolicy::REQUIRE_REVIEW),
        IngestPolicy::NO_STORE);
}

TEST(IngestPolicyResolver, ReplayOutputAlwaysNoStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::REPLAY_OUTPUT, PrivacyClass::INTERNAL, IngestPolicy::STORE),
        IngestPolicy::NO_STORE);
}

TEST(IngestPolicyResolver, ProducerDeclaredNoStoreIsHonoredForUserInput) {
    // user_input + producer explicitly says NO_STORE → NO_STORE (producer
    // intent wins downward; never upward).
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::PUBLIC, IngestPolicy::NO_STORE),
        IngestPolicy::NO_STORE);
}

TEST(IngestPolicyResolver, UserInputProducerStoreMetadataOnlyHonored) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::INTERNAL,
            IngestPolicy::STORE_METADATA_ONLY),
        IngestPolicy::STORE_METADATA_ONLY);
}
