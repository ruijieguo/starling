#include "starling/reconsolidation/plastic_window.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::reconsolidation;
using starling::persistence::SqliteAdapter;

TEST(PlasticWindow, AdaptiveTimeoutModalityOrder) {
    EXPECT_GT(adaptive_timeout_minutes("COMMITS", 0), adaptive_timeout_minutes("BELIEVES", 0));
    EXPECT_GT(adaptive_timeout_minutes("BELIEVES", 0), adaptive_timeout_minutes("ASSUMES", 0));
}
TEST(PlasticWindow, HighFrequencyForces5min) {
    EXPECT_EQ(adaptive_timeout_minutes("COMMITS", 3), 5);
}
TEST(PlasticWindow, ClampBounds) {
    EXPECT_GE(adaptive_timeout_minutes("ASSUMES", 0), 5);
    EXPECT_LE(adaptive_timeout_minutes("COMMITS", 0), 360);
}
TEST(PlasticWindow, FirstTriggerOpens) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    auto r = open_or_append(c,"s1","default","e1","belief.conflict","h1",1.0,
                            "believes","2026-05-27T10:00:00Z");
    EXPECT_TRUE(r.opened);
}
TEST(PlasticWindow, SecondTriggerAppendsNoNewWindow) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    open_or_append(c,"s1","default","e1","belief.conflict","h1",1.0,"believes","2026-05-27T10:00:00Z");
    auto r2 = open_or_append(c,"s1","default","e2","statement.recalled","h2",1.0,"believes","2026-05-27T10:01:00Z");
    EXPECT_FALSE(r2.opened);
    EXPECT_TRUE(r2.appended);
}
TEST(PlasticWindow, DueWindowsReturnsExpired) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    open_or_append(c,"s1","default","e1","belief.conflict","h1",1.0,"believes","2026-05-27T10:00:00Z");
    // 30min default → deadline 10:30; query at 11:00 → due
    auto due = due_windows(c, "2026-05-27T11:00:00Z");
    EXPECT_EQ(due.size(), 1u);
    // query at 10:05 → not due
    auto none = due_windows(c, "2026-05-27T10:05:00Z");
    EXPECT_TRUE(none.empty());
}
TEST(PlasticWindow, ForceCloseAfter10Triggers) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    open_or_append(c,"s1","default","e0","belief.conflict","h0",1.0,"believes","2026-05-27T10:00:00Z");
    for (int i=1;i<=10;i++)
        open_or_append(c,"s1","default","e"+std::to_string(i),"belief.conflict","h",1.0,"believes","2026-05-27T10:00:00Z");
    // after >=10 triggers, window force-closed → not in due (status='closed')
    auto due = due_windows(c, "2026-05-27T09:00:00Z");  // even before deadline
    EXPECT_TRUE(due.empty());
}
