#include "starling/runtime_health.hpp"

#include <utility>

namespace starling {

void RuntimeHealthMonitor::on_change(ChangeListener listener) {
    listener_ = std::move(listener);
}

void RuntimeHealthMonitor::set_ready() {
    const RuntimeHealth from = state_;
    state_ = RuntimeHealth::READY;
    if (listener_) {
        listener_(from, state_, {});
    }
}

void RuntimeHealthMonitor::set_unready(std::vector<std::string> missing_capabilities) {
    const RuntimeHealth from = state_;
    state_ = RuntimeHealth::UNREADY;
    if (listener_) {
        listener_(from, state_, std::move(missing_capabilities));
    }
}

}  // namespace starling
