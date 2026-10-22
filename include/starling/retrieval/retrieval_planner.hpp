#pragma once
// Retrieval Planner — 7 步规划管线(13_retrieval.md §P3 完整 7 步规划):
//   parse → mask → plan → fetch → fuse → ground → abstain
// 每步写 receipt.plan_steps 一行;perspective filter 必须先于语义排序
// (结构化路径 SQL 下推,语义路径 rerank 前按可见集遮蔽)。对外唯一副作用
// 是 fire-and-forget emit statement.recalled(读副作用契约)。
#include <string>
#include <optional>
#include <vector>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/abstention.hpp"
#include "starling/retrieval/affect_reranker.hpp"
#include "starling/retrieval/context_pack.hpp"
#include "starling/retrieval/query_intent.hpp"
#include "starling/retrieval/retrieval_receipt.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/retrieval/statement_row.hpp"
#include "starling/retrieval/temporal_evidence.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/source_vector_index.hpp"

#include <memory>

namespace starling::retrieval {

// 左脑 lane 的依赖注入。默认 nullopt = lane 关闭，planner 行为与改动前逐字节一致。
//
// tau_source 未标定前 lane 不得开启：构造函数里强制校验（§4.4 硬约束）。
struct SourceLaneDeps {
    vector::SourceVectorIndex* index = nullptr;
    embedding::EmbeddingAdapter* embedder = nullptr;
    int         dim = 0;
    std::string model;
    double      tau_source = 0.0;   // <= 0 视为未标定，拒绝构造
    int         k_max = 200;        // 迭代回填的硬上限
    int         chunk_byte_budget = 8000;
};

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
    std::optional<TemporalEvidenceRequest> temporal_evidence; // 默认关闭，只读来源顺序视图。
    std::optional<SourceLaneDeps>          source_lane;       // 默认 nullopt = 左脑关闭
};

struct PlannerEntryOut {
    StatementRow row;
    double score = 0.0;
    ContextPackLabel label = ContextPackLabel::FACT;
};

// 原文条目（左脑 lane，形态 S §4.2-§4.5）。与语句条目分开承载：原文没有
// holder/predicate 语义，硬塞进 StatementRow 会伪造字段。
struct SourceEntryOut {
    std::string engram_ref;
    std::string clause_id;
    std::string speaker;
    std::string session_id;
    std::string observed_at;      // 渲染日期用；provenance=ingest_clock 时不渲染
    std::string text;             // 原话（已转义为单行）
    std::string provenance;       // source_time | ingest_clock
    double      score = 0.0;      // 余弦相似度，不是 RRF 分
    double      rrf_score = 0.0;
    std::int64_t rrf_rank = 0;
};

// 左脑 lane 的配置校验；不合法即 throw std::invalid_argument。
void validate_source_lane(const SourceLaneDeps& deps);

struct PlannerResult {
    std::vector<PlannerEntryOut> entries;
    std::vector<SourceEntryOut>  source_entries;   // 左脑 lane（lane 关闭时恒空）
    RetrievalReceipt receipt;
    std::string context_pack;            // 渲染后的标签文本
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
