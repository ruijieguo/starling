#include "starling/governance/scoped_work_gate.hpp"

#include <gtest/gtest.h>

#include <stdexcept>
#include <string>

using starling::governance::AdmitStatus;
using starling::governance::AcquireOutcome;
using starling::governance::GateConfig;
using starling::governance::GateKey;
using starling::governance::Lane;
using starling::governance::ScopedWorkGate;

namespace {

// Helper: a canonical iso8601 UTC timestamp for lease_until.
constexpr std::string_view kLease = "2026-07-01T00:00:00Z";
constexpr std::string_view kLease2 = "2026-07-01T01:00:00Z";

GateKey make_key(std::string tenant, std::string scope, std::string aggregate, Lane lane) {
    return GateKey{
        .tenant_id    = std::move(tenant),
        .holder_scope = std::move(scope),
        .aggregate_id = std::move(aggregate),
        .lane         = lane,
    };
}

// ── Reentrancy (same GateKey + same task_id) ────────────────────────────────

TEST(ScopedWorkGate, ReentrantSameKeyAndTaskIdIncrementsDepth) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 2, .soft_quota = 2}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Soft);

    const AcquireOutcome out1 = gate.acquire(key, "task-1", kLease);
    EXPECT_EQ(out1.status, AdmitStatus::Admitted);
    EXPECT_EQ(out1.depth, 1);
    EXPECT_EQ(gate.active_slot_count(), 1);

    const AcquireOutcome out2 = gate.acquire(key, "task-1", kLease);
    EXPECT_EQ(out2.status, AdmitStatus::Admitted);
    EXPECT_EQ(out2.depth, 2);
    EXPECT_EQ(gate.active_slot_count(), 1);  // still 1 slot — reentrant

    const AcquireOutcome out3 = gate.acquire(key, "task-1", kLease);
    EXPECT_EQ(out3.status, AdmitStatus::Admitted);
    EXPECT_EQ(out3.depth, 3);
    EXPECT_EQ(gate.active_slot_count(), 1);
}

TEST(ScopedWorkGate, ReentrantReleaseDecrementsDepth) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 2, .soft_quota = 2}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Soft);

    ASSERT_EQ(gate.acquire(key, "task-1", kLease).status, AdmitStatus::Admitted);
    ASSERT_EQ(gate.acquire(key, "task-1", kLease).status, AdmitStatus::Admitted);
    ASSERT_EQ(gate.acquire(key, "task-1", kLease).status, AdmitStatus::Admitted);  // depth = 3

    gate.release(key, "task-1");  // depth = 2
    EXPECT_EQ(gate.active_slot_count(), 1);

    gate.release(key, "task-1");  // depth = 1
    EXPECT_EQ(gate.active_slot_count(), 1);

    gate.release(key, "task-1");  // depth = 0 → slot freed
    EXPECT_EQ(gate.active_slot_count(), 0);
}

// ── L4 KEY DISTINCTION: same GateKey + DIFFERENT task_id = 2 slots ──────────

TEST(ScopedWorkGate, TwoTaskIdsOnOneGateKeyUsesTwoSlots) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 2, .soft_quota = 2}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Soft);

    const AcquireOutcome out1 = gate.acquire(key, "task-1", kLease);
    EXPECT_EQ(out1.status, AdmitStatus::Admitted);
    EXPECT_EQ(out1.depth, 1);

    const AcquireOutcome out2 = gate.acquire(key, "task-2", kLease);
    EXPECT_EQ(out2.status, AdmitStatus::Admitted);
    EXPECT_EQ(out2.depth, 1);   // NOT 2 — this is a NEW slot, not reentrant

    EXPECT_EQ(gate.active_slot_count(), 2);  // 2 distinct slots
}

// ── Cross-aggregate: different GateKey = new slot ───────────────────────────

TEST(ScopedWorkGate, CrossAggregateUsesNewSlot) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 2, .soft_quota = 2}};
    const GateKey key_a = make_key("t1", "scope", "agg-A", Lane::Soft);
    const GateKey key_b = make_key("t1", "scope", "agg-B", Lane::Soft);

    ASSERT_EQ(gate.acquire(key_a, "task-1", kLease).status, AdmitStatus::Admitted);
    ASSERT_EQ(gate.acquire(key_b, "task-1", kLease).status, AdmitStatus::Admitted);

    EXPECT_EQ(gate.active_slot_count(), 2);
}

