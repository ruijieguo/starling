#pragma once
// Context Pack 8 标签(13_retrieval.md §核心算法-3):LLM 收到的不是无差别
// 文本,而是带认识论地位标注的语用结构。classify 为纯函数:行 + 三个成员集
// (planner 预查的承诺/冲突/共识 id 集)→ 标签;首中即停的优先级链。
#include <string>
#include <string_view>
#include <unordered_set>
#include <vector>

#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

enum class ContextPackLabel { FACT, BELIEF, HEARSAY, INFERRED, COMMON, TODO, CONFLICT, ABSTAIN };

inline const char* to_string(ContextPackLabel v) {
    switch (v) {
        case ContextPackLabel::FACT:     return "FACT";
        case ContextPackLabel::BELIEF:   return "BELIEF";
        case ContextPackLabel::HEARSAY:  return "HEARSAY";
        case ContextPackLabel::INFERRED: return "INFERRED";
        case ContextPackLabel::COMMON:   return "COMMON";
        case ContextPackLabel::TODO:     return "TODO";
        case ContextPackLabel::CONFLICT: return "CONFLICT";
        case ContextPackLabel::ABSTAIN:  return "ABSTAIN";
    }
    return "FACT";
}

struct PackContext {
    std::unordered_set<std::string> todo_ids;      // 活跃承诺的 stmt_id
    std::unordered_set<std::string> conflict_ids;  // 未仲裁 CONFLICTS_WITH 端点
    std::unordered_set<std::string> common_ids;    // grounded 共识 stmt_id
    std::unordered_set<std::string> recanted_ids;  // recanted 共识 stmt_id
    std::string querier;
};

struct PackEntry {
    ContextPackLabel label;
    std::string statement_id;
    std::string line;
};

// provenance 不在 StatementRow 里(P1 列裁剪);planner 持有该列时走带参版本。
ContextPackLabel classify_with_provenance(const StatementRow& row,
                                          const PackContext& ctx,
                                          std::string_view provenance);
// 便捷版:provenance 视为 "user_input"。
ContextPackLabel classify(const StatementRow& row, const PackContext& ctx);

// "[LABEL] subject predicate object (conf 0.93, holder Alice)"
std::string render_line(const StatementRow& row, ContextPackLabel label);
// 整包渲染;abstention_reason 非空时输出单行 "[ABSTAIN] 无可靠记忆(reason)"。
std::string render_pack(const std::vector<PackEntry>& entries,
                        std::string_view abstention_reason);

}  // namespace starling::retrieval
