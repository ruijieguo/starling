#ifndef STARLING_GOVERNANCE_RUNTIME_HEALTH_EVENT_HPP
#define STARLING_GOVERNANCE_RUNTIME_HEALTH_EVENT_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "starling/runtime_health.hpp"

namespace starling::governance {

// Backpressure metric sample (05_governance.md:33). Phase 2 carries it on events
// with 0/sentinel defaults; Phase 5's sampler populates real values.
struct MetricsSnapshot {
  std::int64_t outbox_lag_sequence = 0;
  double subscriber_failure_rate = 0.0;
  std::int64_t extraction_queue_depth = 0;
  double projection_lag_seconds = 0.0;
  double runtime_event_loop_lag_ms = 0.0;
  std::int64_t vector_delete_lag = 0;
  std::int64_t erased_evidence_visible_count = 0;
};

// One health-state transition (05_governance.md:126-131). missing_capabilities
// is populated only for transitions into UNREADY (capability/index preflight).
struct RuntimeHealthEvent {
  RuntimeHealth previous_status = RuntimeHealth::UNREADY;
  RuntimeHealth current_status = RuntimeHealth::UNREADY;
  std::string trigger;
  MetricsSnapshot metrics_snapshot;
  std::vector<std::string> missing_capabilities;
};

// A health decision produced by Phase 5's sampler and applied via
// RuntimeSupervisor::note_health(); Phase 2 only consumes it (test-driven).
struct HealthDecision {
  RuntimeHealth target_status = RuntimeHealth::READY;
  std::string trigger;
  MetricsSnapshot metrics_snapshot;
};

// Pure reachability of the RuntimeHealth state machine (D-P2-7):
//   UNREADY->READY; READY<->DEGRADED; READY->DRAINING; DEGRADED->DRAINING;
//   any->UNREADY (fail-closed always reachable); DRAINING is terminal except
//   ->UNREADY; same-state self-loops are legal. Whether a (legal) transition
//   EMITS an event is decided by RuntimeSupervisor::transition_to (OV-3:
//   emit iff from != target OR target == UNREADY), NOT here.
[[nodiscard]] constexpr bool is_legal_transition(RuntimeHealth from,
                                                 RuntimeHealth target) {
  using Health = RuntimeHealth;
  if (target == Health::UNREADY) {
    return true;
  }
  switch (from) {
    case Health::UNREADY:
      return target == Health::READY;
    case Health::READY:
      return target == Health::READY || target == Health::DEGRADED ||
             target == Health::DRAINING;
    case Health::DEGRADED:
      return target == Health::READY || target == Health::DEGRADED ||
             target == Health::DRAINING;
    case Health::DRAINING:
      return target == Health::DRAINING;
  }
  return false;
}

}  // namespace starling::governance

#endif
