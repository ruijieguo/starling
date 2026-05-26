#pragma once
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom::depth_estimator {

// Count nesting_depth=1 statements held by partner in last 7 days.
// Returns >=3 -> 2; 1-2 -> 1; 0 -> 0.
// Caches result in tom_depth_estimator_cache; cache TTL 1h from last_recomputed_at.
int estimate(
    persistence::Connection& conn,
    std::string_view partner_cognizer_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601);

}  // namespace starling::tom::depth_estimator
