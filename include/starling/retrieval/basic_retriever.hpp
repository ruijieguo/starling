#pragma once

#include <chrono>
#include <string>
#include <vector>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/statement_row.hpp"
#include "starling/retrieval/retrieval_receipt.hpp"

namespace starling::retrieval {

// P1 ships only FACT_LOOKUP. The remaining 8 intents (BELIEF_OF_OTHER,
// META_BELIEF, HISTORY, COMMITMENT_DUE, PREFERENCE, NORM_LOOKUP,
// COMMON_GROUND, ABSTAIN_CHECK) are spec'd at 13_retrieval.md
// §"QueryIntent 枚举（9 种）" but rejected at runtime in P1.
enum class QueryIntent {
    FACT_LOOKUP,
};

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
