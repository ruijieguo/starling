#include "starling/retrieval/semantic_retriever.hpp"

#include <sqlite3.h>

#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/store/sqlite_meta_store.hpp"

namespace starling::retrieval {

SemanticResult SemanticRetriever::vector_recall(persistence::Connection& conn,
                                                 const SemanticRetrieverParams& params) {
    // Step 1: embed the query text. An embedder failure (network error,
    // permanent 4xx, missing backend) must DEGRADE, not fail the recall:
    // vector-layer spec "DEGRADED 行为" — vector_recall returns an empty
    // degraded=true result while basic_retrieve and all writes stay normal.
    // Catches std::exception because the embedding adapter raises both
    // EmbeddingError (retryable) and std::runtime_error (permanent).
    embedding::EmbeddingResult er;
    try {
        er = embedder_.embed(params.query_text);
    } catch (const std::exception&) {
        SemanticResult degraded;
        degraded.degraded = true;
        return degraded;
    }
    const auto& q = er.vector;

    // Step 2: build SearchScope — privacy predicates are enforced inside search_topk.
    vector::SearchScope scope;
    scope.tenant_id = params.tenant_id;
    scope.holder_id = params.holder_id.empty()
                          ? std::nullopt
                          : std::optional<std::string>(params.holder_id);
    scope.holder_perspective = params.holder_perspective.empty()
                                   ? std::nullopt
                                   : std::optional<std::string>(params.holder_perspective);
    scope.visible_only = true;  // privacy-first: NEVER widen

    // Step 3: top-k search (visibility/privacy predicate pushed into search).
    auto scored = index_.search_topk(conn, q, params.k, scope);

    // Step 4: 逐个 scored 结果取整行 —— P3.b1 phase 3:读收编进 MetaStore。
    // query_statements 的默认守卫(state IN(consolidated,archived) + review
    // NOT IN(rejected,pending_review))即原 kSelectByIdSql 的 visibility 二次
    // 校验(spec §7);删/状态变 → 空结果 → skip(原 SQLITE_DONE 路径)。
    store::SqliteMetaStore meta(conn);
    SemanticResult result;
    result.degraded = false;
    for (const auto& s : scored) {
        store::StatementFilter f;
        f.tenant_id = params.tenant_id;
        f.id_in = {s.stmt_id};
        const auto rows = meta.query_statements(f);
        if (rows.empty()) continue;
        result.rows.push_back(SemanticScored{rows.front(), s.score});
    }
    // search_topk already returns results in descending-score order.
    return result;
}

}  // namespace starling::retrieval
