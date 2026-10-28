#pragma once
#include <string>
#include <vector>
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/retrieval/statement_row.hpp"
#include "starling/retrieval/retrieval_receipt.hpp"

namespace starling::retrieval {

struct SemanticRetrieverParams {
    std::string tenant_id, holder_id;
    std::string holder_perspective;   // 空=any
    std::string query_text;
    int k = 10;
    std::string trace_id, query_id;
    // true:候选与二次校验都额外接受 consolidation_state='volatile'(只嵌入、
    // 未经 tick 回放)。只放宽巩固状态;review 守卫与 holder/视角谓词不变。
    bool include_volatile = false;
};
struct SemanticScored { StatementRow row; double score; };
struct SemanticResult {
    RetrievalReceipt receipt;
    std::vector<SemanticScored> rows;   // cosine 降序
    bool degraded = false;              // 无 embedder/向量 → true
};

class SemanticRetriever {
public:
    SemanticRetriever(persistence::SqliteAdapter& a, embedding::EmbeddingAdapter& e,
                      vector::VectorIndex& idx) : adapter_(a), embedder_(e), index_(idx) {}
    SemanticResult vector_recall(persistence::Connection&, const SemanticRetrieverParams&);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
    embedding::EmbeddingAdapter& embedder_;
    vector::VectorIndex& index_;
};

}  // namespace starling::retrieval
