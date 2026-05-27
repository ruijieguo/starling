#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace starling::retrieval {

// Four-state sufficiency per docs/design/subsystems_design/13_retrieval.md
// §"RetrievalReceipt 合法性约束".
enum class Sufficiency {
    SUFFICIENT,
    MISSING_INFO,
    NEEDS_RAW,
    ABSTAINED,
};

struct FilterApplied {
    std::string name;
    std::string value;
};

// P1-minimum RetrievalReceipt. Spec lists ~25 fields, but P1 mandates only
// the six below (13_retrieval.md §"RetrievalReceipt（P1 最小字段加粗）").
// Future milestones add scope_plan / plan_steps / score_breakdown / etc.
struct RetrievalReceipt {
    std::string trace_id;
    std::string query_id;
    std::vector<FilterApplied> filters_applied;

    struct CandidateCounts {
        std::int64_t fetched{};
        std::int64_t returned{};
        std::int64_t dropped_by_review{};
        std::int64_t dropped_by_state{};
        std::int64_t dropped_by_time_anchor{};
        std::int64_t dropped_by_evidence_erasure{};
    } candidate_counts;

    std::int64_t evidence_erased_count{};
    // P2.a: count of rows filtered out by apply_frontier_filter. Zero when
    // apply_frontier_filter == false.
    std::int64_t frontier_masked_count{};
    Sufficiency  sufficiency_status{Sufficiency::ABSTAINED};
};

}  // namespace starling::retrieval
