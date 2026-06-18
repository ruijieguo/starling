// sub-project B phase 1 Task 1.3: what_does_X_think 实现(第 8 个 mentalizing 原语)。
// phase 1:仅 location 维、一阶。读 perception_state.last_known 得 X 最后感知的状态,
// 与 PerceptionStateStore.latest_actual(B 自有,observed_at<=as_of,NULL-free)比较得 is_stale。
// observer 分支(二阶交集)与 content 维推断分别留给 phase 3 / phase 4。
#include "starling/tom/mentalizing.hpp"
#include "starling/store/perception_state_store.hpp"
#include <optional>
#include <string>
namespace starling::tom::mentalizing {
StateBelief what_does_X_think(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view x, std::string_view theme,
    std::string_view tenant, std::string_view as_of,
    std::string_view observer) {
    (void)frontier;  // reserved for does_X_know-aligned access checks (phase 5)
    auto& conn = adapter.connection();
    store::PerceptionStateStore ps(conn);
    StateBelief out;
    // phase 1: location dimension only (phase 4 infers content vs location from the theme's events).
    const std::string dim = "location";
    std::optional<store::PerceptionStateRow> row;
    if (observer.empty()) {
        row = ps.last_known(tenant, x, theme, dim, as_of);   // first-order
    } else {
        // phase 3 replaces this with the observer∩x intersection.
        row = ps.last_known(tenant, x, theme, dim, as_of);
    }
    if (!row) return out;  // has_belief stays false
    out.has_belief = true;
    out.state_dim = row->state_dim;
    out.state_value = row->state_value;
    out.source_event_id = row->source_event_id;
    // Ground truth: highest-position non-empty located state across ALL cognizers,
    // bounded by observed_at <= as_of. B-owned, NULL-free by construction (reconstructor
    // skips empty locations). Fixes: (1) as_of-bounded; (2) no NULL-location pollution.
    const std::string truth = ps.latest_actual(tenant, theme, dim, as_of);
    out.is_stale = (!truth.empty() && truth != out.state_value);
    return out;
}
}  // namespace starling::tom::mentalizing
