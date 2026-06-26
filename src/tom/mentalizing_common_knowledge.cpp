// is_common_knowledge: common knowledge among a group G. X's current state is CK
// among G iff the LATEST theme-event any member of G perceived was co-witnessed by
// ALL of G (public establishment). Reuses the source_event_id co-witness intersection
// of what_does_X_think_chain, scoped to the perceptions of G's members.
#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/name_resolver.hpp"
#include "starling/schema/normalize_theme.hpp"
#include "starling/store/perception_state_store.hpp"

#include <algorithm>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace starling::tom::mentalizing {

CommonKnowledgeResult is_common_knowledge(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& group,
    // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of) {
    (void)frontier;  // parity with what_does_X_think_chain (reserved for access checks)
    CommonKnowledgeResult out;
    if (group.empty()) {
        return out;
    }

    auto& conn = adapter.connection();
    const std::string theme_n = schema::normalize_theme(theme);
    cognizer::CognizerHub hub(adapter);
    std::vector<std::string> group_n;
    group_n.reserve(group.size());
    for (const auto& member : group) {
        group_n.push_back(cognizer::resolve_cognizer(hub, tenant, member));
    }

    store::PerceptionStateStore perc(conn);
    const std::string dim = perc.dim_for_theme(tenant, theme_n, as_of);
    if (dim.empty()) {
        return out;  // theme never perceived
    }

    // Per-member set of perceived source_event_ids (this dim only); plus the group's
    // highest-position event (g_max) and a position/value lookup per event.
    std::vector<std::unordered_set<std::string>> member_sets;
    member_sets.reserve(group_n.size());
    std::unordered_map<std::string, std::pair<long long, std::string>> event_info;
    long long g_max_pos = -1;
    std::string g_max_event;

    for (const auto& member : group_n) {
        auto rows = perc.perceived_for_theme(tenant, member, theme_n, as_of);
        std::unordered_set<std::string> seen;
        for (const auto& row : rows) {
            if (row.state_dim != dim) {
                continue;
            }
            seen.insert(row.source_event_id);
            event_info[row.source_event_id] = {row.position, row.state_value};
            if (row.position > g_max_pos) {
                g_max_pos = row.position;
                g_max_event = row.source_event_id;
            }
        }
        member_sets.push_back(std::move(seen));
    }
    if (g_max_event.empty()) {
        return out;  // no member perceived the theme in this dim
    }

    auto co_witnessed_by_all = [&member_sets](const std::string& event_id) {
        return std::ranges::all_of(member_sets, [&event_id](const auto& seen) {
            return seen.contains(event_id);
        });
    };

    // is_ck: the group's latest theme-event was co-witnessed by ALL members.
    out.is_ck = co_witnessed_by_all(g_max_event);

    // ck_value / establishing: the highest-position event co-witnessed by all of G
    // (the last public establishment; == g_max when is_ck).
    long long cw_max_pos = -1;
    for (const auto& [event_id, info] : event_info) {
        if (info.first > cw_max_pos && co_witnessed_by_all(event_id)) {
            cw_max_pos = info.first;
            out.ck_value = info.second;
            out.establishing_event_id = event_id;
        }
    }
    return out;
}

}  // namespace starling::tom::mentalizing
