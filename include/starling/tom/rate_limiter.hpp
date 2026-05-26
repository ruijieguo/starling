#pragma once
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom::rate_limiter {

// Returns true iff no other tom_inferred statement with same
// (tenant_id, holder_id, subject_id, predicate, canonical_object_hash)
// tuple exists with observed_at within the last 600s of the given as_of.
//
// false = write should be REJECTED (or kept as transient context).
bool allow_tom_inferred_write(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view holder_id,
    std::string_view subject_id,
    std::string_view predicate,
    std::string_view canonical_object_hash,
    std::string_view as_of_iso8601);

}  // namespace starling::tom::rate_limiter
