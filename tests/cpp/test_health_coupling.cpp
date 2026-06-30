#include "starling/governance/health_coupling.hpp"
#include "starling/governance/runtime_supervisor.hpp"
#include "starling/governance/scoped_work_gate.hpp"
#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"

#include <gtest/gtest.h>

namespace {

using starling::ProfileCapability;
using starling::RuntimeHealth;
using starling::governance::GateConfig;
using starling::governance::GateKey;
using starling::governance::Lane;
using starling::governance::RuntimeSupervisor;
using starling::governance::ScopedWorkGate;
using starling::governance::StartOutcome;
using starling::governance::degraded_decision;

// Mirror the all_present() helper from test_runtime_supervisor.cpp / test_runtime_supervisor_transitions.cpp.
ProfileCapability all_present() {
    return ProfileCapability{
        .profile_name              = "local-store",
        .relational_backend        = "seekdb",
        .vector_backend            = "seekdb",
        .graph_backend             = "ladybugdb",
        .c_plus_plus_core          = true,
        .cross_partition_transaction = true,
        .transactional_outbox      = true,
        .consumer_checkpoint       = true,
        .tenant_isolation          = "storage_enforced",
        .engram_per_record_key     = true,
        .engram_refcount           = true,
        .projection_index_supported  = false,
        .dimension_versions_supported = false,
        .testing_helper_marker     = true,
    };
}

// Helper to build a gate key.
GateKey make_key(std::string tenant, std::string scope, std::string aggregate, Lane lane) {
    return GateKey{
        .tenant_id    = std::move(tenant),
        .holder_scope = std::move(scope),
        .aggregate_id = std::move(aggregate),
        .lane         = lane,
    };
}

// ── Test 1: degraded_decision drives a READY supervisor to DEGRADED ──────────

TEST(HealthCoupling, DegradedDecisionDrivesReadySupervisorToDegraded) {
    // Construct a RuntimeSupervisor using the unit-test seam (inject idx_present).
    RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
    ASSERT_EQ(sup.start(), StartOutcome::kReady);
    ASSERT_EQ(sup.health(), RuntimeHealth::READY);

    // Build the decision via the helper and apply it.
    const auto decision = degraded_decision("leaked_lease_sweep");
    sup.note_health(decision);

    EXPECT_EQ(sup.health(), RuntimeHealth::DEGRADED);

    const auto last = sup.last_event();
    ASSERT_TRUE(last.has_value());
    EXPECT_EQ(last->current_status, RuntimeHealth::DEGRADED);
    EXPECT_EQ(last->trigger, "leaked_lease_sweep");
}

// ── Test 2: end-to-end: sweep_leaked non-empty → degraded_decision → DEGRADED ─

TEST(HealthCoupling, SweepLeakedResultDrivesDecisionToSupervisorDegraded) {
    // Build a ScopedWorkGate and acquire a slot with a past lease.
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 1}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Soft);

    // Acquire with a lease that is already in the past relative to sweep cutoff.
    const auto result = gate.acquire(key, "stale-task", "2026-06-29T11:00:00Z");
    ASSERT_EQ(result.status, starling::governance::AdmitStatus::Admitted);

    // Sweep at a "now" after the lease_until — should return the stale task_id.
    const auto freed = gate.sweep_leaked("2026-06-29T12:00:00Z");
    ASSERT_FALSE(freed.empty());

    // Build a READY supervisor, apply the degraded_decision triggered by the sweep.
    RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
    ASSERT_EQ(sup.start(), StartOutcome::kReady);

    // The caller pattern (no tick wiring per L1).
    sup.note_health(degraded_decision("leaked_lease_sweep"));

    EXPECT_EQ(sup.health(), RuntimeHealth::DEGRADED);

    const auto last = sup.last_event();
    ASSERT_TRUE(last.has_value());
    EXPECT_EQ(last->current_status, RuntimeHealth::DEGRADED);
    EXPECT_EQ(last->trigger, "leaked_lease_sweep");
}

}  // namespace
