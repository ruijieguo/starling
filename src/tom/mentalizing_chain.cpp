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
#include <set>
#include <string>
#include <unordered_set>
#include <vector>
#include <sqlite3.h>
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

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
        // Observation-primacy (nested-belief chain only):
        // tell/inform events are HEARSAY — the reconstructor writes a perception_state
        // row for each recipient, but these rows represent what the agent was TOLD, not
        // what they first-hand OBSERVED. When an agent has at least one real observation,
        // hearsay must NOT override it. Hearsay is used only as a fallback to fill gaps
        // (an agent who was never physically present and was only ever told).
        //
        // Build the set of statement ids for all tell/inform OCCURRED events in the
        // tenant. Any perception_state row whose source_event_id is in this set is hearsay.
        std::set<std::string> reported_ids;
        {
            sqlite3* raw_db = conn.raw();
            const char* sql =
                "SELECT id FROM statements "
                "WHERE tenant_id=? AND modality='occurred' "
                "AND predicate IN ('tell','inform')";
            sqlite3_stmt* raw_stmt = nullptr;
            if (sqlite3_prepare_v2(raw_db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
                throw persistence::detail::make_sqlite_error(raw_db, "what_does_X_think_chain: reported_ids prepare");
            }
            persistence::StmtHandle stmt_handle(raw_stmt);
            persistence::detail::bind_sv(stmt_handle.get(), 1, tenant);
            int step_rc = 0;
            while ((step_rc = sqlite3_step(stmt_handle.get())) == SQLITE_ROW) {
                const auto* id_text = sqlite3_column_text(stmt_handle.get(), 0);
                if (id_text != nullptr) {
                    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
                    reported_ids.insert(reinterpret_cast<const char*>(id_text));
                }
            }
            if (step_rc != SQLITE_DONE) {
                throw persistence::detail::make_sqlite_error(raw_db, "what_does_X_think_chain: reported_ids step");
            }
        }

        // Each observer's co-witness set: only the source_event_ids of events they
        // OBSERVED (non-hearsay). Observers reason from what they SAW, not what they
        // were told, so we exclude reported (tell/inform) rows here.
        std::vector<std::unordered_set<std::string>> obs_sets;
        obs_sets.reserve(chain_n.size() - 1);
        for (std::size_t idx = 0; idx + 1 < chain_n.size(); ++idx) {
            auto rows = ps.perceived_for_theme(tenant, chain_n[idx], theme_n, as_of);
            std::unordered_set<std::string> observed;
            for (const auto& obs_row : rows) {
                if (!reported_ids.contains(obs_row.source_event_id)) {  // exclude hearsay
                    observed.insert(obs_row.source_event_id);
                }
            }
            obs_sets.push_back(std::move(observed));
        }

        // Holder's highest-position OBSERVED (non-hearsay) row whose event every
        // observer also observed. Observation primacy: skip rows sourced from a
        // tell/inform event when the holder has any first-hand observation at all.
        auto h_rows = ps.perceived_for_theme(tenant, holder, theme_n, as_of);

        // Determine whether the holder has ANY first-hand observation (non-hearsay).
        // If ALL of the holder's rows are hearsay, fall back to considering all rows
        // (hearsay fills gaps when the holder was never physically present).
        bool holder_has_observation = false;
        for (const auto& holder_row : h_rows) {
            if (!reported_ids.contains(holder_row.source_event_id)) { holder_has_observation = true; break; }
        }

        for (auto it = h_rows.rbegin(); it != h_rows.rend(); ++it) {
            if (it->state_dim != dim) { continue; }
            // Skip hearsay rows when the holder has at least one first-hand observation.
            if (holder_has_observation && reported_ids.contains(it->source_event_id)) { continue; }
            bool in_all = true;
            for (const auto& observed_set : obs_sets) {
                if (!observed_set.contains(it->source_event_id)) { in_all = false; break; }
            }
            if (in_all) { row = *it; break; }
        }

        // Hearsay fallback: if no observed row matched the co-witness intersection
        // (e.g. the holder was only ever told), retry with all rows including hearsay
        // so a purely-told holder still yields a belief (gap-filling, not overriding).
        if (!row && !holder_has_observation) {
            // NOLINTNEXTLINE(modernize-loop-convert) -- reverse iteration is intentional (highest position first)
            for (auto it = h_rows.rbegin(); it != h_rows.rend(); ++it) {
                if (it->state_dim != dim) { continue; }
                // In fallback mode the obs_sets already exclude hearsay; a tell event
                // won't be in any observer's observed set, so we need to check the full
                // (including hearsay) observer rows to find a shared event. Re-build
                // observer sets with all rows for the fallback pass.
                bool in_all = true;
                for (std::size_t idx = 0; idx + 1 < chain_n.size(); ++idx) {
                    auto o_rows = ps.perceived_for_theme(tenant, chain_n[idx], theme_n, as_of);
                    bool found = false;
                    for (const auto& obs_row : o_rows) {
                        if (obs_row.source_event_id == it->source_event_id) { found = true; break; }
                    }
                    if (!found) { in_all = false; break; }
                }
                if (in_all) { row = *it; break; }
            }
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
