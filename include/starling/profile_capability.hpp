#pragma once

#include <string>

namespace starling {

// Capability declaration produced by every Adapter at startup.
// Source of truth: subsystems_design/04_substrate.md "Capability 声明".
// Defaults are intentionally fail-closed (all bools false, strings empty).
struct ProfileCapability {
    std::string profile_name;

    std::string relational_backend;
    std::string vector_backend;
    std::string graph_backend;

    bool c_plus_plus_core = false;

    bool cross_partition_transaction = false;
    bool transactional_outbox = false;
    bool consumer_checkpoint = false;

    std::string tenant_isolation;  // "app_filter" | "storage_enforced"

    bool engram_per_record_key = false;
    bool engram_refcount = false;

    bool projection_index_supported = false;
    bool dimension_versions_supported = false;

    bool testing_helper_marker = false;
};

}  // namespace starling
