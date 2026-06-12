#pragma once
// Abstention Gate(13_retrieval.md §Abstention 触发条件):四条件任一满足
// 即结构化拒答("我不知道,因为 ___"),不编造、不输出模糊"不确定"。
// reason 枚举字符串:frontier_deny | only_recanted | conflict_unresolved | low_score。
#include <string>

namespace starling::retrieval {

struct AbstentionConfig {
    double tau_recall = 0.25;   // rerank 后 max(final_score) 阈值
};

struct AbstentionInput {
    double max_score = 0.0;            // rerank 后最高分(无候选=0)
    bool any_candidates = false;
    bool frontier_denied = false;      // mask 遮蔽后候选清零(遮蔽前非零)
    bool only_recanted_evidence = false;  // 全部候选的 cg 状态 recanted
    bool unresolved_conflict = false;  // 最高分候选挂未仲裁 CONFLICTS_WITH 边
};

// 返回 "" = 不拒答;否则四 reason 之一(优先级 frontier > recanted > conflict > score)。
std::string evaluate_abstention(const AbstentionInput& in,
                                const AbstentionConfig& cfg = {});

}  // namespace starling::retrieval
