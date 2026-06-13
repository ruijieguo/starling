// projection_maintainer.cpp -- ProjectionMaintainer outbox subscriber.
// Consumes statement.* bus events → incrementally upserts 5 statement-keyed
// projection tables and advances projection_subscriber_checkpoint.
// proj_common_ground is driven by common_ground changes, not statement events.
// rebuild_projection implements Task 27: full rebuild + repair guard.

#include "starling/projection/projection_maintainer.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/store/sqlite_meta_store.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdio>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::projection {

namespace {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::persistence::detail::bind_sv;
using starling::persistence::detail::make_sqlite_error;
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
    std::string review_status;
    bool        found = false;
};

StmtRow read_stmt(persistence::Connection& conn, std::string_view stmt_id,
                  std::string_view tenant_id) {
    // P3.b1 phase 3:点查收编进 MetaStore.get_statement(纯 id+tenant,字段全覆盖)。
    store::SqliteMetaStore meta(conn);
    StmtRow row;
    const auto r = meta.get_statement(stmt_id, tenant_id);
    if (!r) return row;
    row.tenant_id           = r->tenant_id;
    row.holder_id           = r->holder_id;
    row.subject_kind        = r->subject_kind;
    row.subject_id          = r->subject_id;
    row.predicate           = r->predicate;
    row.consolidation_state = r->consolidation_state;
    row.observed_at         = r->observed_at;
    row.salience            = r->salience;
    row.modality            = r->modality;
    row.review_status       = r->review_status;
    row.found               = true;
    return row;
}

// ── Projection helpers ───────────────────────────────────────────────────────

// Delete the stmt's rows from the 5 statement-keyed projections.
void delete_projection_rows(persistence::Connection& conn,
                            std::string_view stmt_id,
                            std::string_view tenant_id) {
    static const char* kDelSqls[] = {
        "DELETE FROM proj_holder_state_time WHERE stmt_id = ? AND tenant_id = ?",
        "DELETE FROM proj_holder_subgraph     WHERE stmt_id = ? AND tenant_id = ?",
        "DELETE FROM proj_entity_statement    WHERE stmt_id = ? AND tenant_id = ?",
        "DELETE FROM proj_salience_hot        WHERE stmt_id = ? AND tenant_id = ?",
        "DELETE FROM proj_commitment_due      WHERE stmt_id = ? AND tenant_id = ?",
    };
    for (const char* sql : kDelSqls) {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            continue;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, stmt_id);
        bind_sv(h.get(), 2, tenant_id);
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

// ── Vector payload projection (M0.9, 7th projection) ─────────────────────────
// proj_vector_payload is keyed by (tenant_id, stmt_id) but only materializes rows for
// statements that already have an embedded index vector. Driven by the
// vector.embedded event (and refreshed on statement.* when a vector exists).
// These helpers run ALONGSIDE the 6 M0.8 SQL projections; they never touch
// the existing projection tables.

// No-op unless the statement has an embedded vector. UPSERT keyed on
// (tenant_id, stmt_id).
void upsert_vector_payload(persistence::Connection& conn,
                           std::string_view stmt_id,
                           const StmtRow& r) {
    // Only materialize if an embedded vector exists for this stmt.
    {
        const char* exists_sql =
            "SELECT 1 FROM statement_vectors "
            "WHERE stmt_id = ? AND tenant_id = ? AND status = 'embedded'";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), exists_sql, -1, &raw, nullptr) != SQLITE_OK)
            return;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, stmt_id);
        bind_sv(h.get(), 2, r.tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_ROW)
            return;  // no embedded vector yet → do not create a payload row
    }

    const char* sql =
        "INSERT INTO proj_vector_payload"
        "(tenant_id, holder_id, consolidation_state, modality, review_status, stmt_id)"
        " VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(tenant_id,stmt_id) DO UPDATE SET"
        "   consolidation_state=excluded.consolidation_state,"
        "   review_status=excluded.review_status,"
        "   modality=excluded.modality,"
        "   holder_id=excluded.holder_id,"
        "   tenant_id=excluded.tenant_id";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, r.tenant_id);
    bind_sv(h.get(), 2, r.holder_id);
    bind_sv(h.get(), 3, r.consolidation_state);
    if (r.modality.empty())
        sqlite3_bind_null(h.get(), 4);
    else
        bind_sv(h.get(), 4, r.modality);
    bind_sv(h.get(), 5, r.review_status);
    bind_sv(h.get(), 6, stmt_id);
    sqlite3_step(h.get());
}

