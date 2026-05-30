// tests/cpp/test_action_guard.cpp
#include "starling/prospective/action_guard.hpp"
#include <gtest/gtest.h>
using namespace starling::prospective;

TEST(ActionGuard, FailClosedAndApproval) {
    ActionGuard g;
    g.allowed_actions = {"send_reminder", "log_note"};
    g.requires_approval = {"send_reminder"};
    EXPECT_EQ(check(g, "log_note"), GuardVerdict::Allow);
    EXPECT_EQ(check(g, "send_reminder"), GuardVerdict::RequiresApproval);
    EXPECT_EQ(check(g, "delete_everything"), GuardVerdict::Blocked);
}
