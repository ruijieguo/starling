#pragma once
#include <array>
#include <string_view>

namespace starling::extractor {

// Lightweight controlled predicate set (system_design §3.3 "受控核心集" — the
// P2 tier). MUST stay in sync with the vocabulary line in
// python/starling/extractor/prompts.py (EXTRACTION_PROMPT: "predicate must be
// one of: ..."). Statements with a predicate outside this set are NOT
// rejected — validate_extracted_statement downgrades them to REVIEW_REQUESTED
// so LLM-invented predicates get vetted instead of silently entering the
// approved graph. Full URI governance via the Cognizer Hub is P3.
inline constexpr std::array<std::string_view, 10> kCorePredicates = {
    "believes", "doubts", "forbids", "knows", "located_at",
    "member_of", "prefers", "promises", "requires", "responsible_for",
};

inline bool is_core_predicate(std::string_view predicate) {
    for (const auto p : kCorePredicates) {
        if (p == predicate) return true;
    }
    return false;
}

}  // namespace starling::extractor
