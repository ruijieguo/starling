#pragma once

#include <functional>
#include <string>
#include <vector>

namespace starling {

// 4-state runtime health, per subsystems_design/05_governance.md.
// M0.0 implements UNREADY <-> READY only; DEGRADED / DRAINING arrive in P2 with
// background scheduling. Forward-declared here so later milestones extend without
// breaking signatures.
enum class RuntimeHealth {
    UNREADY = 0,
    READY = 1,
    DEGRADED = 2,
    DRAINING = 3,
};

// Not thread-safe; M0.0 callers run on a single thread. P2's background scheduler
// will need either external synchronization or an internal redesign.
class RuntimeHealthMonitor {
public:
    using ChangeListener = std::function<void(RuntimeHealth from, RuntimeHealth to,
                                              const std::vector<std::string>& missing)>;

    RuntimeHealthMonitor() = default;

    RuntimeHealth state() const noexcept { return state_; }

    // Replaces any previously installed listener. M0.0 supports a single
    // listener; a multiplexer can be added in P2 without changing this signature.
    void on_change(ChangeListener listener);

    // Listener exception policy (M0.0): if the listener throws, the new state has
    // already been committed; the exception propagates out of set_ready / set_unready.
    // P2's Python supervisor (Task 8 wraps via pybind) is responsible for not letting
    // Python callbacks throw. A future revision may catch and log; do not depend on
    // either behavior yet.
    void set_ready();
    void set_unready(std::vector<std::string> missing_capabilities);

private:
    RuntimeHealth state_ = RuntimeHealth::UNREADY;
    ChangeListener listener_;
};

}  // namespace starling
