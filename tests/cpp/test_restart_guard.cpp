#include "starling/governance/restart_guard.hpp"

#include <gtest/gtest.h>

using starling::governance::RestartGuard;
using starling::governance::RestartGuardConfig;

namespace {

// Canonical iso8601 UTC timestamps used throughout these tests.
// "recent" restarts fall in the range [2026-06-30T10:00:00Z .. 2026-06-30T10:05:00Z].
// cutoff_inside  = "2026-06-30T09:00:00Z"  — older than all restart marks → in-window
// cutoff_outside = "2026-06-30T11:00:00Z"  — newer than all restart marks → out-of-window
constexpr std::string_view kRestartTs1     = "2026-06-30T10:00:00Z";
constexpr std::string_view kRestartTs2     = "2026-06-30T10:01:00Z";
constexpr std::string_view kRestartTs3     = "2026-06-30T10:02:00Z";
constexpr std::string_view kCutoffInside   = "2026-06-30T09:00:00Z";  // cutoff < all marks
constexpr std::string_view kCutoffOutside  = "2026-06-30T11:00:00Z";  // cutoff > all marks
constexpr std::string_view kCutoffMid      = "2026-06-30T10:01:30Z";  // between ts2 and ts3

// ── Restart-window threshold ─────────────────────────────────────────────────

TEST(RestartGuard, BelowBothThresholdsPauseFalse) {
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 3,
                                          .max_consecutive_no_success = 3}};
    // Zero restarts, zero no-success — should_pause_lane must be false.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));
}

TEST(RestartGuard, RestartsInWindowTripPause) {
    // max_restarts_in_window = 2 → need > 2 in-window restarts to trip (i.e. 3).
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 2,
                                          .max_consecutive_no_success = 99}};

    guard.record_restart(kRestartTs1);
    guard.record_restart(kRestartTs2);
    // count in window = 2; 2 > 2 is false — not yet tripped.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));

    guard.record_restart(kRestartTs3);
    // count in window = 3; 3 > 2 — tripped.
    EXPECT_TRUE(guard.should_pause_lane(kCutoffInside));
}

TEST(RestartGuard, SameRestartsOutOfWindowDoNotTrip) {
    // The same 3 restart marks, but cutoff is AFTER all of them → 0 in-window.
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 2,
                                          .max_consecutive_no_success = 99}};

    guard.record_restart(kRestartTs1);
    guard.record_restart(kRestartTs2);
    guard.record_restart(kRestartTs3);

    // cutoff_outside > all marks → no mark satisfies ts >= cutoff → count = 0; 0 > 2 → false.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffOutside));
}

TEST(RestartGuard, PartialWindowCountsOnlyMarksOnOrAfterCutoff) {
    // kCutoffMid = "2026-06-30T10:01:30Z" — only kRestartTs3 ("2026-06-30T10:02:00Z") qualifies.
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 1,
                                          .max_consecutive_no_success = 99}};

    guard.record_restart(kRestartTs1);
    guard.record_restart(kRestartTs2);
    guard.record_restart(kRestartTs3);

    // Only ts3 >= kCutoffMid → in-window count = 1; 1 > 1 → false.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffMid));

    // With max_restarts_in_window = 0, even 1 in-window restart trips it.
    RestartGuard guard2{RestartGuardConfig{.max_restarts_in_window = 0,
                                           .max_consecutive_no_success = 99}};
    guard2.record_restart(kRestartTs3);
    // count = 1; 1 > 0 → true.
    EXPECT_TRUE(guard2.should_pause_lane(kCutoffInside));
}

// ── Consecutive-no-success threshold ────────────────────────────────────────

TEST(RestartGuard, NoSuccessThresholdTrips) {
    // max_consecutive_no_success = 2 → need > 2 (i.e. 3 calls) to trip.
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 99,
                                          .max_consecutive_no_success = 2}};

    guard.record_no_success();
    guard.record_no_success();
    // consecutive = 2; 2 > 2 → false.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));

    guard.record_no_success();
    // consecutive = 3; 3 > 2 → true.
    EXPECT_TRUE(guard.should_pause_lane(kCutoffInside));
}

TEST(RestartGuard, RecordSuccessResetsConsecutiveNoSuccess) {
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 99,
                                          .max_consecutive_no_success = 2}};

    guard.record_no_success();
    guard.record_no_success();
    guard.record_no_success();
    // consecutive = 3 → tripped.
    EXPECT_TRUE(guard.should_pause_lane(kCutoffInside));

    guard.record_success();
    // consecutive = 0 → no longer tripped.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));
}

TEST(RestartGuard, RecordSuccessMidStreakPreventsTrip) {
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 99,
                                          .max_consecutive_no_success = 2}};

    guard.record_no_success();
    guard.record_no_success();
    guard.record_success();   // reset mid-streak
    guard.record_no_success();
    guard.record_no_success();
    // consecutive restarted from 0 after success → now only 2; 2 > 2 → false.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));
}

// ── Either threshold alone trips ────────────────────────────────────────────

TEST(RestartGuard, RestartWindowAloneTripsPause) {
    // no-success threshold is very high; only restart window can trip it.
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 1,
                                          .max_consecutive_no_success = 9999}};

    guard.record_restart(kRestartTs1);
    guard.record_restart(kRestartTs2);
    // count = 2; 2 > 1 → true; consecutive = 0; 0 > 9999 → false. OR → true.
    EXPECT_TRUE(guard.should_pause_lane(kCutoffInside));
}

TEST(RestartGuard, NoSuccessAloneTripsPause) {
    // restart-window threshold is very high; only no-success can trip it.
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 9999,
                                          .max_consecutive_no_success = 1}};

    guard.record_no_success();
    guard.record_no_success();
    // consecutive = 2; 2 > 1 → true; restart count = 0; 0 > 9999 → false. OR → true.
    EXPECT_TRUE(guard.should_pause_lane(kCutoffInside));
}

// ── Boundary: exact-threshold counts do NOT trip (> not >=) ─────────────────

TEST(RestartGuard, ExactThresholdCountDoesNotTrip) {
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 3,
                                          .max_consecutive_no_success = 3}};

    guard.record_restart(kRestartTs1);
    guard.record_restart(kRestartTs2);
    guard.record_restart(kRestartTs3);
    // count = 3; 3 > 3 → false.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));

    guard.record_no_success();
    guard.record_no_success();
    guard.record_no_success();
    // consecutive = 3; 3 > 3 → false. Neither threshold exceeded.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));
}

// ── Multiple record_success calls only reset, not go negative ───────────────

TEST(RestartGuard, MultipleSuccessCallsIdempotentReset) {
    RestartGuard guard{RestartGuardConfig{.max_restarts_in_window = 99,
                                          .max_consecutive_no_success = 0}};

    guard.record_success();
    guard.record_success();
    guard.record_success();
    // consecutive is clamped at 0; 0 > 0 → false.
    EXPECT_FALSE(guard.should_pause_lane(kCutoffInside));

    // One no-success now trips it (max=0 → >0 → true).
    guard.record_no_success();
    EXPECT_TRUE(guard.should_pause_lane(kCutoffInside));
}

}  // namespace
