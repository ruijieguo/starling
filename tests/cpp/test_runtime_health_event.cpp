#include "starling/governance/runtime_health_event.hpp"

#include <gtest/gtest.h>

namespace {
using starling::RuntimeHealth;
using starling::governance::HealthDecision;
using starling::governance::MetricsSnapshot;
using starling::governance::RuntimeHealthEvent;
using starling::governance::is_legal_transition;

TEST(RuntimeHealthEvent, StructDefaultsAreFailClosedAndZeroed) {
  const MetricsSnapshot snap;
  EXPECT_EQ(snap.outbox_lag_sequence, 0);
  EXPECT_DOUBLE_EQ(snap.subscriber_failure_rate, 0.0);
  EXPECT_EQ(snap.extraction_queue_depth, 0);
  EXPECT_DOUBLE_EQ(snap.projection_lag_seconds, 0.0);
  EXPECT_DOUBLE_EQ(snap.runtime_event_loop_lag_ms, 0.0);
  EXPECT_EQ(snap.vector_delete_lag, 0);
  EXPECT_EQ(snap.erased_evidence_visible_count, 0);

  const RuntimeHealthEvent evt;
  EXPECT_EQ(evt.previous_status, RuntimeHealth::UNREADY);
  EXPECT_EQ(evt.current_status, RuntimeHealth::UNREADY);
  EXPECT_TRUE(evt.trigger.empty());
  EXPECT_TRUE(evt.missing_capabilities.empty());

  const HealthDecision dec;
  EXPECT_EQ(dec.target_status, RuntimeHealth::READY);
  EXPECT_TRUE(dec.trigger.empty());
}

TEST(RuntimeHealthEvent, LegalTransitionsAccepted) {
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::UNREADY, RuntimeHealth::READY));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::READY, RuntimeHealth::DEGRADED));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::DEGRADED, RuntimeHealth::READY));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::READY, RuntimeHealth::DRAINING));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::DEGRADED, RuntimeHealth::DRAINING));
  // any -> UNREADY is always reachable (fail-closed)
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::READY, RuntimeHealth::UNREADY));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::DEGRADED, RuntimeHealth::UNREADY));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::DRAINING, RuntimeHealth::UNREADY));
  // self-loops are legal (transition_to suppresses the event per OV-3; legality != emission)
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::UNREADY, RuntimeHealth::UNREADY));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::READY, RuntimeHealth::READY));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::DEGRADED, RuntimeHealth::DEGRADED));
  EXPECT_TRUE(is_legal_transition(RuntimeHealth::DRAINING, RuntimeHealth::DRAINING));
}

TEST(RuntimeHealthEvent, IllegalTransitionsRejected) {
  EXPECT_FALSE(is_legal_transition(RuntimeHealth::DRAINING, RuntimeHealth::READY));
  EXPECT_FALSE(is_legal_transition(RuntimeHealth::DRAINING, RuntimeHealth::DEGRADED));
  EXPECT_FALSE(is_legal_transition(RuntimeHealth::UNREADY, RuntimeHealth::DEGRADED));
  EXPECT_FALSE(is_legal_transition(RuntimeHealth::UNREADY, RuntimeHealth::DRAINING));
}
}  // namespace
