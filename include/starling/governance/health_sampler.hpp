#pragma once
#include <cstdint>
#include <string>

#include "starling/governance/runtime_health_event.hpp"

namespace starling::governance {

// Per-metric configuration: whether this metric participates in the sampler
// (enabled) and its over-threshold value.  DISABLED metrics are SKIPPED —
// they never contribute to a DEGRADED decision (L1: zero≠healthy; the sampler
// evaluates ONLY enabled metrics, so READY honestly means "enabled metrics
// within SLA", not "all 7 healthy").
//
// Numeric metrics: over-threshold iff value > threshold (strict greater-than).
// erased_evidence has no numeric threshold; over-threshold iff value > 0.
struct NumericMetricCfg {
    bool enabled = false;
    std::int64_t threshold = 0;
};

struct FloatMetricCfg {
    bool enabled = false;
    double threshold = 0.0;
};

struct ErasedEvidenceCfg {
    bool enabled = false;
    // No numeric threshold — any value > 0 trips (OQ-5.4).
};

// Injected thresholds for all 7 backpressure metrics.  Construct with
// designated initializers; c1 enables outbox_lag + runtime_event_loop_lag_ms
// only (the other 5 stay DISABLED until their gatherers land).
//
// Documented recommended defaults (c1 enablement):
//   outbox_lag.threshold              = 100   (sequences)
//   runtime_event_loop_lag_ms.threshold = 200 (ms)
struct HealthSamplerConfig {
    NumericMetricCfg outbox_lag;
    FloatMetricCfg   subscriber_failure_rate;
    NumericMetricCfg extraction_queue_depth;
    FloatMetricCfg   projection_lag_seconds;
    FloatMetricCfg   runtime_event_loop_lag_ms;
    NumericMetricCfg vector_delete_lag;
    ErasedEvidenceCfg erased_evidence;
};

// Pure-function threshold evaluator (L3: no I/O, no mutex, no mutable state).
//
// evaluate(snapshot) checks each ENABLED metric against its threshold and
// returns a HealthDecision carrying the input snapshot:
//
//   * No enabled metric over threshold →
//       { target_status = READY, trigger = "backpressure_recovered", … }
//
//   * ≥1 enabled metric over threshold →
//       { target_status = DEGRADED,
//         trigger = comma-joined list of ALL over-metric names in stable
//                   field order (outbox_lag, subscriber_failure_rate,
//                   extraction_queue_depth, projection_lag_seconds,
//                   runtime_event_loop_lag_ms, vector_delete_lag,
//                   erased_evidence), … }
//
// NEVER returns UNREADY (backpressure ≠ fail-closed).
//
// Flapping debounce is HOST-SIDE (engine.py tracks last-N verdicts; L3).
class HealthSampler {
public:
    explicit HealthSampler(HealthSamplerConfig config);

    [[nodiscard]] HealthDecision evaluate(const MetricsSnapshot& snapshot) const;

private:
    HealthSamplerConfig config_;
};

}  // namespace starling::governance
