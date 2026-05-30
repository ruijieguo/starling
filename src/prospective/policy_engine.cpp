// policy_engine.cpp -- P2.c PolicyEngine drives the Prospective Loop (spec §3.2).
// Stateless-per-tick, SQL-backed. Two entry points:
//   run_post_write — SubscriberPump after each Bus.write: checkpoint-driven
//     consumption of new bus_events. statement.written(COMMITS) → ACTIVE
//     commitment + TimeTrigger; armed event/state triggers evaluated against the
//     event (hit → commitment.fire); commitment.fulfilled/withdrawn → transitions.
//   tick — runtime idle loop: fire due TimeTriggers; ACTIVE commitments whose
//     deadline passed → on_deadline_expired (BROKEN / auto-WITHDRAWN).
// Checkpoint table is policy_engine_checkpoint. Collect rows before writes (no
// nested-cursor writes). emit_event tolerates idempotency collisions.

#include "starling/prospective/policy_engine.hpp"

#include "starling/prospective/trigger.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <random>
#include <string>
#include <string_view>
#include <vector>

namespace starling::prospective {

namespace {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// 32 random hex chars for new trigger ids (mirrors arbitration.cpp).
std::string random_hex_32() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

// emit_event helper (copied from projection_maintainer.cpp pattern). The
// try/catch tolerates idempotency_key UNIQUE collisions — commitment.fire can
// re-emit for the same commitment inside the same window bucket.
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
    ev.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, primary_id,
        /*causation_root=*/"", window_bucket);
    ev.payload_json = std::move(payload_json);
    OutboxWriter ow(conn);
    try {
        ow.append(ev);
    } catch (...) {
        // idempotency collision — tolerate (commitment.fire may repeat).
    }
}

// ── Row structs ──────────────────────────────────────────────────────────────

struct EventRow {
    std::string event_type;
    std::string primary_id;
    int         outbox_sequence = 0;
};

struct StmtMeta {
    std::string modality;
    std::string tenant_id;
    std::string event_time_end;
    std::string observed_at;
    bool        found = false;
};

// An armed trigger joined to its ACTIVE commitment.
struct TriggerRow {
    std::string id;
    std::string kind;
    std::string spec_json;
    std::string commitment_stmt_id;
    std::string tenant_id;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

std::string col_text(sqlite3_stmt* s, int col) {
    const auto* t = sqlite3_column_text(s, col);
    return t ? reinterpret_cast<const char*>(t) : "";
}

// Read policy_engine_checkpoint.seq; default 0 if missing/unreadable.
int read_checkpoint(persistence::Connection& conn) {
    const char* sql = "SELECT seq FROM policy_engine_checkpoint WHERE id=1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return 0;
    StmtHandle h(raw);
    if (sqlite3_step(h.get()) == SQLITE_ROW)
        return sqlite3_column_int(h.get(), 0);
    return 0;
}

void write_checkpoint(persistence::Connection& conn, int new_seq) {
    const char* sql = "UPDATE policy_engine_checkpoint SET seq=? WHERE id=1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return;
    StmtHandle h(raw);
    sqlite3_bind_int(h.get(), 1, new_seq);
    sqlite3_step(h.get());
}

// Look up modality/tenant/deadline columns for a statement.
StmtMeta read_stmt_meta(persistence::Connection& conn, std::string_view stmt_id) {
    const char* sql =
        "SELECT modality, tenant_id, event_time_end, observed_at "
        "FROM statements WHERE id = ?";
    sqlite3_stmt* raw = nullptr;
    StmtMeta m;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return m;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, stmt_id);
    if (sqlite3_step(h.get()) == SQLITE_ROW) {
        m.modality       = col_text(h.get(), 0);
        m.tenant_id      = col_text(h.get(), 1);
        m.event_time_end = col_text(h.get(), 2);
        m.observed_at    = col_text(h.get(), 3);
        m.found          = true;
    }
    return m;
}

