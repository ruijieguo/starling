#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "starling/retrieval/affect_reranker.hpp"   // ScoreRow
#include "starling/retrieval/retrieval_scope.hpp"   // RetrievalScopePlan

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

    // ── P3.a1 planner 字段(默认空;P1 basic_retrieve 路径不填,旧钉测不变)──
    struct PlanStepTrace { std::string step; std::string detail; };
    struct SkippedScope  { std::string scope; std::string reason; std::string stop_policy; };
    struct DegradedPath  { std::string path;  std::string reason; std::string fallback; };

    std::string querier;
    std::string perspective;
    std::string intent_name;                       // to_string(intent)
    std::string runtime_health{"READY"};           // 调用方注入(Python runtime 知情方)
    std::string trace_retention{"metadata_only"};
    RetrievalScopePlan scope_plan;                 // plan_id 空 = 未走 planner
    std::vector<PlanStepTrace> plan_steps;         // 7 步各一行
    std::vector<SkippedScope> skipped_scopes;      // progressive 跳过的 scope
    std::string stop_reason;
    std::vector<std::string> scopes_searched;
    std::vector<ScoreRow> score_breakdown;
    std::vector<DegradedPath> degraded_paths;
    std::string abstention_reason;                 // ""=未拒答
    std::vector<std::string> emitted_events;       // statement.recalled 事件 id
    std::int64_t projection_lag_events{};          // outbox 头 − 最慢消费者 checkpoint
};

}  // namespace starling::retrieval
