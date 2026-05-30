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

}  // namespace starling::reconsolidation
