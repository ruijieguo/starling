#pragma once
// RetrievalScopeStep / RetrievalScopePlan(13_retrieval.md §数据结构)。
// scope 取值:working_set | statement_main | projection_index | semantic_index
// | graph_index | container_view | engram_evidence | tom_runtime。
#include <string>
#include <utility>
#include <vector>

namespace starling::retrieval {

struct RetrievalScopeStep {
    std::string scope;
    std::string holder_scope;            // 本步唯一 holder(多 holder 隔离契约)
    std::string group_scope;             // "" 除非群组
    std::vector<std::pair<std::string, std::string>> filters;  // name→value
    int max_candidates = 50;
    std::string on_error = "degrade";    // degrade | abstain | fail_closed
};

struct RetrievalScopePlan {
    std::string plan_id;                 // = query_id
    std::string mode = "progressive";    // basic|progressive|parallel|exhaustive
    std::vector<RetrievalScopeStep> steps;
    std::string stop_policy = "after_first_sufficient";
    std::string merge_policy = "ranked_union";
    std::string filter_mode = "per_scope_explicit";
};

}  // namespace starling::retrieval
