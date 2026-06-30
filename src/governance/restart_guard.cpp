#include "starling/governance/restart_guard.hpp"

#include <algorithm>
#include <string>

namespace starling::governance {

RestartGuard::RestartGuard(RestartGuardConfig config) : config_(config) {}

void RestartGuard::record_restart(std::string_view now_iso) {
    restart_marks_.emplace_back(now_iso);
}

void RestartGuard::record_no_success() {
    consecutive_no_success_ += 1;
}

void RestartGuard::record_success() {
    consecutive_no_success_ = 0;
}

bool RestartGuard::should_pause_lane(std::string_view cutoff_iso) const {
    // Count restart marks with ts >= cutoff_iso (canonical iso8601 UTC string compare).
    const int in_window = static_cast<int>(
        std::ranges::count_if(restart_marks_, [&cutoff_iso](const std::string& mark) {
            return mark >= cutoff_iso;
        }));

    return (in_window > config_.max_restarts_in_window) ||
           (consecutive_no_success_ > config_.max_consecutive_no_success);
}

}  // namespace starling::governance
