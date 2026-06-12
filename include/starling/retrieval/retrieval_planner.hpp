#pragma once
// Retrieval Planner — 7 步规划管线(13_retrieval.md §P3 完整 7 步规划):
//   parse → mask → plan → fetch → fuse → ground → abstain
// 每步写 receipt.plan_steps 一行;perspective filter 必须先于语义排序
// (结构化路径 SQL 下推,语义路径 rerank 前按可见集遮蔽)。对外唯一副作用
// 是 fire-and-forget emit statement.recalled(读副作用契约)。
#include <string>
#include <vector>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/abstention.hpp"
#include "starling/retrieval/affect_reranker.hpp"
#include "starling/retrieval/context_pack.hpp"
#include "starling/retrieval/query_intent.hpp"
#include "starling/retrieval/retrieval_receipt.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

struct PlannerQuery {
    std::string tenant_id;
    std::string querier;                 // 谁在问(默认 self)
    std::string perspective;             // 从谁的视角;空 = querier
    QueryIntent intent = QueryIntent::FACT_LOOKUP;
    std::string text;                    // 语义线索(semantic_index 源)
    std::string subject_id;              // 结构化提示(可空)
    std::string predicate;               // 结构化提示(可空)
    std::string target;                  // BELIEF_OF_OTHER/META_BELIEF/COMMON_GROUND 对方
    std::string as_of_iso8601;
    int k = 10;
    std::string trace_id;
    std::string query_id;
    std::string runtime_health = "READY";   // 调用方注入(Python runtime 知情方)
    std::string global_holder_filter;    // 非空且与任一 step.holder_scope 不一致
                                         // → invalid_scope_filter_mix 拒绝
    AbstentionConfig abstention;
};

struct PlannerEntryOut {
    StatementRow row;
    double score = 0.0;
    ContextPackLabel label = ContextPackLabel::FACT;
};

struct PlannerResult {
    std::vector<PlannerEntryOut> entries;
    RetrievalReceipt receipt;
    std::string context_pack;            // 渲染后的 8 标签文本
    bool abstained = false;
};

class RetrievalPlanner {
 public:
    // SemanticRetriever 调用方注入:与写入侧同一 embedder(DashboardEngine
    // rebuild_embedder 纪律)。
    RetrievalPlanner(persistence::SqliteAdapter& adapter, SemanticRetriever& semantic)
        : adapter_(adapter), semantic_(semantic) {}

    RetrievalPlanner(const RetrievalPlanner&)            = delete;
    RetrievalPlanner& operator=(const RetrievalPlanner&) = delete;

    // 空 tenant/querier/as_of/query_id → throw std::invalid_argument。
    PlannerResult run(const PlannerQuery& q);

 private:
    persistence::SqliteAdapter& adapter_;
    SemanticRetriever& semantic_;
};

}  // namespace starling::retrieval
