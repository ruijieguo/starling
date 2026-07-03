// commitment_engine.cpp -- P2.c Commitment 五态机 (spec §5).
// created→ACTIVE / fulfill / withdraw / on_deadline_expired (broken_count<3→
// BROKEN, >=3→auto WITHDRAWN) / renegotiate (supersedes chain<3→RENEGOTIATED +
// new ACTIVE, >=3→renegotiation_blocked). Emits commitment.* outbox events.

#include "starling/prospective/commitment_engine.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/store/sqlite_graph_store.hpp"

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
using starling::persistence::detail::bind_sv;
using starling::persistence::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

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
    const std::string canonical_key =
        std::string(tenant_id) + ":" + std::string(primary_id);
    ev.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, canonical_key,
        /*causation_root=*/"", window_bucket);
    ev.payload_json = std::move(payload_json);
    OutboxWriter ow(conn);
    try {
        ow.append(ev);
    } catch (const persistence::SqliteError& e) {
        // ONLY tolerate the idempotency_key UNIQUE collision: a commitment.* event
        // with the same (event_type, aggregate_id, tenant_id, primary_id) re-emitted inside
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

// True if a commitment row already exists for (tenant, stmt). Lets
// create_from_statement stay idempotent: the row upsert + INSERT OR IGNORE
// protection are already safe to repeat, but commitment.active_holding is a
// fail-loud append on a time-independent idempotency_key, so re-materializing an
// existing commitment (a re-delivered statement.written or a tick re-scan) must
// NOT re-emit it — that collides and 500s the tick.
bool commitment_exists(persistence::Connection& conn, std::string_view tenant_id,
                       std::string_view stmt_id) {
    const char* sql = "SELECT 1 FROM commitments WHERE tenant_id=? AND stmt_id=? LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "commitment: exists prepare");
    }
    StmtHandle handle(raw);
    bind_sv(handle.get(), 1, tenant_id);
    bind_sv(handle.get(), 2, stmt_id);
    return sqlite3_step(handle.get()) == SQLITE_ROW;
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

// Guarded state UPDATE: transitions ONLY an ACTIVE commitment to new_state, atomically
// (WHERE ... AND state='ACTIVE'). Returns true iff a row changed — so a settled/missing
// commitment is a no-op the caller can surface (no event emitted, no terminal-state
// overwrite by a stale dashboard or a re-delivered commitment.* event). Drives the
// manual fulfill/withdraw transitions.
bool update_state_if_active(persistence::Connection& conn, std::string_view stmt_id,
                            std::string_view tenant_id, std::string_view new_state,
                            std::string_view now_iso) {
    const char* sql =
        "UPDATE commitments SET state=?, updated_at=? "
        "WHERE tenant_id=? AND stmt_id=? AND state='ACTIVE'";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "commitment: guarded update prepare");
    }
    StmtHandle handle(raw);
    bind_sv(handle.get(), 1, new_state);
    bind_sv(handle.get(), 2, now_iso);
    bind_sv(handle.get(), 3, tenant_id);
    bind_sv(handle.get(), 4, stmt_id);
    if (sqlite3_step(handle.get()) != SQLITE_DONE) {
        throw make_sqlite_error(conn.raw(), "commitment: guarded update step");
    }
    return sqlite3_changes(conn.raw()) > 0;
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
    const bool already = commitment_exists(conn, tenant_id, stmt_id);
    upsert_active_commitment(conn, stmt_id, tenant_id, deadline, /*broken_count=*/0,
                             now_iso);
    insert_self_protection(conn, tenant_id, stmt_id);
    if (!already) {
        emit_event(conn, "commitment.active_holding", stmt_id, stmt_id, tenant_id, "{}");
    }
}

// ── fulfill ──────────────────────────────────────────────────────────────────

