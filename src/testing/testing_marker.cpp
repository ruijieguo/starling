#include "starling/testing_marker.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <sqlite3.h>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::testing {

bool testing_marker_loaded() noexcept { return true; }

namespace {

// Local JSON string escaper. Tenant/stmt ids are usually opaque ASCII tokens
// in tests, but a real test could pass arbitrary input — escape defensively.
// Mirrors the encoder in src/bus/bus.cpp; duplicated here so the testing-only
// translation unit doesn't pull bus.cpp internals.
std::string json_string(std::string_view sv) {
    std::ostringstream os;
    os << '"';
    for (char ch : sv) {
        const auto u = static_cast<unsigned char>(ch);
        switch (ch) {
            case '"':  os << "\\\""; break;
            case '\\': os << "\\\\"; break;
            case '\n': os << "\\n";  break;
            case '\r': os << "\\r";  break;
            case '\t': os << "\\t";  break;
            default:
                if (u < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", u);
                    os << buf;
                } else {
                    os << ch;
                }
        }
    }
    os << '"';
    return os.str();
}

}  // namespace

bool mark_consolidated(
    starling::persistence::SqliteAdapter& adapter,
    std::string_view stmt_id,
    std::string_view tenant_id) {

    auto& conn = adapter.connection();

    // Single transaction wraps the UPDATE + audit append: both land or neither
    // does. The TransactionGuard rolls back on throw via its destructor.
    starling::persistence::TransactionGuard tx(conn);

    // Atomic VOLATILE -> CONSOLIDATED gate. The WHERE includes
    // consolidation_state='volatile' so a re-call after the row has already
    // been promoted (or any other state — archived, replaying_*) updates 0
    // rows and we return false. A missing row also yields 0 changes.
    bool changed = false;
    {
        const char* sql =
            "UPDATE statements SET "
            "  consolidation_state='consolidated', "
            "  updated_at=? "
            "WHERE id=? AND tenant_id=? AND consolidation_state='volatile'";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw starling::bus::detail::make_sqlite_error(
                conn.raw(), "mark_consolidated: update prepare");
        }
        starling::persistence::StmtHandle h(raw);
        const std::string now_iso = starling::bus::detail::iso8601_utc(
            std::chrono::system_clock::now());
        starling::bus::detail::bind_sv(h.get(), 1, now_iso);
        starling::bus::detail::bind_sv(h.get(), 2, stmt_id);
        starling::bus::detail::bind_sv(h.get(), 3, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw starling::bus::detail::make_sqlite_error(
                conn.raw(), "mark_consolidated: update step");
        }
        changed = (sqlite3_changes(conn.raw()) == 1);
    }

    if (!changed) {
        // Idempotent re-call OR row missing OR row in a non-volatile state:
        // commit the (empty) transaction and report no transition. We don't
        // emit an audit event in this branch — replaying tests only see audit
        // rows for actual transitions. The UNIQUE(idempotency_key) constraint
        // on bus_events therefore never trips for this helper.
        tx.commit();
        return false;
    }

    // Audit event. aggregate_id == primary_id == stmt_id makes the
    // idempotency-key (formula §3.10) a pure function of stmt_id, so a
    // hypothetical replay against the same row would collide on UNIQUE if it
    // ever got past the WHERE-state guard above (which it can't). Empty
    // causation_root + empty window_bucket per the §3.10 rules for
    // setup-only audit events.
    {
        starling::bus::BusEvent ev;
        ev.tenant_id    = std::string(tenant_id);
        ev.event_type   = "testing.mark_consolidated";
        ev.primary_id   = std::string(stmt_id);
        ev.aggregate_id = std::string(stmt_id);
        ev.idempotency_key = starling::bus::compute_idempotency_key(
            ev.event_type, ev.aggregate_id, ev.primary_id,
            /*causation_root=*/std::string_view{},
            /*window_bucket=*/std::string_view{});

        std::ostringstream payload;
        payload << "{"
                << "\"stmt_id\":"   << json_string(stmt_id)  << ","
                << "\"tenant_id\":" << json_string(tenant_id) << ","
                << "\"helper\":\"starling.testing.mark_consolidated\""
                << "}";
        ev.payload_json = payload.str();

        starling::bus::OutboxWriter writer(conn);
        writer.append(ev);
    }

    tx.commit();
    return true;
}

