// projection_maintainer.cpp -- ProjectionMaintainer outbox subscriber.
// Consumes statement.* bus events → incrementally upserts 5 statement-keyed
// projection tables and advances projection_subscriber_checkpoint.
// proj_common_ground is driven by common_ground changes, not statement events.
// rebuild_projection is Task 27 (stub).

#include "starling/projection/projection_maintainer.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <cstdio>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::projection {

namespace {

using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// ── Checkpoint helpers ───────────────────────────────────────────────────────

int read_checkpoint(persistence::Connection& conn) {
    const char* sql =
        "SELECT last_processed_outbox_sequence "
        "FROM projection_subscriber_checkpoint WHERE id = 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(),
            "projection_maintainer: read checkpoint prepare");
    StmtHandle h(raw);
    if (sqlite3_step(h.get()) == SQLITE_ROW)
        return sqlite3_column_int(h.get(), 0);
    return 0;
}

void write_checkpoint(persistence::Connection& conn, int new_seq,
                      std::string_view now_iso) {
    const char* sql =
        "UPDATE projection_subscriber_checkpoint "
        "SET last_processed_outbox_sequence = ?, "
        "    last_updated_at = ? "
        "WHERE id = 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(),
            "projection_maintainer: update checkpoint prepare");
    StmtHandle h(raw);
    sqlite3_bind_int(h.get(), 1, new_seq);
    bind_sv(h.get(), 2, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(),
            "projection_maintainer: update checkpoint step");
}

// ── Statement row ────────────────────────────────────────────────────────────

struct StmtRow {
    std::string tenant_id;
    std::string holder_id;
    std::string subject_kind;
    std::string subject_id;
    std::string predicate;
    std::string consolidation_state;
    std::string observed_at;
    double      salience = 0.0;
    std::string modality;
    bool        found = false;
};

StmtRow read_stmt(persistence::Connection& conn, std::string_view stmt_id) {
    const char* sql =
        "SELECT tenant_id, holder_id, subject_kind, subject_id, predicate, "
        "       consolidation_state, observed_at, salience, modality "
        "FROM statements WHERE id = ?";
    sqlite3_stmt* raw = nullptr;
    StmtRow row;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return row;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, stmt_id);
    if (sqlite3_step(h.get()) == SQLITE_ROW) {
        auto get_text = [&](int col) -> std::string {
            const char* t = reinterpret_cast<const char*>(
                sqlite3_column_text(h.get(), col));
            return t ? t : "";
        };
        row.tenant_id           = get_text(0);
        row.holder_id           = get_text(1);
        row.subject_kind        = get_text(2);
        row.subject_id          = get_text(3);
        row.predicate           = get_text(4);
        row.consolidation_state = get_text(5);
        row.observed_at         = get_text(6);
        row.salience            = sqlite3_column_double(h.get(), 7);
        row.modality            = get_text(8);
        row.found               = true;
    }
    return row;
}

// ── Projection helpers ───────────────────────────────────────────────────────

// Delete the stmt's rows from the 5 statement-keyed projections.
void delete_projection_rows(persistence::Connection& conn,
                            std::string_view stmt_id) {
    static const char* kDelSqls[] = {
        "DELETE FROM proj_holder_state_time WHERE stmt_id = ?",
        "DELETE FROM proj_holder_subgraph     WHERE stmt_id = ?",
        "DELETE FROM proj_entity_statement    WHERE stmt_id = ?",
        "DELETE FROM proj_salience_hot        WHERE stmt_id = ?",
        "DELETE FROM proj_commitment_due      WHERE stmt_id = ?",
    };
    for (const char* sql : kDelSqls) {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            continue;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, stmt_id);
        sqlite3_step(h.get());
    }
}

