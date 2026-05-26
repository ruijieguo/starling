#pragma once

#include "starling/persistence/sqlite_adapter.hpp"

#include <string>
#include <string_view>
#include <vector>

namespace starling::tom {

// CommonGroundEntry mirrors one row from the common_ground table (migration
// 0010). In P2.a, the write path (Grounding Acts) is not yet implemented —
// common_ground::query always returns an empty vector (spec §7.2 step 3).
struct CommonGroundEntry {
    std::string id;
    std::string tenant_id;
    std::string statement_id;
    std::string status;
    std::string parties_json;  // raw JSON array of cognizer_id strings
    std::string created_at;
    std::string updated_at;
};

namespace common_ground {

// Returns all active common-ground entries shared between self_id and
// target_id for the given tenant, as of as_of_iso8601.
//
// P2.a stub: returns [] per spec §7.2 step 3. P2.b adds the Grounding Acts
// writer.
std::vector<CommonGroundEntry> query(
    persistence::SqliteAdapter& adapter,
    std::string_view self_id,
    std::string_view target_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601);

}  // namespace common_ground

}  // namespace starling::tom
