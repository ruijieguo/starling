#include "starling/memory/memory_events.hpp"

#include <sqlite3.h>

#include <utility>

#include "starling/persistence/stmt.hpp"

namespace starling::memoryops {

namespace {

// 读一列 TEXT;NULL 当空串(events 的这几列都是 NOT NULL,这里只是防御)。
std::string column_string(sqlite3_stmt* stmt, int col) {
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const auto* text = reinterpret_cast<const char*>(sqlite3_column_text(stmt, col));
    return text != nullptr ? std::string(text) : std::string();
}

}  // namespace

std::int64_t next_seq(persistence::Connection& conn, std::string_view tenant) {
    persistence::Stmt q(conn.raw(),
                        "SELECT COALESCE(MAX(seq) + 1, 0) FROM events WHERE tenant_id=?1");
    q.bind(tenant);
    q.step_row();
    return sqlite3_column_int64(q.raw(), 0);
}

std::vector<PendingEventRow> pending_events(persistence::Connection& conn,
                                            std::string_view tenant) {
    persistence::Stmt q(conn.raw(),
                        "SELECT key, text, interlocutor, seq, failure_category FROM events "
                        "WHERE tenant_id=?1 AND state='pending' ORDER BY seq ASC");
    q.bind(tenant);
    std::vector<PendingEventRow> rows;
    while (q.step_row()) {
        PendingEventRow row;
        row.key = column_string(q.raw(), 0);
        row.text = column_string(q.raw(), 1);
        row.interlocutor = column_string(q.raw(), 2);
        row.seq = sqlite3_column_int64(q.raw(), 3);
        row.failure_category = column_string(q.raw(), 4);
        rows.push_back(std::move(row));
    }
    return rows;
}

}  // namespace starling::memoryops
