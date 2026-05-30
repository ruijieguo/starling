#include "starling/reconsolidation/arbitration.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace starling::reconsolidation {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

namespace {

// SAVEPOINT-based atomic guard. Unlike persistence::TransactionGuard (which
// issues BEGIN IMMEDIATE and cannot nest), a SAVEPOINT nests correctly: issued
// outside any transaction it starts one; issued inside an existing transaction
// or savepoint (e.g. SubscriberPump::run_isolated wraps each subscriber in
// `SAVEPOINT sub_reconsolidation`) it nests. close_due_windows runs in BOTH
// contexts — standalone (Python tests) and inside the pump savepoint — so the
// severe 4-item commit must use a savepoint, not BEGIN IMMEDIATE.
class SavepointGuard {
public:
    SavepointGuard(sqlite3* db, std::string name)
        : db_(db), name_(std::move(name)), active_(true) {
        if (sqlite3_exec(db_, ("SAVEPOINT " + name_).c_str(),
                         nullptr, nullptr, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db_, "SavepointGuard: SAVEPOINT");
    }
    ~SavepointGuard() {
        if (active_) {
            // Roll back then release (ROLLBACK TO does not pop the savepoint).
            sqlite3_exec(db_, ("ROLLBACK TO " + name_).c_str(), nullptr, nullptr, nullptr);
            sqlite3_exec(db_, ("RELEASE " + name_).c_str(), nullptr, nullptr, nullptr);
        }
    }
    void release() {
        if (sqlite3_exec(db_, ("RELEASE " + name_).c_str(),
                         nullptr, nullptr, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db_, "SavepointGuard: RELEASE");
        active_ = false;
    }
    SavepointGuard(const SavepointGuard&) = delete;
    SavepointGuard& operator=(const SavepointGuard&) = delete;

private:
    sqlite3* db_;
    std::string name_;
    bool active_;
};

// 32 random hex chars for new statement id / edge id.
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

// Minimal JSON string escaping (keys/values are controlled; no control chars expected)
std::string json_str(std::string_view sv) {
    std::string out;
    out.reserve(sv.size() + 2);
    out.push_back('"');
    for (char c : sv) {
        if (c == '"')       { out += "\\\""; }
        else if (c == '\\') { out += "\\\\"; }
        else                { out.push_back(c); }
    }
    out.push_back('"');
    return out;
}

// Emit a BusEvent for reconsolidation paths (no causation parent).
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
    ow.append(ev);
}

}  // namespace

// ── Public math helpers ──────────────────────────────────────────────────────

double bayesian_update_up(double conf, double strength) {
    const double result = conf + strength * (1.0 - conf);
    return std::clamp(result, 0.0, 1.0);
}

double bayesian_update_down(double conf, double strength) {
    const double result = conf * (1.0 - strength);
    return std::clamp(result, 0.0, 1.0);
}

// ── aggregate_evidence ───────────────────────────────────────────────────────

Aggregated aggregate_evidence(persistence::Connection& conn, std::string_view stmt_id) {
    sqlite3* db = conn.raw();

    const char* sql =
        "SELECT weight FROM reconsolidation_pending_evidence "
        "WHERE window_stmt_id=? ORDER BY weight DESC LIMIT 50";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "aggregate_evidence: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, stmt_id);

    double sum = 0.0;
    int count = 0;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        sum += sqlite3_column_double(h.get(), 0);
        ++count;
    }

    const double strength = (count == 0) ? 0.0 : std::clamp(sum / count, 0.0, 1.0);

    // Deterministic summary hash: "agg-<count>"
    const std::string summary_hash = "agg-" + std::to_string(count);

    ArbitrationPath path;
    if (strength < 0.3) {
        path = ArbitrationPath::Supports;
    } else if (strength <= 0.7) {
        path = ArbitrationPath::MildContradict;
    } else {
        path = ArbitrationPath::SevereContradict;
    }

    return {path, strength, summary_hash};
}

// ── apply_supports ───────────────────────────────────────────────────────────

