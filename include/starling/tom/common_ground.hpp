#pragma once

#include "starling/persistence/sqlite_adapter.hpp"

#include <string>
#include <string_view>
#include <vector>

namespace starling::tom {

// CommonGroundEntry mirrors one row from the common_ground table (migration
// 0010). P2.j: populated by CommonGroundSubscriber (assert/acknowledge/repair),
// read back by common_ground::query.
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

// Returns all active common-ground entries (grounded/asserted_unack/
// suspected_diverge) shared between self_id and target_id for the given tenant,
// as of as_of_iso8601. P2.j: real read (populated by CommonGroundSubscriber).
std::vector<CommonGroundEntry> query(
    persistence::SqliteAdapter& adapter,
    std::string_view self_id,
    std::string_view target_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601);

}  // namespace common_ground

}  // namespace starling::tom
