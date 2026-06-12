// Affect-aware Reranker(13_retrieval.md §核心算法-2)。钉:四因子各自的
// 边界值、五因子乘法的次序反转、breakdown 与排序对齐。全确定性零 IO。
#include "starling/retrieval/affect_reranker.hpp"

#include <gtest/gtest.h>

#include <cmath>

namespace starling::retrieval {

namespace {
StatementRow row(const char* id, const char* observed_at,
                 const char* valid_to = "", const char* affect = "{}") {
    StatementRow r;
    r.id = id; r.observed_at = observed_at; r.valid_to = valid_to;
    r.affect_json = affect;
    return r;
}
}  // namespace

TEST(AffectReranker, FactorBounds) {
    // recency:同刻=1;30 天≈e^-1;负龄按 0 龄处理(=1)。
    EXPECT_DOUBLE_EQ(recency_factor("2026-06-12T00:00:00Z", "2026-06-12T00:00:00Z"), 1.0);
    EXPECT_NEAR(recency_factor("2026-05-13T00:00:00Z", "2026-06-12T00:00:00Z"),
                std::exp(-1.0), 1e-9);
    EXPECT_DOUBLE_EQ(recency_factor("2026-07-01T00:00:00Z", "2026-06-12T00:00:00Z"), 1.0);
    // activation clamp。
    EXPECT_DOUBLE_EQ(activation_level(-0.5), 0.0);
    EXPECT_DOUBLE_EQ(activation_level(0.4), 0.4);
    EXPECT_DOUBLE_EQ(activation_level(2.0), 1.0);
    // temporal penalty:窗内 0;valid_to 已过 0.3。
    EXPECT_DOUBLE_EQ(temporal_distance_penalty(row("a", "2026-06-01T00:00:00Z"),
                                               "2026-06-12T00:00:00Z"), 0.0);
    EXPECT_DOUBLE_EQ(temporal_distance_penalty(
        row("b", "2026-06-01T00:00:00Z", "2026-06-10T00:00:00Z"),
        "2026-06-12T00:00:00Z"), 0.3);
    // affect_consistency:双中性=1;最大差异→0.5 下界。
    affect::AffectVector neutral{};
    EXPECT_DOUBLE_EQ(affect_consistency("{}", neutral), 1.0);
    affect::AffectVector hot{}; hot.valence = 1.0f; hot.arousal = 1.0f;
    hot.dominance = 1.0f; hot.novelty = 1.0f; hot.stakes = 1.0f;
    EXPECT_NEAR(affect_consistency("{}", hot), 0.5, 1e-9);
}

TEST(AffectReranker, RerankOrdersAndBreakdownAligns) {
    // 同 base 下,高 salience+新近者必须排前;breakdown 与输出同序同 id。
    std::vector<RerankCandidate> cands;
    cands.push_back({row("old-dull", "2026-01-01T00:00:00Z"), 0.8, 0.0, 0.0});
    cands.push_back({row("new-hot",  "2026-06-11T00:00:00Z"), 0.8, 0.9, 0.5});
    QuerierAffectState q{};  // 中性
    const auto breakdown = rerank(cands, q, "2026-06-12T00:00:00Z");
    ASSERT_EQ(cands.size(), 2u);
    ASSERT_EQ(breakdown.size(), 2u);
    EXPECT_EQ(cands[0].row.id, "new-hot");
    EXPECT_EQ(breakdown[0].statement_id, "new-hot");
    EXPECT_GT(breakdown[0].final_score, breakdown[1].final_score);
    // 公式抽查:final = base·(1+0.3r)·(1+0.4s)·(1+0.3a)·affect·(1-penalty)
    const auto& b = breakdown[0];
    EXPECT_NEAR(b.final_score,
                b.base * (1 + 0.3 * b.recency) * (1 + 0.4 * b.salience)
                       * (1 + 0.3 * b.activation) * b.affect_consistency
                       * (1 - b.temporal_penalty), 1e-9);
}

}  // namespace starling::retrieval