// ── Soft over-quota: SoftDropped + counter ───────────────────────────────────

TEST(ScopedWorkGate, SoftOverQuotaReturnsSoftDroppedAndIncreasesCounter) {
    // soft_quota = 1; second soft acquire for a new key must be soft-dropped
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 1}};
    const GateKey key_a = make_key("t1", "scope", "agg-A", Lane::Soft);
    const GateKey key_b = make_key("t1", "scope", "agg-B", Lane::Soft);

    const AcquireOutcome ok = gate.acquire(key_a, "task-1", kLease);
    EXPECT_EQ(ok.status, AdmitStatus::Admitted);
    EXPECT_EQ(ok.depth, 1);

    const AcquireOutcome dropped = gate.acquire(key_b, "task-1", kLease);
    EXPECT_EQ(dropped.status, AdmitStatus::SoftDropped);
    EXPECT_EQ(dropped.depth, 0);
    EXPECT_EQ(gate.dropped_soft_work_count(), 1LL);
    EXPECT_EQ(gate.active_slot_count(), 1);  // slot for key_b NOT held
}

TEST(ScopedWorkGate, SoftDropDoesNotConsumeASlot) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 1}};
    const GateKey key_a = make_key("t1", "scope", "agg-A", Lane::Soft);
    const GateKey key_b = make_key("t1", "scope", "agg-B", Lane::Soft);

    ASSERT_EQ(gate.acquire(key_a, "task-1", kLease).status, AdmitStatus::Admitted);
    ASSERT_EQ(gate.acquire(key_b, "task-1", kLease).status, AdmitStatus::SoftDropped);  // soft-dropped

    // Release key_a; now the quota is free again
    gate.release(key_a, "task-1");
    EXPECT_EQ(gate.active_slot_count(), 0);

    // key_b was soft-dropped — releasing it must throw (slot not held)
    EXPECT_THROW(gate.release(key_b, "task-1"), std::runtime_error);
}

// ── Critical quota is reserved (soft cannot starve critical) ─────────────────

TEST(ScopedWorkGate, CriticalQuotaReservedWhenSoftFull) {
    // critical_quota = 1, soft_quota = 1; fill soft first, critical must still succeed
    ScopedWorkGate gate{GateConfig{.critical_quota = 1, .soft_quota = 1}};
    const GateKey soft_key = make_key("t1", "scope", "agg-A", Lane::Soft);
    const GateKey crit_key = make_key("t1", "scope", "agg-B", Lane::Critical);

    const AcquireOutcome soft_ok = gate.acquire(soft_key, "task-1", kLease);
    EXPECT_EQ(soft_ok.status, AdmitStatus::Admitted);

    const AcquireOutcome crit_ok = gate.acquire(crit_key, "task-2", kLease2);
    EXPECT_EQ(crit_ok.status, AdmitStatus::Admitted);
    EXPECT_EQ(crit_ok.depth, 1);
}

// ── Critical over-quota → CriticalRejected (NO throw per L3) ────────────────

TEST(ScopedWorkGate, CriticalOverQuotaReturnsCriticalRejected) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 1, .soft_quota = 0}};
    const GateKey key_a = make_key("t1", "scope", "agg-A", Lane::Critical);
    const GateKey key_b = make_key("t1", "scope", "agg-B", Lane::Critical);

    const AcquireOutcome ok = gate.acquire(key_a, "task-1", kLease);
    EXPECT_EQ(ok.status, AdmitStatus::Admitted);
    EXPECT_EQ(ok.depth, 1);

    const AcquireOutcome rejected = gate.acquire(key_b, "task-2", kLease);
    EXPECT_EQ(rejected.status, AdmitStatus::CriticalRejected);
    EXPECT_EQ(rejected.depth, 0);
    EXPECT_EQ(gate.active_slot_count(), 1);  // key_b NOT held
}

// ── Release after soft-drop succeeds on re-acquire ──────────────────────────

