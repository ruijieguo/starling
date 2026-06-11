#pragma once
// Working Set — 海马体工作记忆面(system_design §2.4-3)。
//
// 把「此刻该放进 LLM 眼前的上下文」组装成 prompt-ready 的 ContextBlock:
// 五个分区各取自一个核心子系统(persona ← Neocortex PersonaContainer、
// common_ground ← Neocortex CommonGroundContainer、relevant_memories ←
// SemanticRetriever、pending_commitments ← Prospective CommitmentEngine、
// affect ← 召回行情感峰值),按行动优先级分配 token 预算,超额截断。
//
// 边界裁定(2026-06-11):本模块此前实现在 python/starling/working_set.py —
// 核心功能必须居于 C++;Python 侧只保留绑定转发(Memory / DashboardEngine
// 经 MemoryCore 调 _core.build_working_set)。token 估算按 Unicode 码点
// (≈ chars/4,与原 Python len() 语义逐位对齐),截断保证码点边界安全。
#include <map>
#include <string>
#include <string_view>
#include <vector>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/semantic_retriever.hpp"

namespace starling::hippocampus {

struct WorkingBlock {
    std::string label;
    std::string content;
    int token_estimate = 0;
};

struct ContextBlock {
    std::vector<WorkingBlock> blocks;
    std::vector<std::string> truncated;   // 因预算被截断的分区 label
    // 序列化为最终 prompt 文本(各分区带 "## …" 标题,空内容分区跳过)。
    std::string render() const;
};

// 近似 token:max(1, 码点数/4)。
int estimate_tokens(std::string_view text);

// label → content 的分区集按固定优先级
// (pending_commitments > persona > common_ground > relevant_memories > affect)
// 装入预算;放不下的按码点截断到剩余预算并记入 truncated。
ContextBlock assemble(const std::map<std::string, std::string>& sections,
                      int token_budget);

struct WorkingSetParams {
    std::string tenant_id;
    std::string agent_id;          // self/holder
    std::string interlocutor;      // 对话对象(共识配对 + 承诺过滤)
    std::string goal;              // 空 = 不做语义召回(memories/affect 两区缺省)
    int token_budget = 2000;
    int recall_k = 5;
};

// 五源汇集 + assemble。SemanticRetriever 由调用方注入,保证读写同一 embedder
// (与 DashboardEngine 的 rebuild_embedder 纪律一致)。fired 的承诺渲染为
// "⚠ DUE: " 前缀(B3 提醒闭环)。
ContextBlock build_working_set(persistence::SqliteAdapter& adapter,
                               retrieval::SemanticRetriever& retriever,
                               const WorkingSetParams& params);

}  // namespace starling::hippocampus
