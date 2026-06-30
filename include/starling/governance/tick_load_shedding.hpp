#pragma once
#include <cstdint>
#include "starling/runtime_health.hpp"   // starling::RuntimeHealth

namespace starling::governance {

// The 8 maintenance-tick stages, in tick execution order. Mirrors the
// StageTimer labels in src/memory/memory_ops.cpp tick_all. Replay is SPLIT
// into its 3 substages (LOCKED L4): the two safety/retention substages are
// CRITICAL, only ReplayIdle is droppable.
enum class TickStage : std::uint8_t {
    Embed,                    // soft   — high-cost embedding side-effect
    Policy,                   // critical — commitment fire
    CommonGround,             // soft   — non-critical grounding batch
    ReplayOscillationGuard,   // critical — safety (replay.enforce_oscillation_guard)
    ReplayTtlSweep,           // critical — retention (replay.sweep_volatile_ttl)
    ReplayIdle,               // soft   — non-critical consolidation (replay.run_idle)
    Projection,               // soft   — non-critical projection batch
    Outbox,                   // critical — delivery convergence / the lag drainer
};

enum class TickLane : std::uint8_t { Soft, Critical };

// Classify a stage as Soft or Critical (LOCKED L4).
//
// Soft  (skip under DEGRADED): Embed, CommonGround, ReplayIdle, Projection.
// Critical (always-run lane): Policy, ReplayOscillationGuard, ReplayTtlSweep, Outbox.
//
// LOCKED L5 — trigger-awareness invariant:
//   This static lane map is valid ONLY while the enabled sampler triggers are
//   outbox_lag + runtime_event_loop_lag_ms, whose drainer (Outbox) is Critical.
//   Enabling a new trigger whose drainer is a Soft stage (e.g. projection_lag →
//   Projection) requires making the shedding trigger-aware FIRST — otherwise
//   DEGRADED would skip the very stage that drains the trigger (self-deadlock).
//   Not built now.
[[nodiscard]] inline TickLane lane_of(TickStage stage) noexcept {
    switch (stage) {
        case TickStage::Embed:                  return TickLane::Soft;
        case TickStage::Policy:                 return TickLane::Critical;
        case TickStage::CommonGround:           return TickLane::Soft;
        case TickStage::ReplayOscillationGuard: return TickLane::Critical;
        case TickStage::ReplayTtlSweep:         return TickLane::Critical;
        case TickStage::ReplayIdle:             return TickLane::Soft;
        case TickStage::Projection:             return TickLane::Soft;
        case TickStage::Outbox:                 return TickLane::Critical;
    }
    // Unreachable; all enumerators covered above.
    return TickLane::Soft;
}

// Gate decision for a single tick stage given the current RuntimeHealth.
//
// Truth table (LOCKED L4):
//   READY    → every stage runs (true for all).
//   DEGRADED → Critical lane only (Soft stages skipped).
//   DRAINING → shed all background EXCEPT Outbox (keep Outbox to drain
//              in-flight delivery, LOCKED L7); everything else false.
//   UNREADY  → all false (fail-closed; the tick never runs in UNREADY anyway).
[[nodiscard]] inline bool should_run_stage(TickStage stage, RuntimeHealth health) noexcept {
    switch (health) {
        case RuntimeHealth::READY:
            return true;
        case RuntimeHealth::DEGRADED:
            return lane_of(stage) == TickLane::Critical;
        case RuntimeHealth::DRAINING:
            return stage == TickStage::Outbox;
        case RuntimeHealth::UNREADY:
            return false;
    }
    // Unreachable; all enumerators covered above.
    return false;
}

}  // namespace starling::governance
