#pragma once
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

// Configuration for RestartGuard — time-based restart window + consecutive-no-success
// threshold (L7). The caller computes cutoff_iso = now - window_seconds; the guard
// holds no clock, only stored canonical iso8601 UTC restart timestamps.
//
// No std::mutex — single-threaded c1 (L2). M0.9+ adds locking when concurrency lands.
struct RestartGuardConfig {
    int max_restarts_in_window = 0;      // restart-count threshold within the time window
    int max_consecutive_no_success = 0;  // consecutive-no-success threshold
};

// Dual-threshold crash-loop guard.
//
// Restart-window arm: record_restart(now_iso) stores a canonical iso8601 UTC timestamp.
// should_pause_lane(cutoff_iso) counts stored timestamps >= cutoff_iso. If that count
// exceeds max_restarts_in_window, the lane must be paused.
//
// Consecutive-no-success arm: record_no_success() increments a counter;
// record_success() resets it to 0. If the counter exceeds max_consecutive_no_success,
// the lane must be paused.
//
// should_pause_lane returns true when EITHER arm exceeds its threshold (OR logic).
//
// lease_until / cutoff_iso contract: canonical iso8601 UTC ("YYYY-MM-DDTHH:MM:SSZ"),
// matching the same CX-8 / L6 contract as PipelineRun and ScopedWorkGate. No parsing
// or arithmetic — the guard only does string-compare ordering, which is sound for this
// format.
class RestartGuard {
public:
    explicit RestartGuard(RestartGuardConfig config);

    // Store now_iso as a restart mark. now_iso must be canonical iso8601 UTC.
    void record_restart(std::string_view now_iso);

    // Increment the consecutive-no-success counter.
    void record_no_success();

    // Reset the consecutive-no-success counter to 0.
    void record_success();

    // Returns true iff:
    //   (count of stored restart timestamps with ts >= cutoff_iso)
    //       > config_.max_restarts_in_window
    //   OR consecutive_no_success_ > config_.max_consecutive_no_success.
    //
    // cutoff_iso: canonical iso8601 UTC; the caller derives it as now - window_seconds.
    // The guard does NO iso arithmetic — only string-compare (canonical format ensures
    // lexicographic order equals chronological order).
    [[nodiscard]] bool should_pause_lane(std::string_view cutoff_iso) const;

private:
    RestartGuardConfig config_;
    std::vector<std::string> restart_marks_;  // canonical iso8601 UTC timestamps
    int consecutive_no_success_ = 0;
};

}  // namespace starling::governance