// Source-state guard (matches on_deadline_expired / approve_review): only an ACTIVE
// commitment can be manually fulfilled. The guarded UPDATE is atomic, so a settled
// (FULFILLED/WITHDRAWN/FIRED/BROKEN/RENEGOTIATED) or missing commitment is a no-op:
// returns false, emits nothing — a stale dashboard or a re-delivered commitment.fulfilled
// event can neither overwrite a terminal state nor re-emit the released event.
bool CommitmentEngine::fulfill(persistence::Connection& conn,
                               std::string_view stmt_id,
                               std::string_view tenant_id,
                               std::string_view now_iso) {
    governance::require_write_admission(adapter_);   // 门前抛 = 零 DB 写(用类成员 adapter_ 的钩子)
    if (!update_state_if_active(conn, stmt_id, tenant_id, "FULFILLED", now_iso)) {
        return false;
    }
    emit_event(conn, "commitment.fulfilled", stmt_id, stmt_id, tenant_id, "{}");
    emit_event(conn, "commitment.released", stmt_id, stmt_id, tenant_id, "{}");
    return true;
}

// ── withdraw ─────────────────────────────────────────────────────────────────

// Same ACTIVE-only guard as fulfill (see above). withdraw releases the commitment,
// which un-protects the statements it guarded — so silently overwriting a terminal
// state here would have real blast radius; the guard prevents it.
bool CommitmentEngine::withdraw(persistence::Connection& conn,
                                std::string_view stmt_id,
                                std::string_view tenant_id,
                                std::string_view now_iso) {
    governance::require_write_admission(adapter_);   // 门前抛 = 零 DB 写(用类成员 adapter_ 的钩子)
    if (!update_state_if_active(conn, stmt_id, tenant_id, "WITHDRAWN", now_iso)) {
        return false;
    }
    emit_event(conn, "commitment.withdrawn", stmt_id, stmt_id, tenant_id, "{}");
    emit_event(conn, "commitment.released", stmt_id, stmt_id, tenant_id, "{}");
    return true;
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
    // P3.b1 phase 4:边写收编进 GraphStore::insert_edge(同 conn 同事务,created_at
    // 传 now_iso 保持批次时间戳)。
    {
        store::EdgeRecord e;
        e.tenant_id  = std::string(tenant_id);
        e.src_id     = std::string(new_stmt_id);
        e.dst_id     = std::string(old_stmt_id);
        e.edge_kind  = "supersedes";
        e.created_at = now_iso;
        store::SqliteGraphStore(conn).insert_edge(e);
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

// ── pending ──────────────────────────────────────────────────────────────────

std::vector<CommitmentView> CommitmentEngine::pending(persistence::Connection& conn,
        std::string_view tenant_id, std::string_view holder_id, std::string_view interlocutor_id) {
    const char* sql =
        "SELECT c.stmt_id, c.state, COALESCE(c.deadline,''), s.subject_id, s.predicate, s.object_value,"
        "       EXISTS(SELECT 1 FROM commitment_triggers t"
        "              WHERE t.commitment_stmt_id=c.stmt_id AND t.tenant_id=c.tenant_id"
        "                AND t.status='fired') AS fired"
        "  FROM commitments c JOIN statements s ON s.id=c.stmt_id AND s.tenant_id=c.tenant_id"
        " WHERE c.tenant_id=?1 AND c.state='ACTIVE' AND s.holder_id=?2"
        "   AND (?3='' OR s.subject_id=?3 OR s.object_value=?3)"
        " ORDER BY c.deadline";
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "CommitmentEngine::pending prepare");
    StmtHandle h{raw};
    bind_sv(raw, 1, tenant_id);
    bind_sv(raw, 2, holder_id);
    bind_sv(raw, 3, interlocutor_id);
    auto t = [raw](int i){ const unsigned char* c=sqlite3_column_text(raw,i);
                           return c ? std::string(reinterpret_cast<const char*>(c)) : std::string(); };
    std::vector<CommitmentView> out;
    while (sqlite3_step(raw) == SQLITE_ROW) {
        CommitmentView v;
        v.stmt_id=t(0); v.state=t(1); v.deadline=t(2);
        v.subject_id=t(3); v.predicate=t(4); v.object_value=t(5);
        v.fired = sqlite3_column_int(raw, 6) != 0;
        out.push_back(std::move(v));
    }
    return out;
}

}  // namespace starling::prospective
