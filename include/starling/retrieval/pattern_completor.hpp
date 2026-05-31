#pragma once
#include <string>
#include <vector>
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

struct PatternCompletionParams {
    std::string tenant_id, holder_id, holder_perspective;  // perspective "" = any
    std::string cue_text;          // 部分线索 → 嵌入 → 种子
    int seed_k = 5;                // 种子数（vector_recall k）
    int budget = 20;               // 最大传播步数
    int result_k = 20;             // 返回 top-K
    int node_cap = 1000;           // 访问节点上限
    double theta_propagate = 0.05;
    double decay = 0.5;            // 每步衰减
    std::string trace_id, query_id;
};

struct CompletionScored { StatementRow row; double activation; };

struct CompletionResult {
    std::vector<CompletionScored> rows;   // activation 降序, ≤ result_k
    bool completion_truncated = false;     // 访问节点 ≥ node_cap
    bool degraded = false;                 // 传播自 seeds.degraded
};

class PatternCompletor {
public:
    PatternCompletor(persistence::SqliteAdapter& a, SemanticRetriever& seeds)
        : adapter_(a), seeds_(seeds) {}
    CompletionResult complete(persistence::Connection&, const PatternCompletionParams&);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
    SemanticRetriever& seeds_;
};

}  // namespace starling::retrieval
