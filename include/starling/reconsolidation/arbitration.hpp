#pragma once
#include "starling/persistence/connection.hpp"
#include <string>
#include <string_view>

namespace starling::reconsolidation {

enum class ArbitrationPath { Supports, MildContradict, SevereContradict };

struct Aggregated {
    ArbitrationPath path;
    double strength;          // [0,1]
    std::string summary_hash;
};

// 取窗口 pending_evidence 最近 50 条高权重 + 其余背景统计 → 判定路径.
// 路径阈值 (M0.8): strength < 0.3 → Supports; [0.3,0.7] → MildContradict; > 0.7 → SevereContradict.
Aggregated aggregate_evidence(persistence::Connection& conn, std::string_view stmt_id);

// supports: confidence 上调 → CONSOLIDATED → emit statement.consolidated.
void apply_supports(persistence::Connection& conn, std::string_view stmt_id,
                    std::string_view tenant_id, const Aggregated& agg, std::string_view now_iso);

// mild contradict: confidence 下调 + 追加 confidence_history, PROVENANCE 不变
//                  → CONSOLIDATED → emit statement.consolidated (不 emit corrected).
void apply_mild_contradict(persistence::Connection& conn, std::string_view stmt_id,
                           std::string_view tenant_id, const Aggregated& agg, std::string_view now_iso);

double bayesian_update_up(double conf, double strength);
double bayesian_update_down(double conf, double strength);

}  // namespace starling::reconsolidation
