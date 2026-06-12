#include "starling/retrieval/abstention.hpp"

namespace starling::retrieval {

std::string evaluate_abstention(const AbstentionInput& in,
                                const AbstentionConfig& cfg) {
    if (in.frontier_denied)         return "frontier_deny";
    if (in.only_recanted_evidence)  return "only_recanted";
    if (in.unresolved_conflict)     return "conflict_unresolved";
    if (!in.any_candidates || in.max_score < cfg.tau_recall) return "low_score";
    return "";
}

}  // namespace starling::retrieval