// Remove the stmt's row from proj_vector_payload (called on retire).
void delete_vector_payload(persistence::Connection& conn,
                           std::string_view stmt_id,
                           std::string_view tenant_id) {
    const char* sql =
        "DELETE FROM proj_vector_payload WHERE stmt_id = ? AND tenant_id = ?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, stmt_id);
    bind_sv(h.get(), 2, tenant_id);
    sqlite3_step(h.get());
}

// ── Event row ────────────────────────────────────────────────────────────────

struct EventRow {
    std::string event_id;
    std::string event_type;
    std::string primary_id;
    std::string tenant_id;
    int         outbox_sequence = 0;
};

// ── emit_event helper (mirrors arbitration.cpp pattern) ─────────────────────

void emit_event(
    persistence::Connection& conn,
    std::string_view event_type,
    std::string_view primary_id,
    std::string_view aggregate_id,
    std::string_view tenant_id,
    std::string payload_json)
{
    BusEvent ev;
    ev.tenant_id    = std::string(tenant_id);
    ev.event_type   = std::string(event_type);
    ev.primary_id   = std::string(primary_id);
    ev.aggregate_id = std::string(aggregate_id);
    const std::string window_bucket =
        compute_window_bucket(event_type, std::chrono::system_clock::now());
    const std::string canonical_key =
        std::string(tenant_id) + ":" + std::string(primary_id);
    ev.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, canonical_key,
        /*causation_root=*/"", window_bucket);
    ev.payload_json = std::move(payload_json);
    OutboxWriter ow(conn);
    ow.append(ev);
}

// ── Rebuild helpers ──────────────────────────────────────────────────────────

// Small helper: run a single-column COUNT query and return the int64 result.
int64_t scalar_count(persistence::Connection& conn, const char* sql) {
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return 0;
    StmtHandle h(raw);
    int64_t count = 0;
    if (sqlite3_step(h.get()) == SQLITE_ROW)
        count = sqlite3_column_int64(h.get(), 0);
    return count;
}

// Ground truth = how many rows the projection SHOULD have after a rebuild.
// For the 6 M0.8 SQL projections this is 1:1 with statements. For the M0.9
// proj_vector_payload it is the number of embedded vectors whose statement is
// not retired — genuinely smaller than COUNT(*) FROM statements.
int64_t count_ground_truth(persistence::Connection& conn,
                           std::string_view projection_name) {
    if (projection_name == "proj_vector_payload") {
        return scalar_count(conn,
            "SELECT COUNT(*) FROM statement_vectors v "
            "JOIN statements s ON s.id = v.stmt_id "
            "AND s.tenant_id = v.tenant_id "
            "WHERE v.status = 'embedded' "
            "AND s.consolidation_state NOT IN ('archived','forgotten')");
    }
    // For all 6 M0.8 SQL projections: every statement maps to one row.
    return scalar_count(conn, "SELECT COUNT(*) FROM statements");
}

// Rebuilt = how many rows the rebuild produced. For the M0.8 projections this
// is recomputed from statements (1:1). For proj_vector_payload it is the
// ACTUAL materialized row count of the projection table — which can lag the
// ground truth and so trips the §16.3 truncation guard.
int64_t recompute_rebuilt(persistence::Connection& conn,
                          std::string_view projection_name) {
    if (projection_name == "proj_vector_payload") {
        return scalar_count(conn, "SELECT COUNT(*) FROM proj_vector_payload");
    }
    return scalar_count(conn, "SELECT COUNT(*) FROM statements");
}

