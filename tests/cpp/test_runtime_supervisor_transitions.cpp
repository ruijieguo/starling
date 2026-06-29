#include "starling/governance/runtime_supervisor.hpp"

#include <algorithm>
#include <thread>

#include <gtest/gtest.h>

#include "starling/governance/runtime_health_event.hpp"
#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"

namespace {
using starling::ProfileCapability;
using starling::RuntimeHealth;
using starling::governance::HealthDecision;
using starling::governance::RuntimeSupervisor;
using starling::governance::StartOutcome;
using starling::governance::WriteGateDecision;

ProfileCapability all_present() {
  return ProfileCapability{
      .profile_name = "local-store",
      .relational_backend = "seekdb",
      .vector_backend = "seekdb",
      .graph_backend = "ladybugdb",
      .c_plus_plus_core = true,
      .cross_partition_transaction = true,
      .transactional_outbox = true,
      .consumer_checkpoint = true,
      .tenant_isolation = "storage_enforced",
      .engram_per_record_key = true,
      .engram_refcount = true,
      .projection_index_supported = false,
      .dimension_versions_supported = false,
      .testing_helper_marker = true,
  };
}

// NOTE: the supervisor is non-movable (its std::mutex deletes copy+move, which
// is the required self-synchronization design), so a `return sup;` factory is
// ill-formed. Each test constructs in place and calls start() to reach READY.

TEST(RuntimeSupervisorTransitions, StartReadyEmitsOneReadyEvent) {
  RuntimeSupervisor sup(all_present(), false, [] { return true; });
  EXPECT_EQ(sup.start(), StartOutcome::kReady);
  EXPECT_EQ(sup.health(), RuntimeHealth::READY);
  const auto last = sup.last_event();
  ASSERT_TRUE(last.has_value());
  EXPECT_EQ(last->current_status, RuntimeHealth::READY);
  EXPECT_EQ(sup.events().size(), 1U);
}

TEST(RuntimeSupervisorTransitions, StartUnreadyEmitsUnreadyEventWithMissingAndExit78) {
  ProfileCapability caps = all_present();
  caps.transactional_outbox = false;
  RuntimeSupervisor sup(caps, false, [] { return true; });
  EXPECT_EQ(sup.start(), StartOutcome::kUnready);
  EXPECT_EQ(sup.health(), RuntimeHealth::UNREADY);
  EXPECT_EQ(sup.exit_code(), starling::governance::kExConfig);
  const auto last = sup.last_event();
  ASSERT_TRUE(last.has_value());
  EXPECT_EQ(last->current_status, RuntimeHealth::UNREADY);
  EXPECT_NE(std::find(last->missing_capabilities.begin(),
                      last->missing_capabilities.end(), "transactional_outbox"),
            last->missing_capabilities.end());
}

TEST(RuntimeSupervisorTransitions, ReadyToDegradedAndBack) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  sup.note_health(HealthDecision{.target_status = RuntimeHealth::DEGRADED,
                                 .trigger = "outbox_lag", .metrics_snapshot = {}});
  EXPECT_EQ(sup.health(), RuntimeHealth::DEGRADED);
  EXPECT_EQ(sup.last_event()->current_status, RuntimeHealth::DEGRADED);
  sup.note_health(HealthDecision{.target_status = RuntimeHealth::READY,
                                 .trigger = "recovered", .metrics_snapshot = {}});
  EXPECT_EQ(sup.health(), RuntimeHealth::READY);
}

TEST(RuntimeSupervisorTransitions, DegradedAcceptsWritesDrainingAndUnreadyReject) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kAccept);  // READY
  sup.note_health(HealthDecision{.target_status = RuntimeHealth::DEGRADED,
                                 .trigger = "lag", .metrics_snapshot = {}});
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kAccept);  // DEGRADED accepts
  sup.begin_drain("shutdown");
  EXPECT_EQ(sup.health(), RuntimeHealth::DRAINING);
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kPreconditionFailed);  // DRAINING rejects
}

TEST(RuntimeSupervisorTransitions, BeginDrainFromReadyEmitsDrainingEvent) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  sup.begin_drain("sigterm");
  EXPECT_EQ(sup.health(), RuntimeHealth::DRAINING);
  EXPECT_EQ(sup.last_event()->current_status, RuntimeHealth::DRAINING);
  EXPECT_EQ(sup.last_event()->trigger, "sigterm");
}

TEST(RuntimeSupervisorTransitions, IllegalDrainingToReadyIsNoOp) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  sup.begin_drain("shutdown");
  const auto count_before = sup.events().size();
  sup.note_health(HealthDecision{.target_status = RuntimeHealth::READY,
                                 .trigger = "illegal", .metrics_snapshot = {}});
  EXPECT_EQ(sup.health(), RuntimeHealth::DRAINING);          // unchanged
  EXPECT_EQ(sup.events().size(), count_before);              // no event pushed
}

TEST(RuntimeSupervisorTransitions, AnyStateToUnreadyIsReachable) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  sup.note_health(HealthDecision{.target_status = RuntimeHealth::DEGRADED,
                                 .trigger = "lag", .metrics_snapshot = {}});
  sup.note_health(HealthDecision{.target_status = RuntimeHealth::UNREADY,
                                 .trigger = "main_table_lost", .metrics_snapshot = {}});
  EXPECT_EQ(sup.health(), RuntimeHealth::UNREADY);
  EXPECT_EQ(sup.last_event()->current_status, RuntimeHealth::UNREADY);
}

TEST(RuntimeSupervisorTransitions, ReadySelfLoopDoesNotEmit) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  const auto count_before = sup.events().size();  // 1 (the start READY event)
  sup.note_health(HealthDecision{.target_status = RuntimeHealth::READY,
                                 .trigger = "reaffirm", .metrics_snapshot = {}});
  EXPECT_EQ(sup.events().size(), count_before);   // READY→READY suppressed (OV-3)
}

TEST(RuntimeSupervisorTransitions, EventLogCapsAtMax) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  // Toggle READY<->DEGRADED many times; each toggle is a distinct-state emit.
  for (int i = 0; i < 200; ++i) {
    const RuntimeHealth target =
        (i % 2 == 0) ? RuntimeHealth::DEGRADED : RuntimeHealth::READY;
    sup.note_health(HealthDecision{.target_status = target,
                                   .trigger = "toggle", .metrics_snapshot = {}});
  }
  EXPECT_EQ(sup.events().size(), 64U);  // kMaxEvents cap
}

TEST(RuntimeSupervisorTransitions, ConcurrentReadWriteIsRaceFree) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  sup.start();  // → READY
  constexpr int kIters = 2000;
  std::thread writer([&sup] {
    for (int i = 0; i < kIters; ++i) {
      const RuntimeHealth target =
          (i % 2 == 0) ? RuntimeHealth::DEGRADED : RuntimeHealth::READY;
      sup.note_health(HealthDecision{.target_status = target,
                                     .trigger = "stress", .metrics_snapshot = {}});
    }
  });
  std::thread reader([&sup] {
    for (int j = 0; j < kIters; ++j) {
      const auto state = sup.health();
      const auto snapshot = sup.events();
      const auto last = sup.last_event();
      (void)state;
      (void)snapshot;
      (void)last;
    }
  });
  writer.join();
  reader.join();
  const auto final_state = sup.health();
  EXPECT_TRUE(final_state == RuntimeHealth::READY ||
              final_state == RuntimeHealth::DEGRADED);
  EXPECT_FALSE(sup.events().empty());
}
}  // namespace
