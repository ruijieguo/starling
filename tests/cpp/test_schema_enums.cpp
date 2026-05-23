#include <gtest/gtest.h>

#include "starling/schema/enums.hpp"

#include <stdexcept>
#include <string>

using starling::schema::SourceKind;
using starling::schema::IngestPolicy;
using starling::schema::IngestMode;
using starling::schema::PrivacyClass;
using starling::schema::EngramRetentionMode;

using starling::schema::source_kind_from_string;
using starling::schema::ingest_policy_from_string;
using starling::schema::ingest_mode_from_string;
using starling::schema::privacy_class_from_string;
using starling::schema::engram_retention_mode_from_string;

TEST(SchemaEnums, SourceKindRoundTrip) {
    EXPECT_EQ(to_string(SourceKind::USER_INPUT), "user_input");
    EXPECT_EQ(to_string(SourceKind::EXTERNAL_DOC), "external_doc");
    EXPECT_EQ(to_string(SourceKind::TOOL_OBSERVATION), "tool_observation");
    EXPECT_EQ(to_string(SourceKind::SYSTEM_INTERNAL), "system_internal");
    EXPECT_EQ(to_string(SourceKind::OBSERVER_AGENT), "observer_agent");
    EXPECT_EQ(to_string(SourceKind::REPLAY_OUTPUT), "replay_output");

    EXPECT_EQ(source_kind_from_string("user_input"), SourceKind::USER_INPUT);
    EXPECT_EQ(source_kind_from_string("replay_output"), SourceKind::REPLAY_OUTPUT);
    EXPECT_THROW(source_kind_from_string("unknown"), std::invalid_argument);
    EXPECT_THROW(source_kind_from_string(""), std::invalid_argument);
}

TEST(SchemaEnums, IngestPolicyRoundTrip) {
    EXPECT_EQ(to_string(IngestPolicy::STORE), "store");
    EXPECT_EQ(to_string(IngestPolicy::NO_STORE), "no_store");
    EXPECT_EQ(to_string(IngestPolicy::STORE_METADATA_ONLY), "store_metadata_only");
    EXPECT_EQ(to_string(IngestPolicy::REQUIRE_REVIEW), "require_review");

    EXPECT_EQ(ingest_policy_from_string("no_store"), IngestPolicy::NO_STORE);
    EXPECT_THROW(ingest_policy_from_string("STORE"), std::invalid_argument);
}

TEST(SchemaEnums, IngestModeRoundTrip) {
    EXPECT_EQ(to_string(IngestMode::CHUNKED_CONTENT), "chunked_content");
    EXPECT_EQ(to_string(IngestMode::WHOLE_RECORD), "whole_record");
    EXPECT_EQ(to_string(IngestMode::METADATA_ONLY), "metadata_only");
    EXPECT_EQ(ingest_mode_from_string("whole_record"), IngestMode::WHOLE_RECORD);
}

TEST(SchemaEnums, PrivacyClassRoundTrip) {
    EXPECT_EQ(to_string(PrivacyClass::PUBLIC), "public");
    EXPECT_EQ(to_string(PrivacyClass::REGULATED), "regulated");
    EXPECT_EQ(privacy_class_from_string("sensitive"), PrivacyClass::SENSITIVE);
}

TEST(SchemaEnums, EngramRetentionModeRoundTrip) {
    EXPECT_EQ(to_string(EngramRetentionMode::LEGAL_HOLD), "legal_hold");
    EXPECT_EQ(to_string(EngramRetentionMode::AUDIT_RETAIN), "audit_retain");
    EXPECT_EQ(to_string(EngramRetentionMode::REDACTED_RETAIN), "redacted_retain");
    EXPECT_EQ(to_string(EngramRetentionMode::CRYPTO_ERASURE), "crypto_erasure");

    EXPECT_EQ(engram_retention_mode_from_string("crypto_erasure"),
              EngramRetentionMode::CRYPTO_ERASURE);
    EXPECT_THROW(engram_retention_mode_from_string("erased"), std::invalid_argument);
}
