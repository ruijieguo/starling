#include "starling/replay/forgetting_curve.hpp"
#include <gtest/gtest.h>
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
