#ifndef STARLING_GOVERNANCE_CAPABILITY_POLICY_HPP
#define STARLING_GOVERNANCE_CAPABILITY_POLICY_HPP

#include <array>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

// The 7 hard capabilities required by the local-store profile (was runtime.py:19-27).
inline constexpr std::array<std::string_view, 7> kLocalStoreRequired = {
    "transactional_outbox", "consumer_checkpoint", "engram_per_record_key",
    "c_plus_plus_core", "cross_partition_transaction",
    "tenant_isolation_storage_enforced", "testing_helper_marker"};

// Capabilities waived in embedded mode (was runtime.py:36 _EMBEDDED_DEFERRED_CAPS).
inline constexpr std::array<std::string_view, 2> kEmbeddedDeferredCaps = {
    "engram_per_record_key", "testing_helper_marker"};

// Effective required-list for a profile. Pure: no global mutation
// (replaces runtime.py relax_preflight_for_embedded's global rewrite).
std::vector<std::string> required_capabilities(bool embedded);

}  // namespace starling::governance

#endif