// INSERT an armed time trigger for a freshly created commitment.
void register_time_trigger(persistence::Connection& conn,
                           std::string_view commitment_stmt_id,
                           std::string_view tenant_id,
                           std::string_view deadline,
                           std::string_view now_iso) {
    const char* sql =
        "INSERT INTO commitment_triggers"
        "(id, commitment_stmt_id, tenant_id, kind, spec_json, status, created_at)"
        " VALUES(?,?,?,'time',?,'armed',?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "policy_engine: register time trigger prepare");
    StmtHandle h(raw);
    const std::string id = random_hex_32();
    const std::string spec =
        std::string(R"({"at":")") + std::string(deadline) + "\"}";
    bind_sv(h.get(), 1, id);
    bind_sv(h.get(), 2, commitment_stmt_id);
    bind_sv(h.get(), 3, tenant_id);
    bind_sv(h.get(), 4, spec);
    bind_sv(h.get(), 5, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "policy_engine: register time trigger step");
}

// Collect all armed event/state triggers whose commitment is ACTIVE.
std::vector<TriggerRow> collect_armed_event_state_triggers(
    persistence::Connection& conn) {
    std::vector<TriggerRow> rows;
    const char* sql =
        "SELECT t.id, t.kind, t.spec_json, t.commitment_stmt_id, t.tenant_id "
        "FROM commitment_triggers t "
        "JOIN commitments c ON c.stmt_id = t.commitment_stmt_id "
        "WHERE t.status='armed' AND t.kind IN ('event','state') "
        "AND c.state='ACTIVE'";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return rows;
    StmtHandle h(raw);
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        TriggerRow r;
        r.id                 = col_text(h.get(), 0);
        r.kind               = col_text(h.get(), 1);
        r.spec_json          = col_text(h.get(), 2);
        r.commitment_stmt_id = col_text(h.get(), 3);
        r.tenant_id          = col_text(h.get(), 4);
        rows.push_back(std::move(r));
    }
    return rows;
}

// Collect all armed time triggers whose commitment is ACTIVE.
std::vector<TriggerRow> collect_armed_time_triggers(persistence::Connection& conn) {
    std::vector<TriggerRow> rows;
    const char* sql =
        "SELECT t.id, t.commitment_stmt_id, t.spec_json, t.tenant_id "
        "FROM commitment_triggers t "
        "JOIN commitments c ON c.stmt_id = t.commitment_stmt_id "
        "WHERE t.kind='time' AND t.status='armed' AND c.state='ACTIVE'";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return rows;
    StmtHandle h(raw);
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        TriggerRow r;
        r.id                 = col_text(h.get(), 0);
        r.commitment_stmt_id = col_text(h.get(), 1);
        r.spec_json          = col_text(h.get(), 2);
        r.tenant_id          = col_text(h.get(), 3);
        r.kind               = "time";
        rows.push_back(std::move(r));
    }
    return rows;
}

// Collect stmt_ids of ACTIVE commitments whose deadline has passed.
std::vector<std::string> collect_expired_active_commitments(
    persistence::Connection& conn, std::string_view now_iso) {
    std::vector<std::string> ids;
    const char* sql =
        "SELECT stmt_id FROM commitments "
        "WHERE state='ACTIVE' AND deadline IS NOT NULL AND deadline <= ?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return ids;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, now_iso);
    while (sqlite3_step(h.get()) == SQLITE_ROW)
        ids.push_back(col_text(h.get(), 0));
    return ids;
}

// Read a commitment's current state; "" if absent.
std::string read_commitment_state(persistence::Connection& conn,
                                  std::string_view stmt_id) {
    const char* sql = "SELECT state FROM commitments WHERE stmt_id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return "";
    StmtHandle h(raw);
    bind_sv(h.get(), 1, stmt_id);
    if (sqlite3_step(h.get()) == SQLITE_ROW)
        return col_text(h.get(), 0);
    return "";
}

// Mark a trigger fired.
void mark_trigger_fired(persistence::Connection& conn, std::string_view id) {
    const char* sql = "UPDATE commitment_triggers SET status='fired' WHERE id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return;
    StmtHandle h(raw);
    bind_sv(h.get(), 1, id);
    sqlite3_step(h.get());
}

}  // namespace

