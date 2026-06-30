#include "starling/governance/health_sampler.hpp"
#include "starling/governance/runtime_health_event.hpp"
#include "starling/runtime_health.hpp"

#include <gtest/gtest.h>

using starling::RuntimeHealth;
using starling::governance::HealthDecision;
using starling::governance::HealthSampler;
using starling::governance::HealthSamplerConfig;
using starling::governance::MetricsSnapshot;

namespace {

// Helper: build a HealthSamplerConfig with only outbox_lag + runtime_event_loop_lag_ms
// enabled (c1 profile), thresholds set to representative values.
HealthSamplerConfig c1_config() {
    return HealthSamplerConfig{
        .outbox_lag = {.enabled = true, .threshold = 100},
        .subscriber_failure_rate = {.enabled = false, .threshold = 0.5},
        .extraction_queue_depth = {.enabled = false, .threshold = 50},
        .projection_lag_seconds = {.enabled = false, .threshold = 30.0},
        .runtime_event_loop_lag_ms = {.enabled = true, .threshold = 200.0},
        .vector_delete_lag = {.enabled = false, .threshold = 200},
        .erased_evidence = {.enabled = false},
    };
}

// ── all-enabled-within-SLA → READY + trigger "backpressure_recovered" ────────

TEST(HealthSampler, AllEnabledWithinSlaReturnsReady) {
    HealthSampler sampler{c1_config()};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 50;             // under threshold 100
    snap.runtime_event_loop_lag_ms = 100.0;    // under threshold 200

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::READY);
    EXPECT_EQ(dec.trigger, "backpressure_recovered");
}

// ── returned metrics_snapshot equals the input snapshot ──────────────────────

TEST(HealthSampler, MetricsSnapshotCarriedIntoDecision) {
    HealthSampler sampler{c1_config()};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 5;
    snap.runtime_event_loop_lag_ms = 10.0;
    snap.subscriber_failure_rate = 0.99;   // disabled — doesn't matter
    snap.extraction_queue_depth = 999;     // disabled — doesn't matter

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.metrics_snapshot.outbox_lag_sequence, snap.outbox_lag_sequence);
    EXPECT_DOUBLE_EQ(dec.metrics_snapshot.runtime_event_loop_lag_ms,
                     snap.runtime_event_loop_lag_ms);
    EXPECT_DOUBLE_EQ(dec.metrics_snapshot.subscriber_failure_rate,
                     snap.subscriber_failure_rate);
    EXPECT_EQ(dec.metrics_snapshot.extraction_queue_depth, snap.extraction_queue_depth);
}

// ── each enabled metric alone over its threshold → DEGRADED + correct trigger ─

TEST(HealthSampler, OutboxLagAloneOverThresholdDegrades) {
    HealthSampler sampler{c1_config()};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 101;        // over threshold 100
    snap.runtime_event_loop_lag_ms = 10.0; // within threshold

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::DEGRADED);
    EXPECT_EQ(dec.trigger, "outbox_lag");
}

TEST(HealthSampler, RuntimeEventLoopLagAloneOverThresholdDegrades) {
    HealthSampler sampler{c1_config()};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 50;              // within threshold
    snap.runtime_event_loop_lag_ms = 201.0;    // over threshold 200

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::DEGRADED);
    EXPECT_EQ(dec.trigger, "runtime_event_loop_lag_ms");
}

// ── multiple enabled over → DEGRADED + trigger lists ALL in stable order ──────

TEST(HealthSampler, MultipleEnabledOverTriggerListsAll) {
    HealthSampler sampler{c1_config()};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 200;             // over threshold 100
    snap.runtime_event_loop_lag_ms = 500.0;    // over threshold 200

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::DEGRADED);
    // Stable order = config-field order: outbox_lag before runtime_event_loop_lag_ms
    EXPECT_EQ(dec.trigger, "outbox_lag,runtime_event_loop_lag_ms");
}

// ── DISABLED metric set way over its threshold → still READY (L1 zero≠healthy) ─

TEST(HealthSampler, DisabledMetricOverThresholdStillReady) {
    // Only enable nothing (all disabled). Even with wildly-over values, result is READY.
    HealthSamplerConfig all_disabled{
        .outbox_lag = {.enabled = false, .threshold = 0},
        .subscriber_failure_rate = {.enabled = false, .threshold = 0.0},
        .extraction_queue_depth = {.enabled = false, .threshold = 0},
        .projection_lag_seconds = {.enabled = false, .threshold = 0.0},
        .runtime_event_loop_lag_ms = {.enabled = false, .threshold = 0.0},
        .vector_delete_lag = {.enabled = false, .threshold = 0},
        .erased_evidence = {.enabled = false},
    };
    HealthSampler sampler{all_disabled};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 999999;
    snap.subscriber_failure_rate = 1.0;
    snap.extraction_queue_depth = 999999;
    snap.projection_lag_seconds = 9999.0;
    snap.runtime_event_loop_lag_ms = 999999.0;
    snap.vector_delete_lag = 999999;
    snap.erased_evidence_visible_count = 999;

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::READY);
    EXPECT_EQ(dec.trigger, "backpressure_recovered");
}

