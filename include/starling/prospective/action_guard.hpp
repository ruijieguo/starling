// include/starling/prospective/action_guard.hpp
#pragma once
#include <map>
#include <set>
#include <string>
#include <string_view>

namespace starling::prospective {

struct ActionGuard {
    std::string profile_name;
    std::set<std::string> allowed_actions;
    std::set<std::string> requires_approval;
    std::map<std::string, int> idempotency_window_sec;
};

enum class GuardVerdict { Allow, RequiresApproval, Blocked };

// fail-closed: ∉ allowed_actions → Blocked;∈ requires_approval → RequiresApproval;else Allow。
GuardVerdict check(const ActionGuard&, std::string_view action_name);

}  // namespace starling::prospective
