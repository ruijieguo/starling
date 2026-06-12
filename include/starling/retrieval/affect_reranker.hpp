#pragma once
// Affect-aware Reranker(13_retrieval.md §核心算法-2):
//   score = base·(1+0.3·recency)·(1+0.4·salience)·(1+0.3·activation)
//           ·affect_consistency·(1−temporal_penalty)
// 因子全部 [0,1] 有界;affect_consistency 有 0.5 下界(情感失配降权但绝不
// 清零候选——零分会让 abstention 的 low_score 判定失真)。
#include <string>
#include <string_view>
#include <vector>

#include "starling/affect/affect_vector.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

struct QuerierAffectState {
    affect::AffectVector affect;   // 默认全零 = 中性
};

// 一行可审计打分(receipt.score_breakdown 行;retrieval_receipt.hpp include 本头)。
struct ScoreRow {
    std::string statement_id;
    double base{};
    double recency{};
    double salience{};
    double activation{};
    double affect_consistency{};
    double temporal_penalty{};
    double final_score{};
};

struct RerankCandidate {
    StatementRow row;
    double base_relevance{};   // 语义路径=cosine;结构化路径=1.0
    double salience{};         // statements.salience 列(planner SELECT 附带)
    double activation{};       // statements.activation 列
};

// 30 天半衰 e 指数;observed_at 晚于 as_of(未来)按 1.0。
double recency_factor(std::string_view observed_at_iso, std::string_view as_of_iso);
// clamp [0,1]。
double activation_level(double activation);
// v1 有界惩罚:valid_to 非空且 <= as_of → 0.3(过期降权);否则 0。
double temporal_distance_penalty(const StatementRow& row, std::string_view as_of_iso);
// 1 − L1(Δ affect)/5 映射到 [0.5, 1];"{}"/解析失败按中性向量。
double affect_consistency(std::string_view affect_json,
                          const affect::AffectVector& querier);

// 原地按 final_score 降序排序 cands,返回同序 breakdown。
std::vector<ScoreRow> rerank(std::vector<RerankCandidate>& cands,
                             const QuerierAffectState& querier,
                             std::string_view as_of_iso);

}  // namespace starling::retrieval
