#include "starling/bus/conflict_key_backfill.hpp"

#include "starling/bus/conflict_key.hpp"
#include "starling/bus/normalized_interval.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdio>
#include <optional>
#include <string>
#include <vector>

namespace starling::bus::conflict_key_backfill {

namespace {

struct EdgeRow {
    std::string id;
    std::string src_id;
    std::string tenant_id;
};

}  // namespace

bool is_complete(persistence::Connection& conn) {
    const char* sql =
        "SELECT completed_at FROM conflict_key_backfill_state WHERE id = 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return false;
    persistence::StmtHandle h(raw);
    if (sqlite3_step(h.get()) != SQLITE_ROW)
        return false;
    return sqlite3_column_type(h.get(), 0) != SQLITE_NULL;
}

TickStats tick_one_batch(persistence::Connection& conn, int batch_size) {
    TickStats stats;

    if (is_complete(conn))
        return stats;

    // SAVEPOINT so a failure here doesn't corrupt an outer transaction (e.g.
    // Bus::write_impl's TransactionGuard). On any exception we ROLLBACK TO the
    // savepoint and return empty stats.
    try {
        conn.exec("SAVEPOINT conflict_key_backfill");
    } catch (...) {
        return stats;
    }

    try {
        // Fetch cursor.
        std::string last_id;
        {
            const char* sql =
                "SELECT last_processed_edge_id FROM conflict_key_backfill_state WHERE id = 1";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                throw detail::make_sqlite_error(conn.raw(), "backfill: fetch cursor prepare");
            persistence::StmtHandle h(raw);
            if (sqlite3_step(h.get()) == SQLITE_ROW) {
                if (sqlite3_column_type(h.get(), 0) != SQLITE_NULL) {
                    const char* txt = reinterpret_cast<const char*>(
                        sqlite3_column_text(h.get(), 0));
                    if (txt) last_id = txt;
                }
            }
        }

        // SELECT next batch of NULL-key conflicts_with edges.
        std::vector<EdgeRow> batch;
        {
            const char* sql =
                "SELECT se.id, se.src_id, se.tenant_id "
                "FROM statement_edges se "
                "WHERE se.edge_kind = 'conflicts_with' "
                "  AND se.canonical_conflict_key IS NULL "
                "  AND (? = '' OR se.id > ?) "
                "ORDER BY se.id "
                "LIMIT ?";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                throw detail::make_sqlite_error(conn.raw(), "backfill: select batch prepare");
            persistence::StmtHandle h(raw);
            detail::bind_sv(h.get(), 1, last_id);
            detail::bind_sv(h.get(), 2, last_id);
            sqlite3_bind_int(h.get(), 3, batch_size);
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                EdgeRow row;
                auto get_text = [&](int col) -> std::string {
                    const char* t = reinterpret_cast<const char*>(
                        sqlite3_column_text(h.get(), col));
                    return t ? t : "";
                };
                row.id        = get_text(0);
                row.src_id    = get_text(1);
                row.tenant_id = get_text(2);
                batch.push_back(std::move(row));
            }
        }

        if (batch.empty()) {
            // All edges processed — mark complete.
            const std::string now =
                detail::iso8601_utc(std::chrono::system_clock::now());
            {
                const char* sql =
                    "UPDATE conflict_key_backfill_state "
                    "SET completed_at = ?, last_updated_at = ? WHERE id = 1";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw detail::make_sqlite_error(conn.raw(), "backfill: mark complete prepare");
                persistence::StmtHandle h(raw);
                detail::bind_sv(h.get(), 1, now);
                detail::bind_sv(h.get(), 2, now);
                if (sqlite3_step(h.get()) != SQLITE_DONE)
                    throw detail::make_sqlite_error(conn.raw(), "backfill: mark complete step");
            }
            conn.exec("RELEASE SAVEPOINT conflict_key_backfill");
            stats.completed_now = true;
            return stats;
        }

        // Process each edge.
        std::string new_last_id;
        int new_backfilled = 0;
        int new_deduped    = 0;

        for (const auto& edge : batch) {
            stats.rows_processed++;
            new_last_id = edge.id;

            // Fetch the src statement fields needed to compute the conflict key.
            extractor::ExtractedStatement stmt_proxy;
            bool found = false;
            {
                const char* sql =
                    "SELECT holder_id, subject_kind, subject_id, predicate, "
                    "       canonical_object_hash, modality, "
                    "       valid_from, valid_to, event_time_start "
                    "FROM statements "
                    "WHERE id = ? AND tenant_id = ? "
                    "LIMIT 1";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw detail::make_sqlite_error(conn.raw(), "backfill: fetch stmt prepare");
                persistence::StmtHandle h(raw);
                detail::bind_sv(h.get(), 1, edge.src_id);
                detail::bind_sv(h.get(), 2, edge.tenant_id);
                if (sqlite3_step(h.get()) == SQLITE_ROW) {
                    found = true;
                    auto get_text = [&](int col) -> std::string {
                        const char* t = reinterpret_cast<const char*>(
                            sqlite3_column_text(h.get(), col));
                        return t ? t : "";
                    };
                    auto get_opt = [&](int col) -> std::optional<std::string> {
                        if (sqlite3_column_type(h.get(), col) == SQLITE_NULL)
                            return std::nullopt;
                        const char* t = reinterpret_cast<const char*>(
                            sqlite3_column_text(h.get(), col));
                        return t ? std::optional<std::string>{t} : std::nullopt;
                    };
                    stmt_proxy.holder_id             = get_text(0);
                    stmt_proxy.subject_kind          = get_text(1);
                    stmt_proxy.subject_id            = get_text(2);
                    stmt_proxy.predicate             = get_text(3);
                    stmt_proxy.canonical_object_hash = get_text(4);
                    const std::string mod_str        = get_text(5);
                    try {
                        stmt_proxy.modality = schema::modality_from_string(mod_str);
                    } catch (...) {
                        stmt_proxy.modality = schema::Modality::BELIEVES;
                    }
                    stmt_proxy.valid_from       = get_opt(6);
                    stmt_proxy.valid_to         = get_opt(7);
                    stmt_proxy.event_time_start = get_opt(8);
                }
            }

            if (!found) {
                // Orphan edge (src statement deleted?) — skip, leave for manual cleanup.
                continue;
            }

            const std::string key = canonical_conflict_key_hex(stmt_proxy);

            // Attempt UPDATE; if UNIQUE constraint fires -> DELETE + count deduped.
            {
                const char* sql =
                    "UPDATE statement_edges "
                    "SET canonical_conflict_key = ? "
                    "WHERE id = ?";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw detail::make_sqlite_error(conn.raw(), "backfill: update edge prepare");
                persistence::StmtHandle h(raw);
                detail::bind_sv(h.get(), 1, key);
                detail::bind_sv(h.get(), 2, edge.id);
                const int rc = sqlite3_step(h.get());
                if (rc == SQLITE_DONE) {
                    new_backfilled++;
                } else if (rc == SQLITE_CONSTRAINT) {
                    // Duplicate -- delete this edge.
                    const char* del_sql =
                        "DELETE FROM statement_edges WHERE id = ?";
                    sqlite3_stmt* del_raw = nullptr;
                    if (sqlite3_prepare_v2(conn.raw(), del_sql, -1, &del_raw, nullptr) != SQLITE_OK)
                        throw detail::make_sqlite_error(conn.raw(), "backfill: delete dup prepare");
                    persistence::StmtHandle dh(del_raw);
                    detail::bind_sv(dh.get(), 1, edge.id);
                    if (sqlite3_step(dh.get()) != SQLITE_DONE)
                        throw detail::make_sqlite_error(conn.raw(), "backfill: delete dup step");
                    new_deduped++;
                    std::fprintf(stderr,
                        "[conflict_key_backfill] WARN dedup: edge %s key=%s\n",
                        edge.id.c_str(), key.c_str());
                } else {
                    throw detail::make_sqlite_error(conn.raw(), "backfill: update edge step");
                }
            }
        }

        // Update state row.
        {
            const std::string now =
                detail::iso8601_utc(std::chrono::system_clock::now());
            const char* sql =
                "UPDATE conflict_key_backfill_state "
                "SET last_processed_edge_id = ?, "
                "    rows_backfilled = rows_backfilled + ?, "
                "    rows_deduped    = rows_deduped    + ?, "
                "    last_updated_at = ? "
                "WHERE id = 1";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                throw detail::make_sqlite_error(conn.raw(), "backfill: update state prepare");
            persistence::StmtHandle h(raw);
            detail::bind_sv(h.get(), 1, new_last_id);
            sqlite3_bind_int(h.get(), 2, new_backfilled);
            sqlite3_bind_int(h.get(), 3, new_deduped);
            detail::bind_sv(h.get(), 4, now);
            if (sqlite3_step(h.get()) != SQLITE_DONE)
                throw detail::make_sqlite_error(conn.raw(), "backfill: update state step");
        }

        conn.exec("RELEASE SAVEPOINT conflict_key_backfill");

        stats.rows_backfilled = new_backfilled;
        stats.rows_deduped    = new_deduped;

    } catch (...) {
        try {
            conn.exec("ROLLBACK TO SAVEPOINT conflict_key_backfill");
            conn.exec("RELEASE SAVEPOINT conflict_key_backfill");
        } catch (...) {}
        // Return zeroed stats -- backfill failure is best-effort.
        return TickStats{};
    }

    return stats;
}

}  // namespace starling::bus::conflict_key_backfill
