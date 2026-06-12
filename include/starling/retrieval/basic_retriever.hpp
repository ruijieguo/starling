#pragma once

#include <chrono>
#include <string>
#include <vector>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/query_intent.hpp"
#include "starling/retrieval/retrieval_receipt.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

// QueryIntent 全 9 种见 query_intent.hpp(P3.a1 迁出)。BasicRetriever 仍只
// 接受 FACT_LOOKUP——结构化单意图入口的 runtime reject 行为是 P1 契约。

struct BasicRetrieverParams {
    std::string  tenant_id;
    std::string  holder_id;             // single holder only; empty → reject
    std::string  holder_perspective;    // optional; empty → "any" (no SQL predicate),
                                        // non-empty → exact-match predicate AND recorded
                                        // verbatim in receipt.filters_applied per
                                        // 13_retrieval.md:291 (P1-required entry).
    QueryIntent  intent{QueryIntent::FACT_LOOKUP};
    std::string  subject_id;
    std::string  predicate;
    std::string  as_of_iso8601;         // canonicalized at the Python boundary
    std::string  trace_id;              // caller-supplied; receipt echoes it
    std::string  query_id;              // caller-supplied; usually a fresh UUID
    // P2.a: when true, adds an EXISTS subquery against KnowledgeFrontier
    // visible_engrams_at(holder, as_of). Default false preserves P1 behavior.
    bool         apply_frontier_filter{false};
};

struct BasicRetrieveResult {
    std::vector<StatementRow> rows;
    RetrievalReceipt receipt;
};

class BasicRetriever {
 public:
    explicit BasicRetriever(starling::persistence::SqliteAdapter& adapter)
        : adapter_(adapter) {}

    BasicRetriever(const BasicRetriever&)            = delete;
    BasicRetriever& operator=(const BasicRetriever&) = delete;

    // Reject on empty tenant_id, empty holder_id, intent != FACT_LOOKUP, missing
    // subject_id or predicate, missing as_of. No silent broadening, per
    // 13_retrieval.md §"P1 basic_retrieve 闭环".
    BasicRetrieveResult run(const BasicRetrieverParams& params);

 private:
    starling::persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::retrieval
