#include "starling/replay/forgetting_curve.hpp"
#include <gtest/gtest.h>
#include <cmath>
using namespace starling::replay;

TEST(ForgettingCurve, FreshAccessNearOne) {
    ForgettingInputs in; in.salience=0.5; in.modality="BELIEVES";
    in.last_accessed_iso="2026-05-27T10:00:00Z";
    EXPECT_GT(compute_s_t(in, "2026-05-27T10:00:01Z"), 0.99);
}
TEST(ForgettingCurve, CommitsDecaysSlowerThanAssumes) {
    ForgettingInputs c; c.modality="COMMITS"; c.last_accessed_iso="2026-05-01T00:00:00Z";
    ForgettingInputs a; a.modality="ASSUMES"; a.last_accessed_iso="2026-05-01T00:00:00Z";
    EXPECT_GT(compute_s_t(c, "2026-05-27T00:00:00Z"),
              compute_s_t(a, "2026-05-27T00:00:00Z"));
}
TEST(ForgettingCurve, ActiveGroundedBoostsS0) {
    ForgettingInputs g; g.active_grounded=true; g.modality="BELIEVES";
    ForgettingInputs n; n.active_grounded=false; n.modality="BELIEVES";
    EXPECT_GT(compute_s0(g), compute_s0(n));
}
TEST(ForgettingCurve, AccessCountSlowsDecay) {
    ForgettingInputs hi; hi.access_count=10; hi.modality="BELIEVES";
    ForgettingInputs lo; lo.access_count=0; lo.modality="BELIEVES";
    EXPECT_GT(compute_s0(hi), compute_s0(lo));
}
TEST(ForgettingCurve, OldStatementBelowThreshold) {
    ForgettingInputs in; in.salience=0.0; in.modality="ASSUMES";
    in.last_accessed_iso="2025-01-01T00:00:00Z";
    EXPECT_LT(compute_s_t(in, "2026-05-27T00:00:00Z"), 0.05);
}
TEST(ForgettingCurve, SecondsUntilIsCurveInverse) {
    // P3 片 5:Δt = -S0·ln(target);把 Δt 加回 last_accessed,S(t) 应回到 target。
    ForgettingInputs in; in.salience=0.0; in.modality="BELIEVES";
    const double s0 = compute_s0(in);
    EXPECT_NEAR(seconds_until_retrievability(in, 0.05), -s0 * std::log(0.05), 1e-6);
    EXPECT_GT(seconds_until_retrievability(in, 0.05), 0.0);   // target<1 → 正向时间
    // 出界:target ∉ (0,1) → -1(无投影)。
    EXPECT_LT(seconds_until_retrievability(in, 0.0), 0.0);
    EXPECT_LT(seconds_until_retrievability(in, 1.0), 0.0);
}
