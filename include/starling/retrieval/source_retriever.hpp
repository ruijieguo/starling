#pragma once
#include <string>
#include <vector>
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/semantic_retriever.hpp"

namespace starling::retrieval {

// Callers must supply an authorized, filtered source block. This prompt guides
// generation; it does not independently verify attribution or causal claims.
std::string grounded_source_answer_prompt(const std::string& question,
                                         const std::string& source_block);
// Adds a soft output-length policy; it does not truncate evidence or generated text.
std::string compact_source_answer_prompt(const std::string& question,
                                        const std::string& source_block);

std::string retain_source_turns(persistence::SqliteAdapter& adapter,
    const std::string& tenant_id, const std::vector<std::string>& allowed_holders,
    const std::string& turns_json, const std::string& created_at, bool preserve_invalid_time = false);

// Return the tenant-scoped holder allowlist used by observer evaluations.
// The SQL enumeration stays native so Python bindings do not reimplement
// retrieval scope discovery or candidate fusion.
std::vector<std::string> observer_holders(persistence::SqliteAdapter& adapter,
                                           const std::string& tenant_id);

struct ObserverQuery {
    std::string tenant_id;
    std::vector<std::string> allowed_holders;
    std::string question;
    std::string as_of_iso8601;
    // For evidence_profile_v8/v9/v10, k bounds SOURCE rows; hybrid queries may
    // append up to three strictly linked statements within max_context_bytes.
    int k = 10;
    int max_context_bytes = 8000;
    std::string mode = "hybrid";
    // evidence_profile_v9 uses v6 source selection and the independent v8
    // statement sidecar; its sources mode does not invoke the planner.
    // v10额外允许单人物变化题选取最多两个连续同会话的邻接上下文；
    // 只使用授权、已过滤来源，邻接不等于因果或目标人物自述。
    std::string source_strategy = "bm25";
    // Used by focused_dialogue and focused_coverage; outer k/bytes bound the result.
    int source_seed_k = 10;
    int source_seed_max_context_bytes = 4000;
    int source_dialogue_radius = 2;
    // For hybrid queries, fill this many SOURCE rows before statements.
    // Zero preserves the historical alternating source/statement order.
    int min_source_items = 0;
    bool include_unknown_time = false;
};

class ObserverRetriever {
public:
    ObserverRetriever(persistence::SqliteAdapter& adapter, SemanticRetriever& semantic)
        : adapter_(adapter), semantic_(semantic) {}
    std::string run(const ObserverQuery& query);
private:
    persistence::SqliteAdapter& adapter_;
    SemanticRetriever& semantic_;
};
} // namespace starling::retrieval
