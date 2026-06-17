#pragma once
#include "starling/persistence/connection.hpp"
#include <optional>
#include <string>
#include <string_view>
#include <vector>
namespace starling::store {
struct EpisodicEventRow {
    std::string statement_id, tenant_id;
    long long seq = 0;
    std::string event_time;          // "" = NULL
    std::string location;            // "" = NULL
    std::string participants_json = "[]";
    std::string action_raw;          // "" = NULL
};
class EpisodicEventStore {
public:
    explicit EpisodicEventStore(persistence::Connection& conn);
    void upsert(const EpisodicEventRow& row);
    std::optional<EpisodicEventRow> get(std::string_view statement_id, std::string_view tenant);
    // OCCURRED events about a theme (statements.object_value), ordered by seq, then event_time.
    std::vector<EpisodicEventRow> events_for_theme(std::string_view tenant, std::string_view theme_id);
    // Highest-seq event's location for a theme (ground-truth current state), "" if none.
    std::string latest_event_location(std::string_view tenant, std::string_view theme_id);
private:
    persistence::Connection& conn_;
};
}  // namespace starling::store
