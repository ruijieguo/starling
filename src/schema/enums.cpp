#include "starling/schema/enums.hpp"

#include <stdexcept>
#include <string>

namespace starling::schema {

std::string_view to_string(SourceKind v) {
    switch (v) {
        case SourceKind::USER_INPUT:       return "user_input";
        case SourceKind::EXTERNAL_DOC:     return "external_doc";
        case SourceKind::TOOL_OBSERVATION: return "tool_observation";
        case SourceKind::SYSTEM_INTERNAL:  return "system_internal";
        case SourceKind::OBSERVER_AGENT:   return "observer_agent";
        case SourceKind::REPLAY_OUTPUT:    return "replay_output";
    }
    throw std::invalid_argument("unknown SourceKind value");
}

std::string_view to_string(IngestPolicy v) {
    switch (v) {
        case IngestPolicy::STORE:               return "store";
        case IngestPolicy::NO_STORE:            return "no_store";
        case IngestPolicy::STORE_METADATA_ONLY: return "store_metadata_only";
        case IngestPolicy::REQUIRE_REVIEW:      return "require_review";
    }
    throw std::invalid_argument("unknown IngestPolicy value");
}

std::string_view to_string(IngestMode v) {
    switch (v) {
        case IngestMode::CHUNKED_CONTENT: return "chunked_content";
        case IngestMode::WHOLE_RECORD:    return "whole_record";
        case IngestMode::METADATA_ONLY:   return "metadata_only";
    }
    throw std::invalid_argument("unknown IngestMode value");
}

std::string_view to_string(PrivacyClass v) {
    switch (v) {
        case PrivacyClass::PUBLIC:    return "public";
        case PrivacyClass::INTERNAL:  return "internal";
        case PrivacyClass::PERSONAL:  return "personal";
        case PrivacyClass::SENSITIVE: return "sensitive";
        case PrivacyClass::REGULATED: return "regulated";
    }
    throw std::invalid_argument("unknown PrivacyClass value");
}

std::string_view to_string(EngramRetentionMode v) {
    switch (v) {
        case EngramRetentionMode::LEGAL_HOLD:      return "legal_hold";
        case EngramRetentionMode::AUDIT_RETAIN:    return "audit_retain";
        case EngramRetentionMode::REDACTED_RETAIN: return "redacted_retain";
        case EngramRetentionMode::CRYPTO_ERASURE:  return "crypto_erasure";
    }
    throw std::invalid_argument("unknown EngramRetentionMode value");
}

SourceKind source_kind_from_string(std::string_view s) {
    if (s == "user_input")       return SourceKind::USER_INPUT;
    if (s == "external_doc")     return SourceKind::EXTERNAL_DOC;
    if (s == "tool_observation") return SourceKind::TOOL_OBSERVATION;
    if (s == "system_internal")  return SourceKind::SYSTEM_INTERNAL;
    if (s == "observer_agent")   return SourceKind::OBSERVER_AGENT;
    if (s == "replay_output")    return SourceKind::REPLAY_OUTPUT;
    throw std::invalid_argument(std::string("unknown SourceKind: ") + std::string(s));
}

IngestPolicy ingest_policy_from_string(std::string_view s) {
    if (s == "store")               return IngestPolicy::STORE;
    if (s == "no_store")            return IngestPolicy::NO_STORE;
    if (s == "store_metadata_only") return IngestPolicy::STORE_METADATA_ONLY;
    if (s == "require_review")      return IngestPolicy::REQUIRE_REVIEW;
    throw std::invalid_argument(std::string("unknown IngestPolicy: ") + std::string(s));
}

IngestMode ingest_mode_from_string(std::string_view s) {
    if (s == "chunked_content") return IngestMode::CHUNKED_CONTENT;
    if (s == "whole_record")    return IngestMode::WHOLE_RECORD;
    if (s == "metadata_only")   return IngestMode::METADATA_ONLY;
    throw std::invalid_argument(std::string("unknown IngestMode: ") + std::string(s));
}

PrivacyClass privacy_class_from_string(std::string_view s) {
    if (s == "public")    return PrivacyClass::PUBLIC;
    if (s == "internal")  return PrivacyClass::INTERNAL;
    if (s == "personal")  return PrivacyClass::PERSONAL;
    if (s == "sensitive") return PrivacyClass::SENSITIVE;
    if (s == "regulated") return PrivacyClass::REGULATED;
    throw std::invalid_argument(std::string("unknown PrivacyClass: ") + std::string(s));
}

EngramRetentionMode engram_retention_mode_from_string(std::string_view s) {
    if (s == "legal_hold")      return EngramRetentionMode::LEGAL_HOLD;
    if (s == "audit_retain")    return EngramRetentionMode::AUDIT_RETAIN;
    if (s == "redacted_retain") return EngramRetentionMode::REDACTED_RETAIN;
    if (s == "crypto_erasure")  return EngramRetentionMode::CRYPTO_ERASURE;
    throw std::invalid_argument(std::string("unknown EngramRetentionMode: ") + std::string(s));
}

}  // namespace starling::schema