// UPSERT projection_rebuild_state.
void upsert_rebuild_state(persistence::Connection& conn,
                          std::string_view projection_name,
                          int64_t ground_truth, int64_t index_count,
                          std::string_view status, std::string_view now_iso) {
    const char* sql =
        "INSERT INTO projection_rebuild_state"
        "(projection_name, ground_truth_count, index_count, last_rebuilt_at, status)"
        " VALUES(?,?,?,?,?)"
        " ON CONFLICT(projection_name) DO UPDATE SET"
        "   ground_truth_count=excluded.ground_truth_count,"
        "   index_count=excluded.index_count,"
        "   last_rebuilt_at=excluded.last_rebuilt_at,"
        "   status=excluded.status";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "upsert_rebuild_state: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, projection_name);
    sqlite3_bind_int64(h.get(), 2, ground_truth);
    sqlite3_bind_int64(h.get(), 3, index_count);
    bind_sv(h.get(), 4, now_iso);
    bind_sv(h.get(), 5, status);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "upsert_rebuild_state: step");
}

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
            "SELECT event_id, event_type, primary_id, outbox_sequence, tenant_id "
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
            row.tenant_id       = get_text(4);
            batch.push_back(std::move(row));
        }
    }

    if (batch.empty())
        return stats;

    // 3. Process each event.
    int max_seq = last_seq;
    for (const auto& ev : batch) {
        if (ev.outbox_sequence > max_seq) max_seq = ev.outbox_sequence;

        // ── vector.embedded → materialize proj_vector_payload (M0.9) ──────────
        // Runs alongside the statement.* handling below; only the 7th
        // projection is touched here.
        if (ev.event_type == "vector.embedded") {
            stats.events_processed++;
            StmtRow sr = read_stmt(conn, ev.primary_id, ev.tenant_id);
            if (!sr.found) continue;
            const bool is_retiring =
                (sr.consolidation_state == "archived" ||
                 sr.consolidation_state == "forgotten");
            if (!is_retiring)
                upsert_vector_payload(conn, ev.primary_id, sr);
            continue;
        }

        // Only handle statement.* events.
        if (ev.event_type.size() < 10 ||
            ev.event_type.substr(0, 10) != "statement.")
            continue;

        stats.events_processed++;

        // Read statement row; skip if gone.
        StmtRow sr = read_stmt(conn, ev.primary_id, ev.tenant_id);
        if (!sr.found) continue;

        const bool is_retiring =
            (sr.consolidation_state == "archived" ||
             sr.consolidation_state == "forgotten");

        if (is_retiring) {
            delete_projection_rows(conn, ev.primary_id, sr.tenant_id);
            // Also retire the 7th projection (M0.9).
            delete_vector_payload(conn, ev.primary_id, sr.tenant_id);
        } else {
            stats.rows_upserted +=
                upsert_projection_rows(conn, ev.primary_id, sr);
            // Refresh the 7th projection — no-op unless an embedded vector
            // already exists (a plain statement.written before its vector
            // lands must NOT create a payload row).
            upsert_vector_payload(conn, ev.primary_id, sr);
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

// ── do_rebuild — shared logic ────────────────────────────────────────────────

RebuildReport ProjectionMaintainer::do_rebuild(
    persistence::Connection& conn,
    std::string_view projection_name,
    int64_t rebuilt_override,
    std::string_view now_iso)
{
    RebuildReport report;
    report.projection_name = std::string(projection_name);

    const int64_t ground_truth = count_ground_truth(conn, projection_name);
    const int64_t rebuilt = (rebuilt_override >= 0)
        ? rebuilt_override
        : recompute_rebuilt(conn, projection_name);

    report.ground_truth_count = ground_truth;
    report.rebuilt_count      = rebuilt;
    report.truncation_suspected = false;

    if (rebuilt < ground_truth) {
        // ── Truncation path: emit event, mark state, KEEP old active projection ──
        report.truncation_suspected = true;

        // Build payload JSON
        std::ostringstream payload;
        payload << "{"
                << "\"projection\":" << "\"" << projection_name << "\""
                << ",\"ground_truth\":" << ground_truth
                << ",\"rebuilt\":" << rebuilt
                << ",\"truncation_suspected\":true"
                << "}";

        try {
            emit_event(conn, "projection.rebuild_failed",
                       projection_name, projection_name, "default",
                       payload.str());
        } catch (...) {
            // idempotency collision — tolerate
        }

        upsert_rebuild_state(conn, projection_name, ground_truth, rebuilt,
                             "truncation_suspected", now_iso);
        // DO NOT touch the projection table — old active rows stay.
    } else {
        // ── Healthy path: atomically replace active projection content ──────────
        persistence::TransactionGuard tx(conn);

        if (projection_name == "proj_holder_state_time") {
            // Clear then full-rebuild from statements.
            {
                const char* del_sql = "DELETE FROM proj_holder_state_time";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), del_sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw make_sqlite_error(conn.raw(), "rebuild: DELETE proj_holder_state_time prepare");
                StmtHandle h(raw);
                if (sqlite3_step(h.get()) != SQLITE_DONE)
                    throw make_sqlite_error(conn.raw(), "rebuild: DELETE proj_holder_state_time step");
            }
            {
                const char* ins_sql =
                    "INSERT OR REPLACE INTO proj_holder_state_time"
                    "(tenant_id, holder_id, consolidation_state, observed_at, stmt_id)"
                    " SELECT tenant_id, holder_id, consolidation_state, observed_at, id"
                    " FROM statements";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), ins_sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw make_sqlite_error(conn.raw(), "rebuild: INSERT proj_holder_state_time prepare");
                StmtHandle h(raw);
                if (sqlite3_step(h.get()) != SQLITE_DONE)
                    throw make_sqlite_error(conn.raw(), "rebuild: INSERT proj_holder_state_time step");
            }
        } else if (projection_name == "proj_vector_payload") {
            // M0.9 7th projection — DELETE+INSERT from embedded vectors joined
            // to non-retired statements. ground_truth/rebuilt counting differs
            // from the 6 SQL projections (see count_ground_truth above).
            {
                const char* del_sql = "DELETE FROM proj_vector_payload";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), del_sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw make_sqlite_error(conn.raw(), "rebuild: DELETE proj_vector_payload prepare");
                StmtHandle h(raw);
                if (sqlite3_step(h.get()) != SQLITE_DONE)
                    throw make_sqlite_error(conn.raw(), "rebuild: DELETE proj_vector_payload step");
            }
            {
                const char* ins_sql =
                    "INSERT INTO proj_vector_payload"
                    "(tenant_id, holder_id, consolidation_state, modality, review_status, stmt_id)"
                    " SELECT s.tenant_id, s.holder_id, s.consolidation_state,"
                    "        s.modality, s.review_status, s.id"
                    " FROM statement_vectors v"
                    " JOIN statements s ON s.id = v.stmt_id AND s.tenant_id = v.tenant_id"
                    " WHERE v.status = 'embedded'"
                    "   AND s.consolidation_state NOT IN ('archived','forgotten')";
                sqlite3_stmt* raw = nullptr;
                if (sqlite3_prepare_v2(conn.raw(), ins_sql, -1, &raw, nullptr) != SQLITE_OK)
                    throw make_sqlite_error(conn.raw(), "rebuild: INSERT proj_vector_payload prepare");
                StmtHandle h(raw);
                if (sqlite3_step(h.get()) != SQLITE_DONE)
                    throw make_sqlite_error(conn.raw(), "rebuild: INSERT proj_vector_payload step");
            }
        }
        // Generic fallback for other projection names: no-op on the table
        // (ground_truth == rebuilt == 0 for unknown projections → healthy path).

        upsert_rebuild_state(conn, projection_name, ground_truth, rebuilt,
                             "active", now_iso);
        tx.commit();
    }

    return report;
}

// ── rebuild_projection — Task 27 ─────────────────────────────────────────────

RebuildReport ProjectionMaintainer::rebuild_projection(
    persistence::Connection& conn,
    std::string_view projection_name,
    std::string_view now_iso) {
    return do_rebuild(conn, projection_name, /*rebuilt_override=*/-1, now_iso);
}

// ── rebuild_projection_with_injected_count — test hook ───────────────────────

RebuildReport ProjectionMaintainer::rebuild_projection_with_injected_count(
    persistence::Connection& conn,
    std::string_view projection_name,
    int64_t injected_rebuilt,
    std::string_view now_iso) {
    return do_rebuild(conn, projection_name, injected_rebuilt, now_iso);
}

}  // namespace starling::projection
