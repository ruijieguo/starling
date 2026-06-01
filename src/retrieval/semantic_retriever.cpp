#include "starling/retrieval/semantic_retriever.hpp"

#include <sqlite3.h>

#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

namespace starling::retrieval {

namespace {

// SELECT columns mirror basic_retriever.cpp exactly. The WHERE clause re-checks
// the visibility predicate (spec §7 "再次校验可见性") so a row whose state changed
// between search_topk and this fetch (rejected / pending_review / cross-tenant)
// is dropped — defense-in-depth on top of search_topk's scope filtering.
constexpr const char* kSelectByIdSql =
    "SELECT id, tenant_id, holder_id, holder_perspective, "
    "       subject_kind, subject_id, predicate, "
    "       object_kind, object_value, canonical_object_hash, "
    "       modality, polarity, confidence, observed_at, "
    "       valid_from, valid_to, consolidation_state, review_status, "
    "       evidence_json, affect_json "
    "  FROM statements "
    " WHERE id = ?1 AND tenant_id = ?2 "
    "   AND consolidation_state IN ('consolidated','archived') "
    "   AND review_status NOT IN ('rejected','pending_review') "
    " LIMIT 1;";

}  // namespace

SemanticResult SemanticRetriever::vector_recall(persistence::Connection& conn,
                                                 const SemanticRetrieverParams& params) {
    // Step 1: embed the query text.
    auto er = embedder_.embed(params.query_text);
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

    // Step 4: for each scored result, fetch the full statement row.
    sqlite3* db = conn.raw();
    SemanticResult result;
    result.degraded = false;

    for (const auto& s : scored) {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, kSelectByIdSql, -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("semantic_retriever: prepare failed: ")
                + sqlite3_errmsg(db));
        }
        persistence::StmtHandle h{raw};

        sqlite3_bind_text(raw, 1, s.stmt_id.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 2, params.tenant_id.c_str(), -1, SQLITE_TRANSIENT);

        auto col_text = [raw](int i) {
            const unsigned char* t = sqlite3_column_text(raw, i);
            return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
        };

        const int rc = sqlite3_step(raw);
        if (rc == SQLITE_DONE) {
            // Statement was deleted between search and fetch — skip.
            continue;
        }
        if (rc != SQLITE_ROW) {
            throw std::runtime_error(
                std::string("semantic_retriever: step failed: ")
                + sqlite3_errmsg(db));
        }

        StatementRow row;
        row.id                    = col_text(0);
        row.tenant_id             = col_text(1);
        row.holder_id             = col_text(2);
        row.holder_perspective    = col_text(3);
        row.subject_kind          = col_text(4);
        row.subject_id            = col_text(5);
        row.predicate             = col_text(6);
        row.object_kind           = col_text(7);
        row.object_value          = col_text(8);
        row.canonical_object_hash = col_text(9);
        row.modality              = col_text(10);
        row.polarity              = col_text(11);
        row.confidence            = sqlite3_column_double(raw, 12);
        row.observed_at           = col_text(13);
        row.valid_from            = col_text(14);
        row.valid_to              = col_text(15);
        row.consolidation_state   = col_text(16);
        row.review_status         = col_text(17);
        row.evidence_json         = col_text(18);
        row.affect_json           = col_text(19);

        result.rows.push_back(SemanticScored{std::move(row), s.score});
    }

    // search_topk already returns results in descending-score order.
    return result;
}

}  // namespace starling::retrieval
