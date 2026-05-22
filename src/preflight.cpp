#include "starling/preflight.hpp"

#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "starling/profile_capability.hpp"

namespace starling {
namespace {

// Map a capability name to whether the declared ProfileCapability satisfies it.
// Returns false for unknown names (fail-closed) — a typo in the required list
// MUST surface as UNREADY rather than being silently ignored.
//
// Kept as a flat if-chain on string_view literals: the set of recognized names
// is small and changes with the ProfileCapability struct itself, so a hash map
// would add machinery without buying anything. Revisit in P2 if the count grows.
//
// Order follows ProfileCapability field declaration order; tenant_isolation_storage_enforced
// slots in at the position of the underlying tenant_isolation string field.
bool capability_has(const ProfileCapability& cap, std::string_view name) {
    if (name == "c_plus_plus_core") return cap.c_plus_plus_core;
    if (name == "cross_partition_transaction") return cap.cross_partition_transaction;
    if (name == "transactional_outbox") return cap.transactional_outbox;
    if (name == "consumer_checkpoint") return cap.consumer_checkpoint;
    if (name == "tenant_isolation_storage_enforced") {
        return cap.tenant_isolation == "storage_enforced";
    }
    if (name == "engram_per_record_key") return cap.engram_per_record_key;
    if (name == "engram_refcount") return cap.engram_refcount;
    if (name == "projection_index_supported") return cap.projection_index_supported;
    if (name == "dimension_versions_supported") return cap.dimension_versions_supported;
    if (name == "testing_helper_marker") return cap.testing_helper_marker;
    return false;  // unknown -> fail-closed
}

}  // namespace

PreflightResult preflight(const ProfileCapability& declared,
                          const std::vector<std::string>& required) {
    std::vector<std::string> missing;
    missing.reserve(required.size());
    for (const auto& cap_name : required) {
        if (!capability_has(declared, cap_name)) {
            missing.push_back(cap_name);
        }
    }
    if (!missing.empty()) {
        return PreflightResult{PreflightStatus::UNREADY, std::move(missing)};
    }
    return PreflightResult{PreflightStatus::READY, {}};
}

}  // namespace starling
