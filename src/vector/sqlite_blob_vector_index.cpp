#include "starling/vector/vector_index.hpp"
#include "starling/vector/vector_math.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/connection.hpp"

#include <sqlite3.h>
#include <algorithm>
#include <string>
#include <string_view>
#include <vector>

namespace starling::vector {

using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

void SqliteBlobVectorIndex::insert(
    persistence::Connection& conn,
    std::string_view stmt_id,
    std::string_view tenant_id,
    const std::vector<float>& vec)
{
    const char* sql =
        "INSERT INTO statement_vectors"
        "(stmt_id,tenant_id,index_vector,raw_embedding,dim,model,status,embedded_at)"
        " VALUES(?,?,?,?,?,'stub','embedded','1970-01-01T00:00:00Z')"
        " ON CONFLICT(stmt_id) DO UPDATE SET index_vector=excluded.index_vector";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "SqliteBlobVectorIndex::insert prepare");
    StmtHandle h(raw);

    bind_sv(h.get(), 1, stmt_id);
    bind_sv(h.get(), 2, tenant_id);

    const std::string blob = to_blob(vec);
    sqlite3_bind_blob(h.get(), 3, blob.data(), static_cast<int>(blob.size()), SQLITE_TRANSIENT);
    sqlite3_bind_blob(h.get(), 4, blob.data(), static_cast<int>(blob.size()), SQLITE_TRANSIENT);
    sqlite3_bind_int(h.get(), 5, static_cast<int>(vec.size()));

    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "SqliteBlobVectorIndex::insert step");
}

std::vector<ScoredId> SqliteBlobVectorIndex::search_topk(
    persistence::Connection& conn,
    const std::vector<float>& query,
    int k,
    const SearchScope& scope)
{
    const char* sql =
        "SELECT v.stmt_id, v.index_vector"
        " FROM statement_vectors v JOIN statements s ON s.id = v.stmt_id"
        " WHERE v.tenant_id = ?1 AND v.status = 'embedded'"
        "   AND (?2 = '' OR s.holder_id = ?2)"
        "   AND (?3 = '' OR s.holder_perspective = ?3)"
        "   AND (?4 = 0 OR (s.consolidation_state IN ('consolidated','archived')"
        "                   AND s.review_status NOT IN ('rejected','pending_review')))";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "SqliteBlobVectorIndex::search_topk prepare");
    StmtHandle h(raw);

    bind_sv(h.get(), 1, scope.tenant_id);

    const std::string holder = scope.holder_id.value_or("");
    bind_sv(h.get(), 2, holder);

    const std::string perspective = scope.holder_perspective.value_or("");
    bind_sv(h.get(), 3, perspective);

    sqlite3_bind_int(h.get(), 4, scope.visible_only ? 1 : 0);

    std::vector<ScoredId> results;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        const char* id_ptr = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
        std::string sid(id_ptr ? id_ptr : "");

        const void* blob_ptr = sqlite3_column_blob(h.get(), 1);
        int blob_bytes = sqlite3_column_bytes(h.get(), 1);
        std::string blob_data(static_cast<const char*>(blob_ptr), static_cast<size_t>(blob_bytes));
        std::vector<float> vec = from_blob(blob_data);

        double score = cosine(query, vec);
        results.push_back({std::move(sid), score});
    }

    std::sort(results.begin(), results.end(),
              [](const ScoredId& a, const ScoredId& b) { return a.score > b.score; });

    if (static_cast<int>(results.size()) > k)
        results.resize(static_cast<size_t>(k));

    return results;
}

void SqliteBlobVectorIndex::remove(
    persistence::Connection& conn,
    std::string_view stmt_id)
{
    const char* sql = "DELETE FROM statement_vectors WHERE stmt_id=?";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "SqliteBlobVectorIndex::remove prepare");
    StmtHandle h(raw);

    bind_sv(h.get(), 1, stmt_id);

    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "SqliteBlobVectorIndex::remove step");
}

}  // namespace starling::vector