void apply_supports(persistence::Connection& conn, std::string_view stmt_id,
                    std::string_view tenant_id, const Aggregated& agg,
                    std::string_view now_iso) {
    sqlite3* db = conn.raw();

    // Read current confidence
    double old_conf = 0.0;
    {
        const char* sel_sql =
            "SELECT confidence FROM statements WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sel_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_supports: prepare SELECT confidence");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, stmt_id);
        bind_sv(h.get(), 2, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_ROW)
            throw make_sqlite_error(db, "apply_supports: statement not found");
        old_conf = sqlite3_column_double(h.get(), 0);
    }

    const double new_conf = bayesian_update_up(old_conf, agg.strength);
    (void)now_iso;  // available for future updated_at extension

    // UPDATE confidence + consolidation_state
    {
        const char* upd_sql =
            "UPDATE statements SET confidence=?, consolidation_state='consolidated' "
            "WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_supports: prepare UPDATE");
        StmtHandle h(raw);
        sqlite3_bind_double(h.get(), 1, new_conf);
        bind_sv(h.get(), 2, stmt_id);
        bind_sv(h.get(), 3, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "apply_supports: UPDATE step");
    }

    // Emit statement.consolidated
    {
        const double delta = new_conf - old_conf;
        std::ostringstream payload;
        payload << "{\"path\":\"supports\",\"confidence_delta\":" << delta << "}";
        try {
            emit_event(conn, "statement.consolidated",
                       stmt_id, stmt_id, tenant_id, payload.str());
        } catch (...) {
            // idempotency_key UNIQUE collision — skip duplicate
        }
    }
}

// ── apply_mild_contradict ────────────────────────────────────────────────────

void apply_mild_contradict(persistence::Connection& conn, std::string_view stmt_id,
                           std::string_view tenant_id, const Aggregated& agg,
                           std::string_view now_iso) {
    sqlite3* db = conn.raw();

    // Read current confidence + confidence_history_json
    double old_conf = 0.0;
    std::string history_json;
    {
        const char* sel_sql =
            "SELECT confidence, confidence_history_json FROM statements "
            "WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sel_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_mild_contradict: prepare SELECT");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, stmt_id);
        bind_sv(h.get(), 2, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_ROW)
            throw make_sqlite_error(db, "apply_mild_contradict: statement not found");
        old_conf = sqlite3_column_double(h.get(), 0);
        const auto* txt = sqlite3_column_text(h.get(), 1);
        history_json = txt ? reinterpret_cast<const char*>(txt) : "[]";
    }

    const double new_conf = bayesian_update_down(old_conf, agg.strength);

    // Build the ConfidenceEvent JSON object
    std::ostringstream obj_ss;
    obj_ss << "{"
           << "\"old_value\":" << old_conf
           << ",\"new_value\":" << new_conf
           << ",\"ts\":" << json_str(now_iso)
           << ",\"evidence_summary_hash\":" << json_str(agg.summary_hash)
           << ",\"path\":\"mild_contradict\""
           << "}";
    const std::string obj = obj_ss.str();

    // Append to JSON array: "[]" → "[<obj>]"; "[...]" → "[...,<obj>]"
    std::string new_history;
    if (history_json == "[]") {
        new_history = "[" + obj + "]";
    } else {
        // strip trailing ']' and append
        new_history = history_json.substr(0, history_json.size() - 1) + "," + obj + "]";
    }

    // UPDATE confidence + confidence_history_json + consolidation_state.
    // IMPORTANT: do NOT write provenance.
    {
        const char* upd_sql =
            "UPDATE statements SET confidence=?, confidence_history_json=?, "
            "consolidation_state='consolidated' "
            "WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_mild_contradict: prepare UPDATE");
        StmtHandle h(raw);
        sqlite3_bind_double(h.get(), 1, new_conf);
        bind_sv(h.get(), 2, new_history);
        bind_sv(h.get(), 3, stmt_id);
        bind_sv(h.get(), 4, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "apply_mild_contradict: UPDATE step");
    }

    // Emit statement.consolidated (NOT statement.corrected)
    {
        const double delta = new_conf - old_conf;
        std::ostringstream payload;
        payload << "{\"path\":\"mild_contradict\",\"confidence_delta\":" << delta << "}";
        try {
            emit_event(conn, "statement.consolidated",
                       stmt_id, stmt_id, tenant_id, payload.str());
        } catch (...) {
            // idempotency_key UNIQUE collision — skip duplicate
        }
    }
}

