#include "starling/governance/tick_load_shedding.hpp"
#include "starling/runtime_health.hpp"

#include <gtest/gtest.h>

using starling::RuntimeHealth;
using starling::governance::TickLane;
using starling::governance::TickStage;
using starling::governance::lane_of;
using starling::governance::should_run_stage;

namespace {

// ── lane_of: pin every stage per LOCKED L4 classification ────────────────────

TEST(TickLoadShedding_LaneOf, EmbedIsSoft) {
    EXPECT_EQ(lane_of(TickStage::Embed), TickLane::Soft);
}

TEST(TickLoadShedding_LaneOf, PolicyIsCritical) {
    EXPECT_EQ(lane_of(TickStage::Policy), TickLane::Critical);
}

TEST(TickLoadShedding_LaneOf, CommonGroundIsSoft) {
    EXPECT_EQ(lane_of(TickStage::CommonGround), TickLane::Soft);
}

TEST(TickLoadShedding_LaneOf, ReplayOscillationGuardIsCritical) {
    EXPECT_EQ(lane_of(TickStage::ReplayOscillationGuard), TickLane::Critical);
}

TEST(TickLoadShedding_LaneOf, ReplayTtlSweepIsCritical) {
    EXPECT_EQ(lane_of(TickStage::ReplayTtlSweep), TickLane::Critical);
}

TEST(TickLoadShedding_LaneOf, ReplayIdleIsSoft) {
    EXPECT_EQ(lane_of(TickStage::ReplayIdle), TickLane::Soft);
}

TEST(TickLoadShedding_LaneOf, PersonaIsSoft) {
    EXPECT_EQ(lane_of(TickStage::Persona), TickLane::Soft);
}

TEST(TickLoadShedding_LaneOf, ProjectionIsSoft) {
    EXPECT_EQ(lane_of(TickStage::Projection), TickLane::Soft);
}

TEST(TickLoadShedding_LaneOf, OutboxIsCritical) {
    EXPECT_EQ(lane_of(TickStage::Outbox), TickLane::Critical);
}

// ── should_run_stage: READY → all 9 stages run ───────────────────────────────

TEST(TickLoadShedding_ShouldRunStage, ReadyRunsAllStages) {
    constexpr RuntimeHealth health = RuntimeHealth::READY;
    EXPECT_TRUE(should_run_stage(TickStage::Embed,                  health));
    EXPECT_TRUE(should_run_stage(TickStage::Policy,                 health));
    EXPECT_TRUE(should_run_stage(TickStage::CommonGround,           health));
    EXPECT_TRUE(should_run_stage(TickStage::ReplayOscillationGuard, health));
    EXPECT_TRUE(should_run_stage(TickStage::ReplayTtlSweep,         health));
    EXPECT_TRUE(should_run_stage(TickStage::ReplayIdle,             health));
    EXPECT_TRUE(should_run_stage(TickStage::Persona,                health));
    EXPECT_TRUE(should_run_stage(TickStage::Projection,             health));
    EXPECT_TRUE(should_run_stage(TickStage::Outbox,                 health));
}

// ── should_run_stage: DEGRADED → Critical only (Soft skipped) ────────────────

TEST(TickLoadShedding_ShouldRunStage, DegradedSkipsSoftStages) {
    constexpr RuntimeHealth health = RuntimeHealth::DEGRADED;
    EXPECT_FALSE(should_run_stage(TickStage::Embed,        health));
    EXPECT_FALSE(should_run_stage(TickStage::CommonGround, health));
    EXPECT_FALSE(should_run_stage(TickStage::ReplayIdle,   health));
    EXPECT_FALSE(should_run_stage(TickStage::Persona,      health));
    EXPECT_FALSE(should_run_stage(TickStage::Projection,   health));
}

TEST(TickLoadShedding_ShouldRunStage, DegradedKeepsCriticalStages) {
    constexpr RuntimeHealth health = RuntimeHealth::DEGRADED;
    EXPECT_TRUE(should_run_stage(TickStage::Policy,                 health));
    EXPECT_TRUE(should_run_stage(TickStage::ReplayOscillationGuard, health));
    EXPECT_TRUE(should_run_stage(TickStage::ReplayTtlSweep,         health));
    EXPECT_TRUE(should_run_stage(TickStage::Outbox,                  health));
}

// ── should_run_stage: DRAINING → Outbox only ─────────────────────────────────

TEST(TickLoadShedding_ShouldRunStage, DrainingRunsOutboxOnly) {
    constexpr RuntimeHealth health = RuntimeHealth::DRAINING;
    EXPECT_FALSE(should_run_stage(TickStage::Embed,                  health));
    EXPECT_FALSE(should_run_stage(TickStage::Policy,                 health));
    EXPECT_FALSE(should_run_stage(TickStage::CommonGround,           health));
    EXPECT_FALSE(should_run_stage(TickStage::ReplayOscillationGuard, health));
    EXPECT_FALSE(should_run_stage(TickStage::ReplayTtlSweep,         health));
    EXPECT_FALSE(should_run_stage(TickStage::ReplayIdle,             health));
    EXPECT_FALSE(should_run_stage(TickStage::Persona,                health));
    EXPECT_FALSE(should_run_stage(TickStage::Projection,             health));
    EXPECT_TRUE(should_run_stage(TickStage::Outbox,                  health));
}

// ── should_run_stage: UNREADY → all false (fail-closed) ──────────────────────

TEST(TickLoadShedding_ShouldRunStage, UnreadyRunsNoStages) {
    constexpr RuntimeHealth health = RuntimeHealth::UNREADY;
    EXPECT_FALSE(should_run_stage(TickStage::Embed,                  health));
    EXPECT_FALSE(should_run_stage(TickStage::Policy,                 health));
    EXPECT_FALSE(should_run_stage(TickStage::CommonGround,           health));
    EXPECT_FALSE(should_run_stage(TickStage::ReplayOscillationGuard, health));
    EXPECT_FALSE(should_run_stage(TickStage::ReplayTtlSweep,         health));
    EXPECT_FALSE(should_run_stage(TickStage::ReplayIdle,             health));
    EXPECT_FALSE(should_run_stage(TickStage::Persona,                health));
    EXPECT_FALSE(should_run_stage(TickStage::Projection,             health));
    EXPECT_FALSE(should_run_stage(TickStage::Outbox,                 health));
}

}  // namespace
