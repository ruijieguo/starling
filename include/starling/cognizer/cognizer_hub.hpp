#pragma once

#include "starling/cognizer/cognizer.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::cognizer {

class CognizerHub {
public:
    explicit CognizerHub(persistence::SqliteAdapter& adapter);

    // Register a cognizer. UUID5(kStarlingCognizerNamespace, kind+"\x1f"+external_id)
    // gives the id; same input → same id (idempotent).
    //
    // Side effects on re-registration:
    //  - last_seen_at is bumped to now-ish (uses created_at if first time)
    //  - new aliases (not in existing aliases_json) are appended; both
    //    raw and normalized forms updated
    //
    // Throws:
    //  - AliasCollision when any normalized alias points to a different
    //    cognizer
    //  - GroupTenantImplicit when kind=Group + tenant_id="default" + !tenant_explicitly_set
    Cognizer register_cognizer(const CognizerRegistration& req);

    // Returns the id of the cognizer whose normalized aliases contain
    // normalize_alias(query_alias), or std::nullopt if no match.
    std::optional<std::string> lookup_by_alias(
        std::string_view tenant_id, std::string_view query_alias) const;

    // Returns Cognizer by id, or nullopt if missing.
    std::optional<Cognizer> get(
        std::string_view id, std::string_view tenant_id) const;

    // Bumps last_seen_at. No-op if cognizer doesn't exist (Hub is best-effort
    // observer; missing cognizer means BeliefTracker is ahead of register).
    void update_last_seen_at(
        std::string_view id, std::string_view tenant_id,
        std::string_view at_iso8601);

    // Upsert RelationEdge (Task 7).
    RelationEdge upsert_relation(const RelationEdgeInput& req);

    // List relations from a, optionally filtered to active (valid_to NULL or > now).
    std::vector<RelationEdge> relations_of(
        std::string_view cognizer_id, std::string_view tenant_id) const;

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::cognizer
