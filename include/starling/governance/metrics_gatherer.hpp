#pragma once
#include "starling/governance/runtime_health_event.hpp"
#include "starling/persistence/connection.hpp"

namespace starling::governance {

// Reads cleanly-queryable backpressure metrics from the live DB and returns a
// MetricsSnapshot.  c1 gathers only outbox_lag_sequence (OQ-5.1=A); all other
// fields remain at their MetricsSnapshot defaults (0 / 0.0).
//
// outbox_lag_sequence = MAX(bus_events.outbox_sequence)
//                     - consumer_checkpoint.last_delivered_sequence
//                       WHERE consumer_id = 'in_process'
//
// Edge cases (all documented here and tested in test_metrics_gatherer.cpp):
//   - Empty bus_events (no rows)  → lag = 0.
//   - No consumer_checkpoint row for 'in_process' but events exist
//     → delivered treated as 0, lag = MAX(outbox_sequence).
//     Rationale: every pending event is undelivered — this is the true lag.
//   - DB error (prepare or step failure) → SqliteError thrown.
//     The host's tick try/except catches it (L7); no spurious health transition.
//
// No mutex; no mutable state.  Thread safety: the caller must ensure the DB
// connection is not concurrently written while gather() is executing.
class MetricsGatherer {
public:
    MetricsGatherer() = default;

    [[nodiscard]] MetricsSnapshot gather(persistence::Connection& conn) const;
};

}  // namespace starling::governance
