#include "starling/prospective/action_guard.hpp"

namespace starling::prospective {

GuardVerdict check(const ActionGuard& g, std::string_view action_name) {
    if (g.allowed_actions.find(std::string(action_name)) == g.allowed_actions.end())
        return GuardVerdict::Blocked;
    if (g.requires_approval.count(std::string(action_name)))
        return GuardVerdict::RequiresApproval;
    return GuardVerdict::Allow;
}

}  // namespace starling::prospective
