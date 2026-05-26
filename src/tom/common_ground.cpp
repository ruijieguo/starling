#include "starling/tom/common_ground.hpp"

namespace starling::tom::common_ground {

// P2.a stub: returns [] per spec §7.2 step 3. P2.b adds the Grounding Acts
// writer.
std::vector<CommonGroundEntry> query(
    [[maybe_unused]] persistence::SqliteAdapter& adapter,
    [[maybe_unused]] std::string_view self_id,
    [[maybe_unused]] std::string_view target_id,
    [[maybe_unused]] std::string_view tenant_id,
    [[maybe_unused]] std::string_view as_of_iso8601)
{
    return {};
}

}  // namespace starling::tom::common_ground
