#pragma once

#include <string>

namespace starling::retrieval {

// Subset of statements columns returned by basic_retrieve in P1. Anything
// the §14.1 smoke + filter tests don't read is excluded; adding columns
// later requires bumping the SELECT in basic_retriever.cpp.
struct StatementRow {
    std::string id;
    std::string tenant_id;
    std::string holder_id;
    std::string holder_perspective;
    std::string subject_kind;
    std::string subject_id;
    std::string predicate;
    std::string object_kind;
    std::string object_value;
    std::string canonical_object_hash;
    std::string modality;
    std::string polarity;
    double      confidence{};
    std::string observed_at;
    std::string valid_from;          // "" if NULL
    std::string valid_to;            // "" if NULL
    std::string consolidation_state; // "consolidated" | "archived"
    std::string review_status;
    std::string evidence_json;       // raw JSON array of EvidenceRef-like dicts
    std::string affect_json;         // raw affect JSON ("{}" if absent); P2.e
};

}  // namespace starling::retrieval
