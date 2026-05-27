#pragma once

#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/statement_row.hpp"

#include <string>
#include <string_view>
#include <vector>

namespace starling::tom::mentalizing {

// ─── PODs ────────────────────────────────────────────────────────────────────

// Identifies a specific fact without knowing who holds it.
struct FactKey {
    std::string subject_kind;
    std::string subject_id;
    std::string predicate;
    std::string canonical_object_hash;
};

// Result of does_X_know.
enum class KnowsResult {
    FullKnowledge,  // X has asserted the fact with polarity=pos
    NotKnown,       // X hasn't asserted it, but visible evidence suggests they could
    Unknowable,     // No visible evidence path to the fact
};

// Result of find_misalignment.
struct Misalignment {
    std::vector<retrieval::StatementRow> only_x_believes;
    std::vector<retrieval::StatementRow> only_y_believes;
    // Pairs where same (predicate, canonical_object_hash) but |conf_x - conf_y| > 0.3
    std::vector<std::pair<retrieval::StatementRow, retrieval::StatementRow>> confidence_diverges;
};

// One fact believed by all queried members.
struct SharedFact {
    std::string subject_kind;
    std::string subject_id;
    std::string predicate;
    std::string canonical_object_hash;
    std::string polarity;
    std::vector<std::string> source_statement_ids;
};

// ─── Free functions ───────────────────────────────────────────────────────────

// 1. Returns all statements held by cognizer X about subject Y (subject_kind='cognizer').
// Optional modality_filter: if non-empty, adds AND modality = modality_filter.
std::vector<retrieval::StatementRow> what_does_X_believe(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view about_y,
    std::string_view tenant,
    std::string_view as_of,
    std::string_view modality_filter = "");

// 2. Tri-valued know query: FullKnowledge / NotKnown / Unknowable.
KnowsResult does_X_know(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view x,
    const FactKey& fact_key,
    std::string_view tenant,
    std::string_view as_of);

// 3. Finds belief misalignments between X and Y about (subject_kind, subject_id).
Misalignment find_misalignment(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view subject_kind,
    std::string_view subject_id,
    std::string_view tenant,
    std::string_view as_of);

// 4. Returns facts believed by ALL members in member_cognizer_ids.
std::vector<SharedFact> shared_with(
    persistence::SqliteAdapter& adapter,
    const std::vector<std::string>& member_cognizer_ids,
    std::string_view tenant,
    std::string_view as_of);

}  // namespace starling::tom::mentalizing