// ── apply_severe_contradict ──────────────────────────────────────────────────
// §7.3: 4-item atomic commit. No saga (P3). Returns new stmt_id.
// The new version does NOT emit statement.written (防重入 Replay).

std::string apply_severe_contradict(persistence::Connection& conn,
                                    std::string_view old_stmt_id,
                                    std::string_view tenant_id,
                                    const Aggregated& agg,
                                    std::string_view now_iso) {
    sqlite3* db = conn.raw();

    // Step 1: Read old row — all NOT NULL columns needed for the fork.
    struct OldRow {
        std::string holder_id, holder_perspective, subject_kind, subject_id;
        std::string predicate, object_kind, object_value;
        std::string canonical_object_hash, canonical_object_hash_version;
        std::string modality, polarity, observed_at, salience_str, affect_json;
        std::string activation_str, last_accessed, review_status;
        double confidence = 0.0;
    } old;

    {
        const char* sel_sql =
            "SELECT holder_id, holder_perspective, subject_kind, subject_id, predicate, "
            "object_kind, object_value, canonical_object_hash, canonical_object_hash_version, "
            "modality, polarity, confidence, observed_at, salience, affect_json, activation, "
            "last_accessed, review_status "
            "FROM statements WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sel_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_severe_contradict: prepare SELECT old row");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, old_stmt_id);
        bind_sv(h.get(), 2, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_ROW)
            throw make_sqlite_error(db, "apply_severe_contradict: old statement not found");

        auto col_str = [&](int idx) -> std::string {
            const auto* txt = sqlite3_column_text(h.get(), idx);
            return txt ? reinterpret_cast<const char*>(txt) : "";
        };
        old.holder_id                   = col_str(0);
        old.holder_perspective          = col_str(1);
        old.subject_kind                = col_str(2);
        old.subject_id                  = col_str(3);
        old.predicate                   = col_str(4);
        old.object_kind                 = col_str(5);
        old.object_value                = col_str(6);
        old.canonical_object_hash       = col_str(7);
        old.canonical_object_hash_version = col_str(8);
        old.modality                    = col_str(9);
        old.polarity                    = col_str(10);
        old.confidence                  = sqlite3_column_double(h.get(), 11);
        old.observed_at                 = col_str(12);
        old.salience_str                = col_str(13);
        old.affect_json                 = col_str(14);
        old.activation_str              = col_str(15);
        old.last_accessed               = col_str(16);
        old.review_status               = col_str(17);
    }

    const std::string new_id = random_hex_32();
    const std::string now_s(now_iso);

    // Wrap steps 2-5 atomically. Use a SAVEPOINT (not BEGIN IMMEDIATE) so this
    // nests correctly when close_due_windows runs inside the SubscriberPump's
    // `SAVEPOINT sub_reconsolidation` — otherwise BEGIN IMMEDIATE throws
    // "cannot start a transaction within a transaction" and the async severe
    // commit is silently rolled back by run_isolated.
    SavepointGuard tx(db, "severe_contradict");

    // Step 2: INSERT new forked statement (provenance=reconsolidation_derived,
    //         consolidation_state=consolidated, supersedes_id=old_stmt_id).
    //         Do NOT emit statement.written (防重入).
    {
        const char* ins_sql =
            "INSERT INTO statements("
            "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
            "predicate, object_kind, object_value, canonical_object_hash, "
            "canonical_object_hash_version, modality, polarity, confidence, observed_at, "
            "salience, affect_json, activation, last_accessed, provenance, "
            "consolidation_state, review_status, supersedes_id, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
            "'reconsolidation_derived','consolidated',?,?,?,?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, ins_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_severe_contradict: prepare INSERT new row");
        StmtHandle h(raw);
        bind_sv(h.get(),  1, new_id);
        bind_sv(h.get(),  2, tenant_id);
        bind_sv(h.get(),  3, old.holder_id);
        bind_sv(h.get(),  4, old.holder_perspective);
        bind_sv(h.get(),  5, old.subject_kind);
        bind_sv(h.get(),  6, old.subject_id);
        bind_sv(h.get(),  7, old.predicate);
        bind_sv(h.get(),  8, old.object_kind);
        bind_sv(h.get(),  9, old.object_value);
        bind_sv(h.get(), 10, old.canonical_object_hash);
        bind_sv(h.get(), 11, old.canonical_object_hash_version);
        bind_sv(h.get(), 12, old.modality);
        bind_sv(h.get(), 13, old.polarity);
        sqlite3_bind_double(h.get(), 14, old.confidence);
        bind_sv(h.get(), 15, old.observed_at);
        bind_sv(h.get(), 16, old.salience_str);
        bind_sv(h.get(), 17, old.affect_json);
        bind_sv(h.get(), 18, old.activation_str);
        bind_sv(h.get(), 19, old.last_accessed);
        bind_sv(h.get(), 20, old.review_status);
        bind_sv(h.get(), 21, old_stmt_id);  // supersedes_id
        bind_sv(h.get(), 22, now_s);         // created_at
        bind_sv(h.get(), 23, now_s);         // updated_at
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "apply_severe_contradict: INSERT new row step");
    }

    // Step 3: INSERT SUPERSEDES edge: new_id -> old_stmt_id.
    {
        const std::string edge_id = random_hex_32();
        const char* edge_sql =
            "INSERT INTO statement_edges(id, tenant_id, src_id, dst_id, edge_kind, created_at) "
            "VALUES(?,?,?,?,'supersedes',?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, edge_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_severe_contradict: prepare INSERT edge");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, edge_id);
        bind_sv(h.get(), 2, tenant_id);
        bind_sv(h.get(), 3, new_id);
        bind_sv(h.get(), 4, old_stmt_id);
        bind_sv(h.get(), 5, now_s);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "apply_severe_contradict: INSERT edge step");
    }

    // Step 4: UPDATE old statement → archived.
    {
        // State guard: only archive a still-live row. Mirrors the P1 sync path's
        // defensive guard against archiving an already-terminal statement.
        const char* upd_sql =
            "UPDATE statements SET consolidation_state='archived', updated_at=? "
            "WHERE id=? AND tenant_id=? "
            "  AND consolidation_state NOT IN ('archived','forgotten')";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "apply_severe_contradict: prepare UPDATE archive");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, now_s);
        bind_sv(h.get(), 2, old_stmt_id);
        bind_sv(h.get(), 3, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "apply_severe_contradict: UPDATE archive step");
        if (sqlite3_changes(db) != 1)
            throw std::runtime_error("apply_severe_contradict: old statement row not found or already terminal");
    }

    // Step 5: Emit 3 outbox events (statement.corrected, statement.archived, statement.superseded).
    // Do NOT emit statement.written for new_id (防重入 Replay).
    {
        std::ostringstream corrected_payload;
        corrected_payload << "{\"old_stmt_id\":" << json_str(old_stmt_id)
                          << ",\"new_stmt_id\":" << json_str(new_id) << "}";
        emit_event(conn, "statement.corrected",
                   new_id, new_id, tenant_id, corrected_payload.str());
    }
    {
        std::ostringstream archived_payload;
        archived_payload << "{\"reason\":\"severe_contradict\""
                         << ",\"superseded_by\":" << json_str(new_id) << "}";
        emit_event(conn, "statement.archived",
                   old_stmt_id, old_stmt_id, tenant_id, archived_payload.str());
    }
    {
        std::ostringstream superseded_payload;
        superseded_payload << "{\"old_stmt_id\":" << json_str(old_stmt_id)
                           << ",\"new_stmt_id\":" << json_str(new_id) << "}";
        emit_event(conn, "statement.superseded",
                   new_id, new_id, tenant_id, superseded_payload.str());
    }

    tx.release();
    (void)agg;  // agg.strength available for future confidence fork; kept as-is per spec
    return new_id;
}

}  // namespace starling::reconsolidation
