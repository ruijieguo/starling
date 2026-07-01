#pragma once
#include "starling/governance/runtime_health_event.hpp"
#include <string>
#include <utility>

namespace starling::governance {

// Pure builder — constructs a HealthDecision targeting DEGRADED.
//
// Usage pattern (caller drives; no live observation in c1 — L1):
//   if (!gate.sweep_leaked(now).empty())
//       supervisor.note_health(degraded_decision("leaked_lease_sweep"));
//   if (guard.should_pause_lane(cutoff))
//       supervisor.note_health(degraded_decision("restart_guard_pause"));
//
// The gate and guard hold NO supervisor reference (OQ-4.6). Live routing and
// real health-observation land at M0.9+.
[[nodiscard]] inline HealthDecision degraded_decision(std::string trigger) {
    return HealthDecision{
        .target_status    = RuntimeHealth::DEGRADED,
        .trigger          = std::move(trigger),
        .metrics_snapshot = {},
    };
}

}  // namespace starling::governance
