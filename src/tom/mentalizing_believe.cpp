#include "starling/tom/mentalizing.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace starling::tom::mentalizing {

namespace {

// Map a sqlite3_stmt row (columns 0-18 matching the SELECT below) into a
// StatementRow, mirroring the column order used in basic_retriever.cpp.
retrieval::StatementRow row_from_stmt(sqlite3_stmt* raw) {
    auto col_text = [raw](int i) -> std::string {
        const unsigned char* t = sqlite3_column_text(raw, i);
        return t ? std::string(reinterpret_cast<const char*>(t)) : std::string{};
    };
    retrieval::StatementRow r;
    r.id                    = col_text(0);
    r.tenant_id             = col_text(1);
    r.holder_id             = col_text(2);
    r.holder_perspective    = col_text(3);
    r.subject_kind          = col_text(4);
    r.subject_id            = col_text(5);
    r.predicate             = col_text(6);
    r.object_kind           = col_text(7);
    r.object_value          = col_text(8);
    r.canonical_object_hash = col_text(9);
    r.modality              = col_text(10);
    r.polarity              = col_text(11);
    r.confidence            = sqlite3_column_double(raw, 12);
    r.observed_at           = col_text(13);
    r.valid_from            = col_text(14);
    r.valid_to              = col_text(15);
    r.consolidation_state   = col_text(16);
    r.review_status         = col_text(17);
    r.evidence_json         = col_text(18);
    return r;
}

}  // namespace

// SELECT all statements held by cognizer X about subject Y.
// Optionally filter by modality.
std::vector<retrieval::StatementRow> what_does_X_believe(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view about_y,
    std::string_view tenant,
    std::string_view as_of,
    std::string_view modality_filter)
{
    auto& conn = adapter.connection();
    sqlite3* db = conn.raw();

    const std::string sql_base =
        "SELECT id, tenant_id, holder_id, holder_perspective,"
        "       subject_kind, subject_id, predicate,"
        "       object_kind, object_value, canonical_object_hash,"
        "       modality, polarity, confidence, observed_at,"
        "       valid_from, valid_to, consolidation_state, review_status,"
        "       evidence_json"
        "  FROM statements"
        " WHERE tenant_id = ?1"
        "   AND holder_id = ?2"
        "   AND subject_kind = 'cognizer'"
        "   AND subject_id = ?3"
        "   AND consolidation_state IN ('consolidated','archived')"
        "   AND review_status NOT IN ('rejected','pending_review')"
        "   AND (valid_from IS NULL OR valid_from <= ?4)"
        "   AND (valid_to   IS NULL OR valid_to   >  ?4)";

    const std::string sql = modality_filter.empty()
        ? sql_base
        : sql_base + " AND modality = ?5";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("what_does_X_believe: prepare failed: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle stmt{raw};

    sqlite3_bind_text(raw, 1, tenant.data(), static_cast<int>(tenant.size()),
                      SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, x.data(), static_cast<int>(x.size()),
                      SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, about_y.data(), static_cast<int>(about_y.size()),
                      SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 4, as_of.data(), static_cast<int>(as_of.size()),
                      SQLITE_TRANSIENT);
    if (!modality_filter.empty()) {
        sqlite3_bind_text(raw, 5, modality_filter.data(),
                          static_cast<int>(modality_filter.size()), SQLITE_TRANSIENT);
    }

    std::vector<retrieval::StatementRow> result;
    while (true) {
        const int rc = sqlite3_step(raw);
        if (rc == SQLITE_DONE) break;
        if (rc != SQLITE_ROW) {
            throw std::runtime_error(
                std::string("what_does_X_believe: step failed: ") + sqlite3_errmsg(db));
        }
        result.push_back(row_from_stmt(raw));
    }
    return result;
}

}  // namespace starling::tom::mentalizing