bool mark_evidence_erased(
    starling::persistence::SqliteAdapter& adapter,
    std::string_view engram_id,
    std::string_view tenant_id,
    std::string_view erased_at_iso8601) {

    auto& conn = adapter.connection();

    // Single transaction wraps the UPDATE + audit append: both land or neither
    // does. The TransactionGuard rolls back on throw via its destructor.
    starling::persistence::TransactionGuard tx(conn);

    // Atomic NULL -> ISO8601 gate. The WHERE includes erased_at IS NULL so a
    // re-call after the row has already been erased updates 0 rows and we
    // return false. A missing row also yields 0 changes.
    bool changed = false;
    {
        const char* sql =
            "UPDATE engrams SET erased_at=?1 "
            "WHERE id=?2 AND tenant_id=?3 AND erased_at IS NULL";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw starling::bus::detail::make_sqlite_error(
                conn.raw(), "mark_evidence_erased: update prepare");
        }
        starling::persistence::StmtHandle h(raw);
        starling::bus::detail::bind_sv(h.get(), 1, erased_at_iso8601);
        starling::bus::detail::bind_sv(h.get(), 2, engram_id);
        starling::bus::detail::bind_sv(h.get(), 3, tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw starling::bus::detail::make_sqlite_error(
                conn.raw(), "mark_evidence_erased: update step");
        }
        changed = (sqlite3_changes(conn.raw()) == 1);
    }

    if (!changed) {
        // Idempotent re-call OR row missing OR row already erased: commit the
        // (empty) transaction and report no transition. We don't emit an audit
        // event in this branch — replaying tests only see audit rows for
        // actual transitions. The UNIQUE(idempotency_key) constraint on
        // bus_events therefore never trips for this helper.
        tx.commit();
        return false;
    }

    // Audit event. aggregate_id == primary_id == engram_id makes the
    // idempotency-key (formula §3.10) a pure function of engram_id, so a
    // hypothetical replay against the same row would collide on UNIQUE if it
    // ever got past the WHERE-state guard above (which it can't). Empty
    // causation_root + empty window_bucket per the §3.10 rules for
    // setup-only audit events.
    {
        starling::bus::BusEvent ev;
        ev.tenant_id    = std::string(tenant_id);
        ev.event_type   = "testing.mark_evidence_erased";
        ev.primary_id   = std::string(engram_id);
        ev.aggregate_id = std::string(engram_id);
        // Propagate the caller-supplied erased_at into the audit envelope's
        // created_at so consumers can correlate the event with the row's
        // erased_at without parsing payload_json. Without this, OutboxWriter::
        // append fills created_at with the wall-clock time at write — losing
        // the correlation with the semantically meaningful erasure timestamp.
        ev.created_at   = std::string(erased_at_iso8601);
        ev.idempotency_key = starling::bus::compute_idempotency_key(
            ev.event_type, ev.aggregate_id, ev.primary_id,
            /*causation_root=*/std::string_view{},
            /*window_bucket=*/std::string_view{});

        std::ostringstream payload;
        payload << "{"
                << "\"engram_id\":"  << json_string(engram_id)         << ","
                << "\"tenant_id\":"  << json_string(tenant_id)         << ","
                << "\"erased_at\":"  << json_string(erased_at_iso8601) << ","
                << "\"helper\":\"starling.testing.mark_evidence_erased\""
                << "}";
        ev.payload_json = payload.str();

        starling::bus::OutboxWriter writer(conn);
        writer.append(ev);
    }

    tx.commit();
    return true;
}

}  // namespace starling::testing
