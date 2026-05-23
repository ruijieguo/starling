#pragma once

#include "starling/schema/enums.hpp"

namespace starling::evidence {

// Pure function; no state. Implements the §3.7 IngestPolicy resolution table:
//
//   user_input                   → STORE   (regulated → REQUIRE_REVIEW)
//   external_doc                 → STORE   (sensitive/regulated → REQUIRE_REVIEW)
//   tool_observation             → STORE_METADATA_ONLY (always downgraded)
//   system_internal              → NO_STORE  ← self-pollution guard
//   observer_agent               → NO_STORE  ← self-pollution guard
//   replay_output                → NO_STORE  ← self-pollution guard
//
// Producer-declared NO_STORE is always honored (producer can refuse storage
// for any source_kind; resolver never promotes NO_STORE).
//
// privacy_class can DOWNGRADE the result (REGULATED on user_input → REQUIRE_REVIEW)
// but CANNOT upgrade NO_STORE to STORE. Self-pollution beats privacy beats
// producer intent.
class IngestPolicyResolver {
public:
    static schema::IngestPolicy resolve(
        schema::SourceKind source_kind,
        schema::PrivacyClass privacy_class,
        schema::IngestPolicy producer_declared);
};

}  // namespace starling::evidence
