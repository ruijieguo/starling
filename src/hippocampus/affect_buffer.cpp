#include "starling/hippocampus/affect_buffer.hpp"

#include <sqlite3.h>

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

namespace starling::hippocampus::affect_buffer {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

std::vector<std::string> member_ids(persistence::Connection& conn,
                                    std::string_view tenant_id,
                                    const Config& cfg) {
    sqlite3* db = conn.raw();
    const char* sql =
        "SELECT id FROM statements "
        "WHERE tenant_id=? AND consolidation_state='volatile' AND salience >= ? "
        "ORDER BY salience DESC, created_at ASC LIMIT ?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "affect_buffer: member_ids prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    sqlite3_bind_double(h.get(), 2, cfg.theta_buffer);
    sqlite3_bind_int(h.get(), 3, cfg.capacity);
    std::vector<std::string> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        const auto* t = sqlite3_column_text(h.get(), 0);
        if (t) out.emplace_back(reinterpret_cast<const char*>(t));
    }
    return out;
}

std::unordered_set<std::string> member_set(persistence::Connection& conn,
                                           std::string_view tenant_id,
                                           const Config& cfg) {
    const auto ids = member_ids(conn, tenant_id, cfg);
    return {ids.begin(), ids.end()};
}

}  // namespace starling::hippocampus::affect_buffer