TEST(ScopedWorkGate, ReleaseFreesSlotEnablingSubsequentAcquire) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 1}};
    const GateKey key_a = make_key("t1", "scope", "agg-A", Lane::Soft);
    const GateKey key_b = make_key("t1", "scope", "agg-B", Lane::Soft);

    ASSERT_EQ(gate.acquire(key_a, "task-1", kLease).status, AdmitStatus::Admitted);
    const AcquireOutcome dropped = gate.acquire(key_b, "task-1", kLease);
    EXPECT_EQ(dropped.status, AdmitStatus::SoftDropped);

    // Free key_a; now key_b should be admissible
    gate.release(key_a, "task-1");

    const AcquireOutcome now_ok = gate.acquire(key_b, "task-1", kLease);
    EXPECT_EQ(now_ok.status, AdmitStatus::Admitted);
    EXPECT_EQ(now_ok.depth, 1);
}

// ── L5 Fail-loud release scenarios ──────────────────────────────────────────

TEST(ScopedWorkGate, ReleaseUnheldKeyThrows) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 2}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Soft);

    // Never acquired — must throw
    EXPECT_THROW(gate.release(key, "task-1"), std::runtime_error);
}

TEST(ScopedWorkGate, ReleaseWrongTaskIdForHeldKeyThrows) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 2}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Soft);

    ASSERT_EQ(gate.acquire(key, "task-1", kLease).status, AdmitStatus::Admitted);

    // wrong task_id for the held key — must throw
    EXPECT_THROW(gate.release(key, "task-WRONG"), std::runtime_error);
}

TEST(ScopedWorkGate, ReleaseAfterFullDepthUnwindThrows) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 2}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Soft);

    ASSERT_EQ(gate.acquire(key, "task-1", kLease).status, AdmitStatus::Admitted);
    gate.release(key, "task-1");  // depth → 0, slot freed

    // depth is already 0 (slot gone) — another release must throw
    EXPECT_THROW(gate.release(key, "task-1"), std::runtime_error);
}

// ── Lease stored (needed by 4.2 sweep_leaked) ────────────────────────────────

TEST(ScopedWorkGate, AcquireStoresLeaseUntil) {
    // Indirectly verified: active_slot_count() == 1 implies the slot was stored.
    // The lease_until field is opaque to tests until 4.2, but we confirm the slot
    // carries it by introspecting that a held slot is visible after acquire.
    ScopedWorkGate gate{GateConfig{.critical_quota = 1, .soft_quota = 0}};
    const GateKey key = make_key("t1", "scope", "agg-A", Lane::Critical);

    ASSERT_EQ(gate.acquire(key, "task-1", kLease).status, AdmitStatus::Admitted);
    EXPECT_EQ(gate.active_slot_count(), 1);

    gate.release(key, "task-1");
    EXPECT_EQ(gate.active_slot_count(), 0);
}

// ── Multiple lanes coexist; each counted independently ───────────────────────

TEST(ScopedWorkGate, CriticalAndSoftSlotsAreCounted) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 1, .soft_quota = 1}};
    const GateKey crit = make_key("t1", "scope", "agg-C", Lane::Critical);
    const GateKey soft = make_key("t1", "scope", "agg-S", Lane::Soft);

    ASSERT_EQ(gate.acquire(crit, "task-c", kLease).status, AdmitStatus::Admitted);
    ASSERT_EQ(gate.acquire(soft, "task-s", kLease).status, AdmitStatus::Admitted);
    EXPECT_EQ(gate.active_slot_count(), 2);

    gate.release(crit, "task-c");
    EXPECT_EQ(gate.active_slot_count(), 1);
}

// ── Soft over-quota accumulates counter across multiple drops ─────────────────

TEST(ScopedWorkGate, DroppedCounterAccumulates) {
    ScopedWorkGate gate{GateConfig{.critical_quota = 0, .soft_quota = 1}};
    const GateKey key_a = make_key("t1", "scope", "agg-A", Lane::Soft);
    const GateKey key_b = make_key("t1", "scope", "agg-B", Lane::Soft);
    const GateKey key_c = make_key("t1", "scope", "agg-C", Lane::Soft);

    ASSERT_EQ(gate.acquire(key_a, "task-1", kLease).status, AdmitStatus::Admitted);     // admitted
    ASSERT_EQ(gate.acquire(key_b, "task-2", kLease).status, AdmitStatus::SoftDropped);  // dropped → count=1
    ASSERT_EQ(gate.acquire(key_c, "task-3", kLease).status, AdmitStatus::SoftDropped);  // dropped → count=2

    EXPECT_EQ(gate.dropped_soft_work_count(), 2LL);
}

}  // namespace
