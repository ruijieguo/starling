#pragma once

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <string>
#include <string_view>
#include <unordered_set>
#include <vector>

namespace starling::cognizer {

class KnowledgeFrontier {
public:
    explicit KnowledgeFrontier(persistence::SqliteAdapter& adapter);

    // 5 record APIs — each inserts into cognizer_presence_log (1) or
    // cognizer_frontier_facts (2-5). Idempotent on (tenant, cognizer,
    // statement/engram, fact_kind) — duplicate records are silently
    // skipped via INSERT OR IGNORE on a synthesized stable id.

    // 1/5: presence_log entry per perceived_by cognizer.
    void record_presence_from_statement(
        std::string_view tenant_id,
        const std::vector<std::string>& perceived_by,
        std::string_view engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // 2/5: explicit_told for each perceived_by, anchored to a statement.
    void record_explicit_told(
        std::string_view tenant_id,
        const std::vector<std::string>& perceived_by,
        std::string_view statement_id,
        std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // 3/5: accessible_source (cognizer can read this adapter's data).
    void record_accessible_source(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view adapter_name,
        std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // 4/5: group_membership (cognizer belongs to group_id; expressed via
    // metadata_json={"group_id": ...}).
    void record_group_membership(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view group_id,
        std::string_view at_iso8601,
        persistence::Connection& conn);

    // 5/5: explicit_not_told (cognizer was specifically NOT told a fact).
    void record_explicit_negation(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view referenced_statement_id,
        std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // Query (Task 9).
    std::unordered_set<std::string> visible_engrams_at(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view as_of_iso8601) const;

private:
    [[maybe_unused]] persistence::SqliteAdapter& adapter_;  // used by Task 9 visible_engrams_at
};

}  // namespace starling::cognizer
