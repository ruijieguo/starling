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

class RuntimeHealthMonitor {
public:
    using ChangeListener = std::function<void(RuntimeHealth from, RuntimeHealth to,
                                              const std::vector<std::string>& missing)>;

    RuntimeHealthMonitor() = default;

    RuntimeHealth state() const noexcept { return state_; }

    void on_change(ChangeListener listener);

    void set_ready();
    void set_unready(std::vector<std::string> missing_capabilities);

private:
    RuntimeHealth state_ = RuntimeHealth::UNREADY;
    ChangeListener listener_;
};

}  // namespace starling
