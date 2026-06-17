#pragma once
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom::depth_estimator {

// Estimate the ToM order a partner has demonstrated over the last 7 days.
// Reads the partner's consolidated/archived statements grouped by nesting_depth
// and returns the highest order demonstrated: a statement held at nesting_depth=d
// demonstrates order d+1, credited once the partner has >= 3 statements at that
// depth. Returns any non-negative int, monotone in the partner's maximum
// demonstrated nesting. Preserves the legacy {0,1,2} outputs for shallow
// (depth-0/1) partners: nesting_depth=1 count >=3 -> 2; 1-2 -> 1; 0 -> 0.
// Caches result in tom_depth_estimator_cache; cache TTL 1h from last_recomputed_at.
int estimate(
    persistence::Connection& conn,
    std::string_view partner_cognizer_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601);

}  // namespace starling::tom::depth_estimator
