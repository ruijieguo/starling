#include "starling/evidence/ingest_policy_resolver.hpp"

namespace starling::evidence {

schema::IngestPolicy IngestPolicyResolver::resolve(
    schema::SourceKind source_kind,
    schema::PrivacyClass privacy_class,
    schema::IngestPolicy producer_declared) {
    using SK = schema::SourceKind;
    using PC = schema::PrivacyClass;
    using IP = schema::IngestPolicy;

    // Producer-declared NO_STORE is always honored.
    if (producer_declared == IP::NO_STORE) return IP::NO_STORE;

    // Self-pollution guard: these source kinds are always NO_STORE regardless
    // of producer intent or privacy_class. §3.7 line 1094.
    if (source_kind == SK::SYSTEM_INTERNAL ||
        source_kind == SK::OBSERVER_AGENT  ||
        source_kind == SK::REPLAY_OUTPUT) {
        return IP::NO_STORE;
    }

    // Producer-declared REQUIRE_REVIEW or STORE_METADATA_ONLY are honored as
    // explicit downgrades (producer knows something the table doesn't).
    if (producer_declared == IP::REQUIRE_REVIEW ||
        producer_declared == IP::STORE_METADATA_ONLY) {
        return producer_declared;
    }

    // From here, producer_declared == STORE.
    // tool_observation always downgrades STORE to STORE_METADATA_ONLY (§3.7).
    if (source_kind == SK::TOOL_OBSERVATION) {
        return IP::STORE_METADATA_ONLY;
    }

    // Privacy-driven downgrades for user_input / external_doc.
    if (privacy_class == PC::REGULATED) {
        // Regulated always needs human review before being treated as STORE.
        return IP::REQUIRE_REVIEW;
    }
    if (source_kind == SK::EXTERNAL_DOC && privacy_class == PC::SENSITIVE) {
        return IP::REQUIRE_REVIEW;
    }

    return IP::STORE;
}

}  // namespace starling::evidence
