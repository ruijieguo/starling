// commitment_engine.cpp -- P2.c Commitment 五态机 (spec §5).
// created→ACTIVE / fulfill / withdraw / on_deadline_expired (broken_count<3→
// BROKEN, >=3→auto WITHDRAWN) / renegotiate (supersedes chain<3→RENEGOTIATED +
// new ACTIVE, >=3→renegotiation_blocked). Emits commitment.* outbox events.

#include "starling/prospective/commitment_engine.hpp"

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

namespace starling::prospective {

namespace {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// 32 random hex chars for new edge ids (mirrors arbitration.cpp).
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

// emit_event helper (copied from projection_maintainer.cpp pattern).
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
    } catch (const persistence::SqliteError& e) {
        // ONLY tolerate the idempotency_key UNIQUE collision: a commitment.* event
        // with the same (event_type, aggregate_id, primary_id) re-emitted inside
        // the same window bucket coalesces (the state UPDATE has already committed;
        // the duplicate event is dropped). Any other SQLite error (I/O, busy,
        // schema) is a real failure and must propagate — a broad catch(...) would
        // hide it. SqliteError::code() carries the extended error code; its low
        // 8 bits == SQLITE_CONSTRAINT for all constraint violations.
        if ((e.code() & 0xFF) != SQLITE_CONSTRAINT)
            throw;
    }
}

// UPSERT a commitment row into ACTIVE state with the given deadline/broken_count.
// deadline bound as NULL when empty. created_at and updated_at set to now. The
// conflict key is composite (tenant_id, stmt_id) — statements PK is (id,
// tenant_id), so a bare stmt_id collides across tenants. The conflict update only
// re-activates non-terminal rows: a reprocessed statement.written must NOT
// resurrect a FULFILLED/WITHDRAWN commitment.
void upsert_active_commitment(persistence::Connection& conn,
                              std::string_view stmt_id,
                              std::string_view tenant_id,
                              std::string_view deadline,
                              int broken_count,
                              std::string_view now_iso) {
    const char* sql =
        "INSERT INTO commitments"
        "(stmt_id,tenant_id,state,broken_count,deadline,created_at,updated_at)"
        " VALUES(?,?,'ACTIVE',?,?,?,?)"
        " ON CONFLICT(tenant_id, stmt_id) DO UPDATE SET"
        "   state='ACTIVE',"
        "   broken_count=excluded.broken_count,"
        "   deadline=excluded.deadline,"
        "   updated_at=excluded.updated_at"
        " WHERE commitments.state NOT IN ('FULFILLED','WITHDRAWN')";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "commitment: upsert active prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, stmt_id);
    bind_sv(h.get(), 2, tenant_id);
    sqlite3_bind_int(h.get(), 3, broken_count);
    if (deadline.empty())
        sqlite3_bind_null(h.get(), 4);
    else
        bind_sv(h.get(), 4, deadline);
    bind_sv(h.get(), 5, now_iso);
    bind_sv(h.get(), 6, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "commitment: upsert active step");
}

// INSERT OR IGNORE a self-protection row (commitment protects its own stmt).
void insert_self_protection(persistence::Connection& conn,
                            std::string_view tenant_id,
                            std::string_view stmt_id) {
    const char* sql =
        "INSERT OR IGNORE INTO commitment_protection"
        "(tenant_id, commitment_stmt_id, protected_stmt_id) VALUES(?, ?, ?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "commitment: insert protection prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, stmt_id);
    bind_sv(h.get(), 3, stmt_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "commitment: insert protection step");
}

// Simple state-only UPDATE with updated_at, scoped to (tenant_id, stmt_id).
void update_state(persistence::Connection& conn, std::string_view stmt_id,
                  std::string_view tenant_id, std::string_view state,
                  std::string_view now_iso) {
    const char* sql =
        "UPDATE commitments SET state=?, updated_at=? "
        "WHERE tenant_id=? AND stmt_id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "commitment: update state prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, state);
    bind_sv(h.get(), 2, now_iso);
    bind_sv(h.get(), 3, tenant_id);
    bind_sv(h.get(), 4, stmt_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(conn.raw(), "commitment: update state step");
}

