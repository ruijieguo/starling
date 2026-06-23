// what_does_X_think_chain — arbitrary multi-order perception ToM. Generalizes the
// order-2 observer intersection in mentalizing_think.cpp:42-53: holder = chain.back(),
// observers = the rest; the answer is the holder's highest-position perceived state
// among events that EVERY observer also perceived. N=1 -> first-order last_known.
#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/name_resolver.hpp"
#include "starling/schema/normalize_theme.hpp"
#include "starling/store/perception_state_store.hpp"

#include <optional>
#include <string>
#include <unordered_set>
#include <vector>

namespace starling::tom::mentalizing {

StateBelief what_does_X_think_chain(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& chain,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of) {
    (void)frontier;  // parity with what_does_X_think (reserved for access checks)
    StateBelief out;
    if (chain.empty()) return out;

    auto& conn = adapter.connection();
    const std::string theme_n = schema::normalize_theme(theme);  // match the write side
    cognizer::CognizerHub hub(adapter);                          // query-side lookup-only
    std::vector<std::string> chain_n;
    chain_n.reserve(chain.size());
    for (const auto& c : chain) chain_n.push_back(cognizer::resolve_cognizer(hub, tenant, c));

    store::PerceptionStateStore ps(conn);
    const std::string dim = ps.dim_for_theme(tenant, theme_n, as_of);
    if (dim.empty()) return out;  // theme never perceived

    const std::string& holder = chain_n.back();
    std::optional<store::PerceptionStateRow> row;
    if (chain_n.size() == 1) {
        row = ps.last_known(tenant, holder, theme_n, dim, as_of);   // first-order
    } else {
        // Each observer's perceived-event-id set for the theme.
        std::vector<std::unordered_set<std::string>> obs_sets;
        obs_sets.reserve(chain_n.size() - 1);
        for (std::size_t i = 0; i + 1 < chain_n.size(); ++i) {
            auto rows = ps.perceived_for_theme(tenant, chain_n[i], theme_n, as_of);
            std::unordered_set<std::string> s;
            for (const auto& r : rows) s.insert(r.source_event_id);
            obs_sets.push_back(std::move(s));
        }
        // Holder's highest-position row whose event every observer also perceived.
        auto h_rows = ps.perceived_for_theme(tenant, holder, theme_n, as_of);
        for (auto it = h_rows.rbegin(); it != h_rows.rend(); ++it) {
            if (it->state_dim != dim) continue;
            bool in_all = true;
            for (const auto& s : obs_sets) {
                if (!s.count(it->source_event_id)) { in_all = false; break; }
            }
            if (in_all) { row = *it; break; }
        }
    }
    if (!row) return out;
    out.has_belief = true;
    out.state_dim = row->state_dim;
    out.state_value = row->state_value;
    out.source_event_id = row->source_event_id;
    const std::string truth = ps.latest_actual(tenant, theme_n, dim, as_of);
    out.is_stale = (!truth.empty() && truth != out.state_value);
    return out;
}

}  // namespace starling::tom::mentalizing