// ── run_post_write ───────────────────────────────────────────────────────────

void PolicyEngine::run_post_write(persistence::Connection& conn,
                                  std::string_view now_iso) {
    // 1. Read checkpoint.
    const int last_seq = read_checkpoint(conn);

    // 2. Collect new bus_events (ordered).
    std::vector<EventRow> batch;
    {
        const char* sql =
            "SELECT event_type, primary_id, outbox_sequence "
            "FROM bus_events WHERE outbox_sequence > ? "
            "ORDER BY outbox_sequence";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            return;
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, last_seq);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            EventRow r;
            r.event_type      = col_text(h.get(), 0);
            r.primary_id      = col_text(h.get(), 1);
            r.outbox_sequence = sqlite3_column_int(h.get(), 2);
            batch.push_back(std::move(r));
        }
    }

    if (batch.empty())
        return;

    int max_seq = last_seq;

    // 3. Process each event.
    for (const auto& ev : batch) {
        if (ev.outbox_sequence > max_seq) max_seq = ev.outbox_sequence;

        if (ev.event_type == "statement.written") {
            StmtMeta m = read_stmt_meta(conn, ev.primary_id);
            if (m.found && m.modality == "COMMITS") {
                const std::string deadline =
                    !m.event_time_end.empty() ? m.event_time_end : m.observed_at;
                commitment_engine_.create_from_statement(
                    conn, ev.primary_id, m.tenant_id, deadline, now_iso);
                if (!deadline.empty())
                    register_time_trigger(conn, ev.primary_id, m.tenant_id,
                                          deadline, now_iso);
            }
        } else if (ev.event_type == "commitment.fulfilled") {
            commitment_engine_.fulfill(conn, ev.primary_id, now_iso);
        } else if (ev.event_type == "commitment.withdrawn") {
            commitment_engine_.withdraw(conn, ev.primary_id, now_iso);
        }

        // Evaluate armed event/state triggers against THIS event. Collect first
        // to avoid mutating while a cursor is open.
        std::vector<TriggerRow> triggers =
            collect_armed_event_state_triggers(conn);
        for (const auto& t : triggers) {
            TriggerContext tctx{std::string(now_iso), ev.event_type,
                                ev.primary_id};
            if (evaluate_trigger(conn, t.kind, t.spec_json, tctx)) {
                emit_event(conn, "commitment.fire", t.commitment_stmt_id,
                           t.commitment_stmt_id, t.tenant_id, "{}");
                mark_trigger_fired(conn, t.id);
            }
        }
    }

    // 4. Advance checkpoint (best-effort).
    write_checkpoint(conn, max_seq);
}

// ── tick ─────────────────────────────────────────────────────────────────────

PolicyTickStats PolicyEngine::tick(persistence::Connection& conn,
                                   std::string_view now_iso) {
    PolicyTickStats stats;

    // 1. Fire due TimeTriggers. Collect first to avoid mutating mid-cursor.
    {
        const std::vector<TriggerRow> triggers = collect_armed_time_triggers(conn);
        for (const auto& t : triggers) {
            TriggerContext tctx{std::string(now_iso), /*event_type=*/"",
                                /*event_primary_id=*/""};
            if (evaluate_trigger(conn, "time", t.spec_json, tctx)) {
                emit_event(conn, "commitment.fire", t.commitment_stmt_id,
                           t.commitment_stmt_id, t.tenant_id, "{}");
                mark_trigger_fired(conn, t.id);
                ++stats.fired;
            }
        }
    }

    // 2. Deadline expiry: ACTIVE commitments whose deadline passed →
    //    on_deadline_expired (BROKEN, or auto-WITHDRAWN after chronic failure).
    {
        const std::vector<std::string> expired =
            collect_expired_active_commitments(conn, now_iso);
        for (const auto& stmt_id : expired) {
            commitment_engine_.on_deadline_expired(conn, stmt_id, now_iso);
            if (read_commitment_state(conn, stmt_id) == "WITHDRAWN")
                ++stats.auto_withdrawn;
            else
                ++stats.broken;
        }
    }

    return stats;
}

}  // namespace starling::prospective
