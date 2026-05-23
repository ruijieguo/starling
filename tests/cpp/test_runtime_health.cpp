#include <gtest/gtest.h>

#include "starling/runtime_health.hpp"

using starling::RuntimeHealth;
using starling::RuntimeHealthMonitor;

TEST(RuntimeHealth, StartsUnready) {
    RuntimeHealthMonitor monitor;
    EXPECT_EQ(monitor.state(), RuntimeHealth::UNREADY);
}

TEST(RuntimeHealth, TransitionToReadyEmitsEvent) {
    RuntimeHealthMonitor monitor;
    bool event_seen = false;
    monitor.on_change([&](RuntimeHealth from, RuntimeHealth to,
                          const std::vector<std::string>& missing) {
        EXPECT_EQ(from, RuntimeHealth::UNREADY);
        EXPECT_EQ(to, RuntimeHealth::READY);
        EXPECT_TRUE(missing.empty());
        event_seen = true;
    });
    monitor.set_ready();
    EXPECT_EQ(monitor.state(), RuntimeHealth::READY);
    EXPECT_TRUE(event_seen);
}

TEST(RuntimeHealth, SetUnreadyCarriesMissingCapabilities) {
    RuntimeHealthMonitor monitor;
    std::vector<std::string> captured;
    monitor.on_change([&](RuntimeHealth, RuntimeHealth,
                          const std::vector<std::string>& missing) {
        captured = missing;
    });
    monitor.set_unready({"transactional_outbox", "idx_statement_id_tenant"});
    EXPECT_EQ(monitor.state(), RuntimeHealth::UNREADY);
    EXPECT_EQ(captured.size(), 2);
    EXPECT_EQ(captured[0], "transactional_outbox");
}