TEST(HealthSampler, DisabledMetricInMixedConfigDoesNotContribute) {
    // subscriber_failure_rate is disabled (way over); only outbox_lag enabled (within).
    HealthSamplerConfig cfg{
        .outbox_lag = {.enabled = true, .threshold = 100},
        .subscriber_failure_rate = {.enabled = false, .threshold = 0.1},
        .extraction_queue_depth = {.enabled = false, .threshold = 0},
        .projection_lag_seconds = {.enabled = false, .threshold = 0.0},
        .runtime_event_loop_lag_ms = {.enabled = false, .threshold = 0.0},
        .vector_delete_lag = {.enabled = false, .threshold = 0},
        .erased_evidence = {.enabled = false},
    };
    HealthSampler sampler{cfg};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 50;           // within threshold
    snap.subscriber_failure_rate = 0.99;    // disabled, would be over threshold

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::READY);
    EXPECT_EQ(dec.trigger, "backpressure_recovered");
}

// ── erased_evidence enabled & >0 → DEGRADED ──────────────────────────────────

TEST(HealthSampler, ErasedEvidenceEnabledAndNonZeroDegrades) {
    HealthSamplerConfig cfg{
        .outbox_lag = {.enabled = false, .threshold = 0},
        .subscriber_failure_rate = {.enabled = false, .threshold = 0.0},
        .extraction_queue_depth = {.enabled = false, .threshold = 0},
        .projection_lag_seconds = {.enabled = false, .threshold = 0.0},
        .runtime_event_loop_lag_ms = {.enabled = false, .threshold = 0.0},
        .vector_delete_lag = {.enabled = false, .threshold = 0},
        .erased_evidence = {.enabled = true},
    };
    HealthSampler sampler{cfg};
    MetricsSnapshot snap;
    snap.erased_evidence_visible_count = 1;

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::DEGRADED);
    EXPECT_EQ(dec.trigger, "erased_evidence");
}

TEST(HealthSampler, ErasedEvidenceEnabledAndZeroDoesNotDegrade) {
    HealthSamplerConfig cfg{
        .outbox_lag = {.enabled = false, .threshold = 0},
        .subscriber_failure_rate = {.enabled = false, .threshold = 0.0},
        .extraction_queue_depth = {.enabled = false, .threshold = 0},
        .projection_lag_seconds = {.enabled = false, .threshold = 0.0},
        .runtime_event_loop_lag_ms = {.enabled = false, .threshold = 0.0},
        .vector_delete_lag = {.enabled = false, .threshold = 0},
        .erased_evidence = {.enabled = true},
    };
    HealthSampler sampler{cfg};
    MetricsSnapshot snap;
    snap.erased_evidence_visible_count = 0;

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::READY);
    EXPECT_EQ(dec.trigger, "backpressure_recovered");
}

// ── NEVER returns UNREADY ─────────────────────────────────────────────────────

TEST(HealthSampler, NeverReturnsUnready) {
    HealthSampler sampler{c1_config()};
    MetricsSnapshot snap;
    // Both enabled metrics way over threshold.
    snap.outbox_lag_sequence = 9999;
    snap.runtime_event_loop_lag_ms = 99999.0;

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_NE(dec.target_status, RuntimeHealth::UNREADY);
    EXPECT_EQ(dec.target_status, RuntimeHealth::DEGRADED);
}

// ── boundary: exact-threshold does NOT trip (> not >=) ───────────────────────

TEST(HealthSampler, ExactThresholdDoesNotTrip) {
    HealthSampler sampler{c1_config()};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 100;            // exactly at threshold — should NOT trip
    snap.runtime_event_loop_lag_ms = 200.0;   // exactly at threshold — should NOT trip

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::READY);
    EXPECT_EQ(dec.trigger, "backpressure_recovered");
}

// ── all 7 metrics enabled + all over → trigger lists all in stable field order ─

TEST(HealthSampler, AllSevenEnabledAndOverTriggerListsAllInOrder) {
    HealthSamplerConfig all_enabled{
        .outbox_lag = {.enabled = true, .threshold = 0},
        .subscriber_failure_rate = {.enabled = true, .threshold = 0.0},
        .extraction_queue_depth = {.enabled = true, .threshold = 0},
        .projection_lag_seconds = {.enabled = true, .threshold = 0.0},
        .runtime_event_loop_lag_ms = {.enabled = true, .threshold = 0.0},
        .vector_delete_lag = {.enabled = true, .threshold = 0},
        .erased_evidence = {.enabled = true},
    };
    HealthSampler sampler{all_enabled};
    MetricsSnapshot snap;
    snap.outbox_lag_sequence = 1;
    snap.subscriber_failure_rate = 0.1;
    snap.extraction_queue_depth = 1;
    snap.projection_lag_seconds = 0.1;
    snap.runtime_event_loop_lag_ms = 0.1;
    snap.vector_delete_lag = 1;
    snap.erased_evidence_visible_count = 1;

    HealthDecision dec = sampler.evaluate(snap);
    EXPECT_EQ(dec.target_status, RuntimeHealth::DEGRADED);
    EXPECT_EQ(dec.trigger,
              "outbox_lag,subscriber_failure_rate,extraction_queue_depth,"
              "projection_lag_seconds,runtime_event_loop_lag_ms,vector_delete_lag,"
              "erased_evidence");
}

}  // namespace
