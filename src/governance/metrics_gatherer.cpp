#include "starling/governance/metrics_gatherer.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

#include <sqlite3.h>

namespace starling::governance {

using persistence::StmtHandle;
using persistence::detail::make_sqlite_error;

// ── MetricsGatherer::gather ───────────────────────────────────────────────────
//
// Outbox-lag query (c1 only; other 6 metrics stay at default 0):
//
//   SELECT
//     COALESCE(MAX(b.outbox_sequence), 0)
//       - COALESCE(
//           (SELECT last_delivered_sequence
//              FROM consumer_checkpoint
//             WHERE consumer_id = 'in_process'),
//           0)
//   FROM bus_events AS b
//
// Semantics:
//   - MAX(outbox_sequence)          → head of the outbox (0 if no events).
//   - last_delivered_sequence       → cursor of the 'in_process' consumer.
//   - COALESCE(subquery, 0)         → treat absent checkpoint as delivered=0
//                                     (all events are undelivered — full lag).
//   - Result is always >= 0 because:
//       * If no events exist, MAX → NULL → COALESCE(NULL,0) = 0; lag = 0 - 0 = 0.
//       * If the checkpoint is ahead (impossible in practice but schema-legal),
//         the result could be negative; we clamp to 0 via MAX(..., 0) below.
//
// Error handling: prepare or step failures throw SqliteError (mirrors store
// idiom).  The host tick's try/except catches them — no spurious transitions.

[[nodiscard]] MetricsSnapshot
MetricsGatherer::gather(persistence::Connection& conn) const {
    sqlite3* const dbh = conn.raw();

    // Single query: COALESCE clamps missing events or missing checkpoint to 0.
    // The outer MAX(..., 0) guards against a theoretically-negative result if
    // the checkpoint somehow exceeds the current head.
    constexpr const char* kSql =
        "SELECT MAX("
        "  COALESCE(MAX(b.outbox_sequence), 0)"
        "  - COALESCE("
        "      (SELECT last_delivered_sequence"
        "         FROM consumer_checkpoint"
        "        WHERE consumer_id = 'in_process'),"
        "      0),"
        "  0)"
        " FROM bus_events AS b";

    sqlite3_stmt* raw_stmt = nullptr;
    if (sqlite3_prepare_v2(dbh, kSql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "MetricsGatherer::gather: prepare failed");
    }
    StmtHandle hnd(raw_stmt);

    const int rcode = sqlite3_step(hnd.get());
    if (rcode != SQLITE_ROW) {
        throw make_sqlite_error(dbh, "MetricsGatherer::gather: step failed");
    }

    MetricsSnapshot snap;
    snap.outbox_lag_sequence = sqlite3_column_int64(hnd.get(), 0);
    // All other fields remain at MetricsSnapshot defaults (0 / 0.0).
    // runtime_event_loop_lag_ms is set by the host (engine.py tick-delay path).
    // projection_lag_seconds, erased_evidence_visible_count, and the 3
    // instrumentation metrics are deferred to M0.9+ (OQ-5.1=A, L1).
    return snap;
}

}  // namespace starling::governance
