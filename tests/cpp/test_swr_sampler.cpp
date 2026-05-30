#include "starling/replay/swr_sampler.hpp"
#include <gtest/gtest.h>
using namespace starling::replay;

static SamplerInputs base() {
    SamplerInputs i; i.salience=0.8; i.provenance="user_input";
    i.last_replayed_iso=""; return i;
}

TEST(SwrSampler, ReplayDerivedNotInPool) {
    auto i=base(); i.provenance="replay_derived";
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, TomInferredQuarterFactor) {
    EXPECT_DOUBLE_EQ(provenance_factor("tom_inferred"), 0.25);
    EXPECT_DOUBLE_EQ(provenance_factor("user_input"), 1.0);
}
TEST(SwrSampler, CooldownZerosWeight) {
    auto i=base(); i.last_replayed_iso="2026-05-27T09:58:00Z";
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, ConflictBypassesCooldown) {
    auto i=base(); i.last_replayed_iso="2026-05-27T09:58:00Z"; i.has_conflict=true;
    EXPECT_GT(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, DerivedDepth3Excluded) {
    auto i=base(); i.derived_depth=3;
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, GoalRelevantBoostsWeight) {
    auto g=base(); g.goal_relevant=true;
    auto n=base(); n.goal_relevant=false;
    EXPECT_GT(sample_weight(g, {}, "2026-05-27T10:00:00Z"),
              sample_weight(n, {}, "2026-05-27T10:00:00Z"));
}
TEST(SwrSampler, WMinTruncatesLowWeight) {
    auto i=base(); i.salience=0.001; i.replay_count=100;
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
