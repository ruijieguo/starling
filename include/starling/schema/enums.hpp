#pragma once

#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::schema {

enum class SourceKind {
    USER_INPUT,
    EXTERNAL_DOC,
    TOOL_OBSERVATION,
    SYSTEM_INTERNAL,
    OBSERVER_AGENT,
    REPLAY_OUTPUT,
};

enum class IngestPolicy {
    STORE,
    NO_STORE,
    STORE_METADATA_ONLY,
    REQUIRE_REVIEW,
};

enum class IngestMode {
    CHUNKED_CONTENT,
    WHOLE_RECORD,
    METADATA_ONLY,
};

enum class PrivacyClass {
    PUBLIC,
    INTERNAL,
    PERSONAL,
    SENSITIVE,
    REGULATED,
};

enum class EngramRetentionMode {
    LEGAL_HOLD,
    AUDIT_RETAIN,
    REDACTED_RETAIN,
    CRYPTO_ERASURE,
};

std::string_view to_string(SourceKind);
std::string_view to_string(IngestPolicy);
std::string_view to_string(IngestMode);
std::string_view to_string(PrivacyClass);
std::string_view to_string(EngramRetentionMode);

SourceKind          source_kind_from_string(std::string_view);
IngestPolicy        ingest_policy_from_string(std::string_view);
IngestMode          ingest_mode_from_string(std::string_view);
PrivacyClass        privacy_class_from_string(std::string_view);
EngramRetentionMode engram_retention_mode_from_string(std::string_view);

}  // namespace starling::schema
