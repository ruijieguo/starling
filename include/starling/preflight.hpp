#pragma once

#include <string>
#include <vector>

#include "starling/profile_capability.hpp"

namespace starling {

// Result enum for preflight: a binary READY / UNREADY decision. Caller is
// expected to wire UNREADY into RuntimeHealth + an EX_CONFIG (78) exit per
// system_design.md §15.3.4 TC-NEW-PREFLIGHT.
enum class PreflightStatus {
    READY,
    UNREADY,
};

// Result of a preflight check.
//
// `missing` preserves the order of the `required` argument passed to
// `preflight()` and contains every requirement that was not satisfied,
// including capability names not recognized by the matcher. UNREADY iff
// `missing` is non-empty.
struct PreflightResult {
    PreflightStatus status;
    std::vector<std::string> missing;
};

// Capability requirement names recognized by preflight (string-keyed for ease of
// listing in config + future extensibility):
//
//   "c_plus_plus_core"                         -> ProfileCapability::c_plus_plus_core
//   "cross_partition_transaction"              -> ProfileCapability::cross_partition_transaction
//   "transactional_outbox"                     -> ProfileCapability::transactional_outbox
//   "consumer_checkpoint"                      -> ProfileCapability::consumer_checkpoint
//   "tenant_isolation_storage_enforced"        -> tenant_isolation == "storage_enforced"
//   "engram_per_record_key"                    -> ProfileCapability::engram_per_record_key
//   "engram_refcount"                          -> ProfileCapability::engram_refcount
//   "projection_index_supported"               -> P2 only
//   "dimension_versions_supported"             -> P3 only
//   "testing_helper_marker"                    -> testing_helper_marker
//
// Unknown capability names are treated as missing (fail-closed): a typo in a
// required capability list MUST cause the runtime to refuse READY rather than
// silently skip the requirement.
PreflightResult preflight(const ProfileCapability& declared,
                          const std::vector<std::string>& required);

}  // namespace starling