// supersedes chain length ENDING at stmt_id: count stmt_id + each predecessor it
// superseded. A renegotiation inserts edge src=new, dst=old ("new supersedes
// old"); following src=cur→dst walks backward through the chain.
int supersedes_chain_length(persistence::Connection& conn, std::string_view start,
                            std::string_view tenant_id) {
    int count = 1;
    std::string cur(start);
    const char* sql =
        "SELECT dst_id FROM statement_edges "
        "WHERE src_id=? AND tenant_id=? AND edge_kind='supersedes' LIMIT 1";
    // Bound the walk: the caller only needs to distinguish < kMaxRenegotiationChain
    // from >=, so stop once count exceeds the cap. This also makes a cyclic
    // supersedes edge set (which a misbehaving caller could create) terminate —
    // a cycle counts as >= cap, hence correctly blocked.
    while (count <= kMaxRenegotiationChain) {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            break;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, cur);
        bind_sv(h.get(), 2, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_ROW)
            break;
        const auto* t = sqlite3_column_text(h.get(), 0);
        if (!t)
            break;
        cur = reinterpret_cast<const char*>(t);
        ++count;
    }
    return count;
}

}  // namespace

// ── create_from_statement ────────────────────────────────────────────────────

void CommitmentEngine::create_from_statement(persistence::Connection& conn,
                                             std::string_view stmt_id,
                                             std::string_view tenant_id,
                                             std::string_view deadline,
                                             std::string_view now_iso) {
    upsert_active_commitment(conn, stmt_id, tenant_id, deadline, /*broken_count=*/0,
                             now_iso);
    insert_self_protection(conn, tenant_id, stmt_id);
    emit_event(conn, "commitment.active_holding", stmt_id, stmt_id, tenant_id, "{}");
}

// ── fulfill ──────────────────────────────────────────────────────────────────

void CommitmentEngine::fulfill(persistence::Connection& conn,
                               std::string_view stmt_id,
                               std::string_view tenant_id,
                               std::string_view now_iso) {
    update_state(conn, stmt_id, tenant_id, "FULFILLED", now_iso);
    emit_event(conn, "commitment.fulfilled", stmt_id, stmt_id, tenant_id, "{}");
    emit_event(conn, "commitment.released", stmt_id, stmt_id, tenant_id, "{}");
}

// ── withdraw ─────────────────────────────────────────────────────────────────

void CommitmentEngine::withdraw(persistence::Connection& conn,
                                std::string_view stmt_id,
                                std::string_view tenant_id,
                                std::string_view now_iso) {
    update_state(conn, stmt_id, tenant_id, "WITHDRAWN", now_iso);
    emit_event(conn, "commitment.withdrawn", stmt_id, stmt_id, tenant_id, "{}");
    emit_event(conn, "commitment.released", stmt_id, stmt_id, tenant_id, "{}");
}

// ── on_deadline_expired ──────────────────────────────────────────────────────

void CommitmentEngine::on_deadline_expired(persistence::Connection& conn,
                                           std::string_view stmt_id,
                                           std::string_view tenant_id,
                                           std::string_view now_iso) {
    // Read current (broken_count, state), scoped to (tenant_id, stmt_id).
    int broken_count = 0;
    std::string state;
    bool found = false;
    {
        const char* sql =
            "SELECT broken_count, state FROM commitments "
            "WHERE tenant_id=? AND stmt_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(conn.raw(), "commitment: read broken_count prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, tenant_id);
        bind_sv(h.get(), 2, stmt_id);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            broken_count = sqlite3_column_int(h.get(), 0);
            const auto* t = sqlite3_column_text(h.get(), 1);
            state = t ? reinterpret_cast<const char*>(t) : "";
            found = true;
        }
    }

    // Source-state guard: only an ACTIVE commitment breaks/auto-withdraws on a
    // deadline. A terminal/renegotiated row (e.g. a stale deadline that re-fired
    // after the commitment was already fulfilled) must not transition.
    if (!found || state != "ACTIVE")
        return;

    if (broken_count >= kMaxBrokenCount) {
        // Chronic failure → auto WITHDRAWN.
        // TODO(P3): cognizer_hub.downgrade_trust_priors — emitting the event is
        // the P2.c contract; trust_priors downgrade is deferred.
        update_state(conn, stmt_id, tenant_id, "WITHDRAWN", now_iso);
        emit_event(conn, "commitment.auto_withdrawn", stmt_id, stmt_id, tenant_id,
                   R"({"reason":"chronic_failure"})");
    } else {
        const char* sql =
            "UPDATE commitments SET state='BROKEN', broken_count=broken_count+1, "
            "updated_at=? WHERE tenant_id=? AND stmt_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(conn.raw(), "commitment: broken update prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, now_iso);
        bind_sv(h.get(), 2, tenant_id);
        bind_sv(h.get(), 3, stmt_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(conn.raw(), "commitment: broken update step");
        emit_event(conn, "commitment.broken", stmt_id, stmt_id, tenant_id, "{}");
    }
}