// UPSERT into the 5 statement-keyed projections. Returns number of upserts.
int upsert_projection_rows(persistence::Connection& conn,
                           std::string_view stmt_id,
                           const StmtRow& r) {
    int count = 0;

    // proj_holder_state_time
    {
        const char* sql =
            "INSERT OR REPLACE INTO proj_holder_state_time"
            "(tenant_id, holder_id, consolidation_state, observed_at, stmt_id)"
            " VALUES(?,?,?,?,?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, r.tenant_id);
            bind_sv(h.get(), 2, r.holder_id);
            bind_sv(h.get(), 3, r.consolidation_state);
            bind_sv(h.get(), 4, r.observed_at);
            bind_sv(h.get(), 5, stmt_id);
            if (sqlite3_step(h.get()) == SQLITE_DONE) count++;
        }
    }

    // proj_holder_subgraph
    {
        const char* sql =
            "INSERT OR REPLACE INTO proj_holder_subgraph"
            "(tenant_id, holder_id, subject_kind, subject_id, predicate, stmt_id)"
            " VALUES(?,?,?,?,?,?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, r.tenant_id);
            bind_sv(h.get(), 2, r.holder_id);
            bind_sv(h.get(), 3, r.subject_kind);
            bind_sv(h.get(), 4, r.subject_id);
            bind_sv(h.get(), 5, r.predicate);
            bind_sv(h.get(), 6, stmt_id);
            if (sqlite3_step(h.get()) == SQLITE_DONE) count++;
        }
    }

    // proj_entity_statement
    {
        const char* sql =
            "INSERT OR REPLACE INTO proj_entity_statement"
            "(tenant_id, subject_kind, subject_id, stmt_id)"
            " VALUES(?,?,?,?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, r.tenant_id);
            bind_sv(h.get(), 2, r.subject_kind);
            bind_sv(h.get(), 3, r.subject_id);
            bind_sv(h.get(), 4, stmt_id);
            if (sqlite3_step(h.get()) == SQLITE_DONE) count++;
        }
    }

    // proj_salience_hot
    {
        const char* sql =
            "INSERT OR REPLACE INTO proj_salience_hot"
            "(tenant_id, salience, stmt_id)"
            " VALUES(?,?,?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, r.tenant_id);
            sqlite3_bind_double(h.get(), 2, r.salience);
            bind_sv(h.get(), 3, stmt_id);
            if (sqlite3_step(h.get()) == SQLITE_DONE) count++;
        }
    }

    // proj_commitment_due — due_at = observed_at if modality=COMMITS, else NULL
    {
        const char* sql =
            "INSERT OR REPLACE INTO proj_commitment_due"
            "(tenant_id, due_at, stmt_id)"
            " VALUES(?,?,?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, r.tenant_id);
            if (r.modality == "COMMITS") {
                bind_sv(h.get(), 2, r.observed_at);
            } else {
                sqlite3_bind_null(h.get(), 2);
            }
            bind_sv(h.get(), 3, stmt_id);
            if (sqlite3_step(h.get()) == SQLITE_DONE) count++;
        }
    }

    return count;
}

// ── Event row ────────────────────────────────────────────────────────────────

struct EventRow {
    std::string event_id;
    std::string event_type;
    std::string primary_id;
    int         outbox_sequence = 0;
};

}  // namespace

// ── Constructor ──────────────────────────────────────────────────────────────

ProjectionMaintainer::ProjectionMaintainer(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {
    (void)adapter_;
}

// ── tick_one_batch ───────────────────────────────────────────────────────────

MaintainerStats ProjectionMaintainer::tick_one_batch(
    persistence::Connection& conn, std::string_view now_iso) {

    MaintainerStats stats;

    // 1. Read checkpoint.
    int last_seq = 0;
    try {
        last_seq = read_checkpoint(conn);
    } catch (...) {
        return stats;  // cannot read checkpoint — no-op
    }

    // 2. SELECT events after checkpoint.
    std::vector<EventRow> batch;
    {
        const char* sql =
            "SELECT event_id, event_type, primary_id, outbox_sequence "
            "FROM bus_events "
            "WHERE outbox_sequence > ? "
            "ORDER BY outbox_sequence";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            return stats;
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, last_seq);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            EventRow row;
            auto get_text = [&](int col) -> std::string {
                const char* t = reinterpret_cast<const char*>(
                    sqlite3_column_text(h.get(), col));
                return t ? t : "";
            };
            row.event_id        = get_text(0);
            row.event_type      = get_text(1);
            row.primary_id      = get_text(2);
            row.outbox_sequence = sqlite3_column_int(h.get(), 3);
            batch.push_back(std::move(row));
        }
    }

    if (batch.empty())
        return stats;

    // 3. Process each event.
    int max_seq = last_seq;
    for (const auto& ev : batch) {
        if (ev.outbox_sequence > max_seq) max_seq = ev.outbox_sequence;

        // Only handle statement.* events.
        if (ev.event_type.size() < 10 ||
            ev.event_type.substr(0, 10) != "statement.")
            continue;

        stats.events_processed++;

        // Read statement row; skip if gone.
        StmtRow sr = read_stmt(conn, ev.primary_id);
        if (!sr.found) continue;

        const bool is_retiring =
            (sr.consolidation_state == "archived" ||
             sr.consolidation_state == "forgotten");

        if (is_retiring) {
            delete_projection_rows(conn, ev.primary_id);
        } else {
            stats.rows_upserted +=
                upsert_projection_rows(conn, ev.primary_id, sr);
        }
    }

    // 4. Advance checkpoint.
    try {
        write_checkpoint(conn, max_seq, now_iso);
    } catch (...) {
        // best-effort; don't fail the batch
    }

    return stats;
}

// ── rebuild_projection — Task 27 (stub) ─────────────────────────────────────

RebuildReport ProjectionMaintainer::rebuild_projection(
    persistence::Connection& /*conn*/,
    std::string_view /*projection_name*/,
    std::string_view /*now_iso*/) {
    throw std::runtime_error("rebuild_projection: not implemented (Task 27)");
}

}  // namespace starling::projection
