#pragma once
#include "starling/persistence/connection.hpp"
#include <optional>
#include <string>
#include <string_view>
#include <vector>
namespace starling::store {
struct PerceptionStateRow {
    std::string tenant_id, cognizer_id, theme_id, state_dim, state_value, observed_at;
    long long position = 0;
    std::string source_event_id;
};
class PerceptionStateStore {
public:
    explicit PerceptionStateStore(persistence::Connection& conn);
    // Idempotent on (tenant_id, cognizer_id, source_event_id).
    void upsert(const PerceptionStateRow& row);
    // Highest-position row with observed_at <= as_of for (cognizer, theme, dim); nullopt if none.
    std::optional<PerceptionStateRow> last_known(
        std::string_view tenant, std::string_view cognizer,
        std::string_view theme, std::string_view state_dim, std::string_view as_of);
    // All rows a cognizer perceived for a theme (any dim) with observed_at <= as_of, ordered by position.
    // (Used by the phase-3 observer intersection.)
    std::vector<PerceptionStateRow> perceived_for_theme(
        std::string_view tenant, std::string_view cognizer,
        std::string_view theme, std::string_view as_of);
    // Highest-position state_value for a theme+dim across ALL cognizers (ground truth),
    // bounded by observed_at <= as_of; "" if none. perception_state only ever holds
    // non-empty located states (the reconstructor skips empty locations) and the actor
    // of every located event is a witness, so this equals the latest asserted state.
    std::string latest_actual(std::string_view tenant, std::string_view theme,
                              std::string_view state_dim, std::string_view as_of);
    // The state dimension a theme is tracked in: "content" if any content-dim row
    // exists for the theme (observed_at <= as_of), else "location" if any location
    // row, else "" (the theme was never perceived). content sorts first.
    std::string dim_for_theme(std::string_view tenant, std::string_view theme,
                              std::string_view as_of);
private:
    persistence::Connection& conn_;
};
}  // namespace starling::store
