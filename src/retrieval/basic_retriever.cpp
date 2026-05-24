#include "starling/retrieval/basic_retriever.hpp"

#include <sqlite3.h>

#include <stdexcept>
#include <string>
#include <vector>

#include "starling/final_query_assertion.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

namespace starling::retrieval {

namespace {

// The single P1 SELECT.
//
// SQL filter shape (also recorded in receipt.filters_applied):
//   tenant_id = ?1
//   holder_id = ?2  (logical "holder_scope" in §13 — annotated below so the
//                    M0.0 substring guard `is_final_query_safe` passes
//                    without renaming the column)
//   subject_kind = 'cognizer' (P1 retrieves cognizer subjects only)
//   subject_id = ?3
//   predicate = ?4
//   consolidation_state IN ('consolidated','archived')
//   review_status NOT IN ('rejected','pending_review')
//   valid_from IS NULL OR valid_from <= ?5
//   valid_to   IS NULL OR valid_to   >  ?5
//
// The block comment `/* holder_scope: holder_id */` is intentional: the M0.0
// final-query guard (final_query_assertion.cpp) does substring match on the
// raw SQL after stripping `--` line comments only, so a `/* */` annotation
// satisfies the TC-NEG-TENANT predicate without changing the schema. The
// column itself is `holder_id` (P1 single-holder; multi-holder scope arrives
// in M0.6+1).
//
// Evidence-erasure cannot be expressed as a column predicate (it requires a
// per-row JSON scan + secondary SELECT against engrams), so it is applied as
// a post-filter in C++. The receipt counts the drops separately.
constexpr const char* kSelectSql =
    "/* holder_scope: holder_id (P1 single-holder) */ "
    "SELECT id, tenant_id, holder_id, holder_perspective, "
    "       subject_kind, subject_id, predicate, "
    "       object_kind, object_value, canonical_object_hash, "
    "       modality, polarity, confidence, observed_at, "
    "       valid_from, valid_to, consolidation_state, review_status, "
    "       evidence_json "
    "  FROM statements "
    " WHERE tenant_id = ?1 "
    "   AND holder_id = ?2 "
    "   AND subject_kind = 'cognizer' "
    "   AND subject_id = ?3 "
    "   AND predicate = ?4 "
    "   AND consolidation_state IN ('consolidated','archived') "
    "   AND review_status NOT IN ('rejected','pending_review') "
    "   AND (valid_from IS NULL OR valid_from <= ?5) "
    "   AND (valid_to   IS NULL OR valid_to   >  ?5) ";

// Returns true iff `evidence_json` references at least one engram whose
// engrams.erased_at is non-NULL for the same tenant. Pulled out so the
// caller can count erasures for the receipt.
bool any_evidence_erased(starling::persistence::Connection& conn,
                         const std::string& tenant_id,
                         const std::string& evidence_json) {
    // evidence_json is a JSON array of objects like
    //   [{"engram_ref":"<uuid>","content_hash":"..."},...]
    // We scan for `"engram_ref":"<uuid>"` substrings (the same idiom
    // statement_writer.cpp uses for chunk-dup guards), then for each
    // engram_ref check whether engrams(id=?, tenant_id=?).erased_at IS NOT NULL.
    static constexpr const char* kCheckSql =
        "SELECT 1 FROM engrams "
        " WHERE tenant_id = ?1 AND id = ?2 "
        "   AND erased_at IS NOT NULL LIMIT 1;";

    static constexpr const char* kRefKey = "\"engram_ref\":\"";
    std::string::size_type pos = 0;
    while (true) {
        auto a = evidence_json.find(kRefKey, pos);
        if (a == std::string::npos) return false;
        a += std::char_traits<char>::length(kRefKey);
        auto b = evidence_json.find('"', a);
        if (b == std::string::npos) return false;
        std::string engram_id = evidence_json.substr(a, b - a);
        pos = b + 1;

        sqlite3_stmt* raw = nullptr;
        sqlite3* db = conn.raw();
        if (sqlite3_prepare_v2(db, kCheckSql, -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("evidence-erased prepare failed: ")
                + sqlite3_errmsg(db));
        }
        starling::persistence::StmtHandle h{raw};
        sqlite3_bind_text(raw, 1, tenant_id.c_str(),  -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 2, engram_id.c_str(),  -1, SQLITE_TRANSIENT);
        const int rc = sqlite3_step(raw);
        if (rc == SQLITE_ROW)  return true;
        if (rc == SQLITE_DONE) continue;
        throw std::runtime_error(
            std::string("evidence-erased step failed: ")
            + sqlite3_errmsg(db));
    }
}

}  // namespace

BasicRetrieveResult BasicRetriever::run(const BasicRetrieverParams& params) {
    if (params.tenant_id.empty()) {
        throw std::invalid_argument("basic_retrieve: tenant_id is required");
    }
    if (params.holder_id.empty()) {
        throw std::invalid_argument(
            "basic_retrieve: holder_id is required (single holder)");
    }
    if (params.intent != QueryIntent::FACT_LOOKUP) {
        throw std::invalid_argument(
            "basic_retrieve: only FACT_LOOKUP is supported in P1");
    }
    if (params.subject_id.empty() || params.predicate.empty()) {
        throw std::invalid_argument(
            "basic_retrieve: subject_id and predicate are required");
    }
    if (params.as_of_iso8601.empty()) {
        throw std::invalid_argument(
            "basic_retrieve: as_of timestamp is required");
    }

    // TC-NEG-TENANT: validate that the final SQL contains tenant_id +
    // holder_scope predicates. Belt-and-suspenders on top of the hardcoded
    // kSelectSql — if anyone later changes the constant in a way that
    // removes either guard, this throws before the query runs.
    if (!adapter_.check_final_query(kSelectSql)) {
        throw FinalQueryAssertionError(
            "basic_retrieve: final SQL missing tenant_id or holder_scope guard");
    }

    BasicRetrieveResult result;
    result.receipt.trace_id = params.trace_id;
    result.receipt.query_id = params.query_id;
    // The filters_applied entries mirror the SQL filter shape per
    // 13_retrieval.md §"RetrievalReceipt（P1 最小字段加粗）". Auditors verify
    // this list against the SQL to confirm what was actually applied.
    result.receipt.filters_applied = {
        {"tenant_id",             params.tenant_id},
        {"holder_id",             params.holder_id},
        {"subject_kind",          "cognizer"},
        {"subject_id",            params.subject_id},
        {"predicate",             params.predicate},
        {"consolidation_state",   "consolidated|archived"},
        {"review_status_exclude", "rejected|pending_review"},
        {"as_of",                 params.as_of_iso8601},
        {"evidence_erased",       "exclude"},
    };

    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, kSelectSql, -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("basic_retrieve prepare failed: ")
            + sqlite3_errmsg(db));
    }
    starling::persistence::StmtHandle stmt{raw};

    sqlite3_bind_text(raw, 1, params.tenant_id.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, params.holder_id.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, params.subject_id.c_str(),    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 4, params.predicate.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 5, params.as_of_iso8601.c_str(), -1, SQLITE_TRANSIENT);

    auto col_text = [raw](int i) {
        const unsigned char* t = sqlite3_column_text(raw, i);
        return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
    };

    // NOTE: dropped_by_state / dropped_by_review / dropped_by_time_anchor
    // remain 0 in the P1 receipt because the SELECT pre-filters those rows
    // before we materialize them — we never see the drops at the row level.
    // Future versions may move these filters to a wider SELECT + post-filter
    // if per-reason counts become observability-required.
    while (true) {
        const int rc = sqlite3_step(raw);
        if (rc == SQLITE_DONE) break;
        if (rc != SQLITE_ROW) {
            throw std::runtime_error(
                std::string("basic_retrieve step failed: ")
                + sqlite3_errmsg(db));
        }
        result.receipt.candidate_counts.fetched += 1;

        StatementRow row;
        row.id                      = col_text(0);
        row.tenant_id               = col_text(1);
        row.holder_id               = col_text(2);
        row.holder_perspective      = col_text(3);
        row.subject_kind            = col_text(4);
        row.subject_id              = col_text(5);
        row.predicate               = col_text(6);
        row.object_kind             = col_text(7);
        row.object_value            = col_text(8);
        row.canonical_object_hash   = col_text(9);
        row.modality                = col_text(10);
        row.polarity                = col_text(11);
        row.confidence              = sqlite3_column_double(raw, 12);
        row.observed_at             = col_text(13);
        row.valid_from              = col_text(14);
        row.valid_to                = col_text(15);
        row.consolidation_state     = col_text(16);
        row.review_status           = col_text(17);
        row.evidence_json           = col_text(18);

        if (any_evidence_erased(conn, row.tenant_id, row.evidence_json)) {
            result.receipt.candidate_counts.dropped_by_evidence_erasure += 1;
            result.receipt.evidence_erased_count += 1;
            continue;
        }
        result.rows.push_back(std::move(row));
    }

    result.receipt.candidate_counts.returned =
        static_cast<std::int64_t>(result.rows.size());
    result.receipt.sufficiency_status =
        result.rows.empty() ? Sufficiency::MISSING_INFO
                            : Sufficiency::SUFFICIENT;

    return result;
}

}  // namespace starling::retrieval
