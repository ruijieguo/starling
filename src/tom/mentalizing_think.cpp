// sub-project B phase 1 Task 1.3: what_does_X_think 实现(第 8 个 mentalizing 原语)。
// phase 1:仅 location 维、一阶。读 perception_state.last_known 得 X 最后感知的状态,
// 与 PerceptionStateStore.latest_actual(B 自有,observed_at<=as_of,NULL-free)比较得 is_stale。
// phase 3:observer 分支 — 二阶交集:取 observer 与 x 均感知的 source_event_id 集合,
//         选最高 position(rbegin)的匹配 dim 行 → observer 对 x 的心智模型。
// content 维推断留给 phase 4。
#include "starling/tom/mentalizing.hpp"
#include "starling/store/perception_state_store.hpp"
#include <optional>
#include <string>
#include <unordered_set>
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
    // phase 4: infer the dimension the theme is tracked in — "content" if the theme
    // has any content-dim perception (a closed labelled container that was seen/opened),
    // else "location". "" → the theme was never perceived → has_belief stays false.
    const std::string dim = ps.dim_for_theme(tenant, theme, as_of);
    if (dim.empty()) return out;
    std::optional<store::PerceptionStateRow> row;
    if (observer.empty()) {
        row = ps.last_known(tenant, x, theme, dim, as_of);   // first-order
    } else {
        // observer's model of x: events both perceived (single-scene co-presence).
        auto x_rows   = ps.perceived_for_theme(tenant, x, theme, as_of);
        auto obs_rows = ps.perceived_for_theme(tenant, observer, theme, as_of);
        std::unordered_set<std::string> obs_events;
        for (const auto& r : obs_rows) obs_events.insert(r.source_event_id);
        for (auto it = x_rows.rbegin(); it != x_rows.rend(); ++it) {   // highest position first
            if (it->state_dim == dim && obs_events.count(it->source_event_id)) { row = *it; break; }
        }
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
