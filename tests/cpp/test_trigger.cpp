#include "starling/prospective/trigger.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::prospective;
using starling::persistence::SqliteAdapter;

TEST(Trigger, TimeFiresWhenDue) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "", "", "default"};
    EXPECT_TRUE(evaluate_trigger(c, "time", R"({"at":"2026-05-30T11:00:00Z"})", ctx));
    EXPECT_FALSE(evaluate_trigger(c, "time", R"({"at":"2026-05-30T13:00:00Z"})", ctx));
}
TEST(Trigger, EventMatchesType) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "statement.written", "s1", "default"};
    EXPECT_TRUE(evaluate_trigger(c, "event", R"({"event_type":"statement.written"})", ctx));
    EXPECT_FALSE(evaluate_trigger(c, "event", R"({"event_type":"cognizer.observed"})", ctx));
}
TEST(Trigger, CompoundAllOfShortCircuits) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "statement.written", "s1", "default"};
    EXPECT_TRUE(evaluate_trigger(c, "compound",
        R"({"all_of":[{"kind":"time","spec":{"at":"2026-05-30T11:00:00Z"}},{"kind":"event","spec":{"event_type":"statement.written"}}]})", ctx));
    EXPECT_FALSE(evaluate_trigger(c, "compound",
        R"({"all_of":[{"kind":"time","spec":{"at":"2026-05-30T11:00:00Z"}},{"kind":"event","spec":{"event_type":"x"}}]})", ctx));
}
TEST(Trigger, CompoundAnyOf) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "statement.written", "s1", "default"};
    EXPECT_TRUE(evaluate_trigger(c, "compound",
        R"({"any_of":[{"kind":"event","spec":{"event_type":"nope"}},{"kind":"time","spec":{"at":"2026-05-30T11:00:00Z"}}]})", ctx));
    EXPECT_FALSE(evaluate_trigger(c, "compound",
        R"({"any_of":[{"kind":"event","spec":{"event_type":"nope"}},{"kind":"time","spec":{"at":"2026-05-30T13:00:00Z"}}]})", ctx));
}