// ── renegotiate ──────────────────────────────────────────────────────────────

bool CommitmentEngine::renegotiate(persistence::Connection& conn,
                                   std::string_view old_stmt_id,
                                   std::string_view new_stmt_id,
                                   std::string_view tenant_id,
                                   std::string_view now_iso) {
    // Old (broken_count, state), scoped to (tenant_id, old_stmt_id). tenant_id is
    // supplied by the caller (which knows it) rather than read from the row.
    int old_broken_count = 0;
    std::string old_state;
    bool found = false;
    {
        const char* sql =
            "SELECT broken_count, state FROM commitments "
            "WHERE tenant_id=? AND stmt_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(conn.raw(), "commitment: renegotiate read old prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, tenant_id);
        bind_sv(h.get(), 2, old_stmt_id);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            old_broken_count = sqlite3_column_int(h.get(), 0);
            const auto* t = sqlite3_column_text(h.get(), 1);
            old_state = t ? reinterpret_cast<const char*>(t) : "";
            found = true;
        }
    }

    // Source-state guard: only an ACTIVE or BROKEN commitment can be a
    // renegotiation source. A FULFILLED/WITHDRAWN/RENEGOTIATED (or missing) source
    // returns false, emits nothing, and creates no supersedes edge.
    if (!found || (old_state != "ACTIVE" && old_state != "BROKEN"))
        return false;

    const int chain_len = supersedes_chain_length(conn, old_stmt_id, tenant_id);
    if (chain_len >= kMaxRenegotiationChain) {
        emit_event(conn, "commitment.renegotiation_blocked", old_stmt_id, old_stmt_id,
                   tenant_id,
                   std::string(R"({"chain_len":)") + std::to_string(chain_len) + "}");
        return false;
    }

    // INSERT supersedes edge: src=new, dst=old ("new supersedes old").
    {
        const char* sql =
            "INSERT INTO statement_edges"
            "(id,tenant_id,src_id,dst_id,edge_kind,created_at)"
            " VALUES(?,?,?,?,'supersedes',?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(conn.raw(), "commitment: renegotiate edge prepare");
        StmtHandle h(raw);
        const std::string edge_id = random_hex_32();
        bind_sv(h.get(), 1, edge_id);
        bind_sv(h.get(), 2, tenant_id);
        bind_sv(h.get(), 3, new_stmt_id);
        bind_sv(h.get(), 4, old_stmt_id);
        bind_sv(h.get(), 5, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(conn.raw(), "commitment: renegotiate edge step");
    }

    // Old commitment → RENEGOTIATED.
    update_state(conn, old_stmt_id, tenant_id, "RENEGOTIATED", now_iso);

    // New commitment → ACTIVE, carrying over the old broken_count so chronic
    // failure persists across renegotiation. deadline NULL (carried fresh).
    upsert_active_commitment(conn, new_stmt_id, tenant_id, /*deadline=*/"",
                             old_broken_count, now_iso);
    insert_self_protection(conn, tenant_id, new_stmt_id);

    emit_event(conn, "commitment.renegotiated", new_stmt_id, new_stmt_id, tenant_id,
               std::string(R"({"old_stmt_id":")") + std::string(old_stmt_id) + "\"}");
    return true;
}

}  // namespace starling::prospective
