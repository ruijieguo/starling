#include "starling/prospective/trigger.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <string>
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

// P2.c hardening (B#5): a deeply nested compound trigger must return false
// without crashing (the depth cap rejects beyond kMaxCompoundDepth=16).
TEST(Trigger, CompoundDeepNestingDoesNotCrash) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "statement.written", "s1", "default"};
    // Build {"all_of":[{"kind":"compound","spec": <inner> }]} nested 50 deep,
    // with a satisfiable time leaf at the bottom. Beyond the cap it's a non-match.
    std::string leaf = R"({"kind":"time","spec":{"at":"2026-05-30T11:00:00Z"}})";
    std::string spec = leaf;
    for (int i = 0; i < 50; ++i)
        spec = R"({"kind":"compound","spec":{"all_of":[)" + spec + "]}}";
    // Outermost level is the compound spec body itself (strip the wrapping
    // {"kind":"compound","spec":...}).
    std::string outer = R"({"all_of":[)" + spec + "]}";
    EXPECT_FALSE(evaluate_trigger(c, "compound", outer, ctx));
}

// P2.c hardening (B#5): a compound child missing "spec" (or "kind") evaluates to
// a non-match and does not throw.
TEST(Trigger, CompoundMalformedChildDoesNotThrow) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "statement.written", "s1", "default"};
    // all_of with a child missing "spec" → the child is non-match → all_of false.
    EXPECT_NO_THROW({
        bool r = evaluate_trigger(c, "compound",
            R"({"all_of":[{"kind":"event"}]})", ctx);
        EXPECT_FALSE(r);
    });
    // any_of where the only satisfiable branch is malformed → false, no throw.
    EXPECT_NO_THROW({
        bool r = evaluate_trigger(c, "compound",
            R"({"any_of":[{"kind":"time"},{"spec":{"at":"2026-05-30T11:00:00Z"}}]})", ctx);
        EXPECT_FALSE(r);
    });
}
