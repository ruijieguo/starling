#include "starling/retrieval/pattern_completor.hpp"

#include <sqlite3.h>
#include <algorithm>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

namespace starling::retrieval {

namespace {
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// Fetch a full StatementRow by (id, tenant) re-checking visibility — mirrors
// semantic_retriever.cpp kSelectByIdSql exactly (defense-in-depth on top of the
// walk's per-hop scope predicate).
constexpr const char* kSelectByIdSql =
    "SELECT id, tenant_id, holder_id, holder_perspective, "
    "       subject_kind, subject_id, predicate, "
    "       object_kind, object_value, canonical_object_hash, "
    "       modality, polarity, confidence, observed_at, "
    "       valid_from, valid_to, consolidation_state, review_status, "
    "       evidence_json "
    "  FROM statements "
    " WHERE id = ?1 AND tenant_id = ?2 "
    "   AND consolidation_state IN ('consolidated','archived') "
    "   AND review_status NOT IN ('rejected','pending_review') "
    " LIMIT 1;";

StatementRow fetch_row(persistence::Connection& conn, const std::string& id,
                       const std::string& tenant) {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, kSelectByIdSql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PatternCompletor::fetch_row prepare");
    StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, tenant.c_str(), -1, SQLITE_TRANSIENT);

    auto col = [raw](int i) {
        const unsigned char* t = sqlite3_column_text(raw, i);
        return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
    };
    StatementRow row;  // empty id signals "vanished / not visible"
    if (sqlite3_step(raw) != SQLITE_ROW) return row;
    row.id = col(0); row.tenant_id = col(1); row.holder_id = col(2);
    row.holder_perspective = col(3); row.subject_kind = col(4); row.subject_id = col(5);
    row.predicate = col(6); row.object_kind = col(7); row.object_value = col(8);
    row.canonical_object_hash = col(9); row.modality = col(10); row.polarity = col(11);
    row.confidence = sqlite3_column_double(raw, 12); row.observed_at = col(13);
    row.valid_from = col(14); row.valid_to = col(15); row.consolidation_state = col(16);
    row.review_status = col(17); row.evidence_json = col(18);
    return row;
}

}  // namespace

CompletionResult PatternCompletor::complete(persistence::Connection& conn,
                                            const PatternCompletionParams& params) {
    CompletionResult out;

    // Step 1: seeds via vector_recall (privacy-first; reused verbatim).
    SemanticRetrieverParams sp;
    sp.tenant_id = params.tenant_id;
    sp.holder_id = params.holder_id;
    sp.holder_perspective = params.holder_perspective;
    sp.query_text = params.cue_text;
    sp.k = params.seed_k;
    sp.trace_id = params.trace_id;
    sp.query_id = params.query_id;
    auto seeds = seeds_.vector_recall(conn, sp);
    out.degraded = seeds.degraded;
    if (seeds.rows.empty()) return out;  // no seeds → no walk

    // Step 2: activation init (seeds at 1.0).
    std::unordered_map<std::string, double> activation;
    std::unordered_set<std::string> visited;
    for (const auto& s : seeds.rows) {
        activation[s.row.id] = 1.0;
        visited.insert(s.row.id);
    }

    // Step 3: spreading-activation walk — filled in a later task. No propagation yet.

    // Step 4: top result_k by activation desc.
    std::vector<std::pair<std::string, double>> ranked(activation.begin(), activation.end());
    std::sort(ranked.begin(), ranked.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });
    if (static_cast<int>(ranked.size()) > params.result_k)
        ranked.resize(static_cast<size_t>(params.result_k));

    for (const auto& [id, act] : ranked) {
        StatementRow row = fetch_row(conn, id, params.tenant_id);
        if (row.id.empty()) continue;  // vanished between walk and fetch
        out.rows.push_back(CompletionScored{std::move(row), act});
    }
    return out;
}

}  // namespace starling::retrieval
