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

// severe contradict: 4 项原子提交 (仅原子事务, saga 推迟 P3):
//   1. 新版 (provenance=reconsolidation_derived, CONSOLIDATED, supersedes_id=old)
//   2. SUPERSEDES 边 (新版→旧版)
//   3. 旧版 ARCHIVED
//   4. emit statement.corrected + archived + superseded (同 outbox batch)
// 新版不 emit statement.written (防重入 Replay). 返回新版 stmt_id.
std::string apply_severe_contradict(persistence::Connection& conn,
                                    std::string_view old_stmt_id,
                                    std::string_view tenant_id,
                                    const Aggregated& agg, std::string_view now_iso);

double bayesian_update_up(double conf, double strength);
double bayesian_update_down(double conf, double strength);

}  // namespace starling::reconsolidation
