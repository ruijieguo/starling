#pragma once
#include <array>
#include <string_view>

namespace starling::extractor {

// Lightweight controlled predicate set (system_design §3.3 "受控核心集" — the
// P2 tier). The belief-tier core set MUST stay in sync with the vocabulary line
// in python/starling/extractor/prompts.py (EXTRACTION_PROMPT: "predicate must be
// one of: ..."). Statements with a predicate outside this set are NOT
// rejected — validate_extracted_statement downgrades them to REVIEW_REQUESTED
// so LLM-invented predicates get vetted instead of silently entering the
// approved graph (except for modality=OCCURRED rows, which keep open-domain
// action verbs verbatim; see statement_validator.cpp). Full URI governance via
// the Cognizer Hub is P3.
inline constexpr std::array<std::string_view, 10> kCoreBeliefPredicates = {
    "believes", "doubts", "forbids", "knows", "located_at",
    "member_of", "prefers", "promises", "requires", "responsible_for",
};

// Curated action predicate class (sub-project A, phase 3): common
// object-manipulation verbs used by episodic events (modality=OCCURRED,
// e.g. "Sally put ball in basket" → predicate=put). These are in-vocab so the
// common cases are NOT downgraded to REVIEW_REQUESTED. OCCURRED rows also keep
// out-of-set action verbs verbatim (open-domain); this curated list only
// suppresses review for the canonical verbs across all modalities.
inline constexpr std::array<std::string_view, 10> kActionPredicates = {
    "put", "place", "move", "take", "give",
    "remove", "transfer", "leave", "open", "close",
};

// Informational/perception predicate class (sub-project B): speech + perception
// verbs that update a cognizer's knowledge. tell/inform convey a state to a
// recipient; see/look (phase 4) read a container's apparent content.
inline constexpr std::array<std::string_view, 4> kPerceptionPredicates = {
    "tell", "inform", "see", "look",
};

// General-fact predicate class (sub-project C): attributive + relational
// predicates for arbitrary declarative world-facts ("X is a Y", quantities,
// relationships). In-vocab so general facts are approved, not REVIEW_REQUESTED.
// No overlap with kCoreBeliefPredicates (located_at/member_of/knows already core).
inline constexpr std::array<std::string_view, 8> kGeneralFactPredicates = {
    "is_a", "instance_of", "has_property", "has_value",
    "part_of", "related_to", "depends_on", "reports_to",
};

inline bool is_core_predicate(std::string_view predicate) {
    for (const auto p : kCoreBeliefPredicates) {
        if (p == predicate) return true;
    }
    for (const auto p : kActionPredicates) {
        if (p == predicate) return true;
    }
    for (const auto p : kPerceptionPredicates) {
        if (p == predicate) return true;
    }
    for (const auto p : kGeneralFactPredicates) {
        if (p == predicate) return true;
    }
    return false;
}

}  // namespace starling::extractor
