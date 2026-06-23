// what_does_X_think_chain: arbitrary multi-order perception ToM (generalizes the
// order-2 observer intersection in test_mentalizing_think.cpp).
#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/store/episodic_event_store.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <memory>
#include <string>
#include <vector>

namespace {

std::unique_ptr<starling::persistence::SqliteAdapter> open_migrated() {
    auto a = starling::persistence::SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Same seed helper as test_perception_reconstructor.cpp: one OCCURRED statements
// row + one episodic_events row.
void seed_event(starling::persistence::SqliteAdapter& a, const char* tenant,
                const char* stmt_id, const char* actor, const char* action,
                const char* theme, const char* location, const char* participants_json,
                long long seq, const char* observed_at) {
    auto& conn = a.connection();
    const std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES('" + std::string(stmt_id) +
        "','" + tenant + "','cog-self','FIRST_PERSON','cognizer','" + actor +
        "','" + action + "','entity','" + theme + "','h-" + stmt_id +
        "','v1','occurred','POS',0.9,'" + observed_at +
        "',0.5,'{}',0.0,'" + observed_at +
        "','user_input','[{\"engram_id\":\"eng-" + stmt_id +
        "\"}]','consolidated','approved',0,'" + observed_at + "','" + observed_at + "')";
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql.c_str(), nullptr, nullptr, &err),
              SQLITE_OK)
        << (err ? err : "");

    starling::store::EpisodicEventStore ep(conn);
    starling::store::EpisodicEventRow row;
    row.statement_id = stmt_id;
    row.tenant_id = tenant;
    row.seq = seq;
    row.location = location;
    row.participants_json = participants_json;
    row.action_raw = action;
    ep.upsert(row);
}

}  // namespace

using starling::tom::mentalizing::what_does_X_think;
using starling::tom::mentalizing::what_does_X_think_chain;

// Build the standard 3-cognizer scene: all enter the cast; initial find ball@A
// (participants=[] -> witnessed by all present); c3 leaves; c2 moves ball->B; c1 also
// gets a leave so the cast includes it.
static std::unique_ptr<starling::persistence::SqliteAdapter> scene_early_leave(const char* T) {
    auto a = open_migrated();
    seed_event(*a, T, "h0", "c1", "find",  "ball", "A", R"([])",     1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "h1", "c3", "leave", "room", "",  R"(["c3"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "h2", "c2", "move",  "ball", "B", R"(["c2"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "h3", "c1", "leave", "room", "",  R"(["c1"])", 4, "2026-01-01T00:00:04Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    return a;
}

TEST(WhatDoesXThinkChain, OrderOneEqualsFirstOrder) {
    auto a = scene_early_leave("tc1");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto chain = what_does_X_think_chain(*a, f, {"c2"}, "ball", "tc1", AS);
    auto first = what_does_X_think(*a, f, "c2", "ball", "tc1", AS, "");
    EXPECT_EQ(chain.has_belief, first.has_belief);
    EXPECT_EQ(chain.state_value, first.state_value);
    EXPECT_EQ(chain.state_value, "B");
}

TEST(WhatDoesXThinkChain, OrderTwoEqualsObserverBranch) {
    auto a = scene_early_leave("tc2");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto chain = what_does_X_think_chain(*a, f, {"c1", "c2"}, "ball", "tc2", AS);
    auto obs = what_does_X_think(*a, f, "c2", "ball", "tc2", AS, "c1");
    EXPECT_EQ(chain.has_belief, obs.has_belief);
    EXPECT_EQ(chain.state_value, obs.state_value);
}

TEST(WhatDoesXThinkChain, OrderThreeEarlyLeaverReturnsInitial) {
    auto a = scene_early_leave("tc3");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto r = what_does_X_think_chain(*a, f, {"c1", "c2", "c3"}, "ball", "tc3", AS);
    EXPECT_TRUE(r.has_belief);
    EXPECT_EQ(r.state_value, "A") << "c3 only ever saw the initial A; all co-saw it";
}

TEST(WhatDoesXThinkChain, OrderThreeAllPresentReturnsMoved) {
    auto a = open_migrated();
    const char* T = "tc3b";
    seed_event(*a, T, "j0", "c1", "find", "ball", "A", R"([])",     1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "j1", "c2", "move", "ball", "B", R"(["c2"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "j2", "c3", "leave", "room", "", R"(["c3"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "j3", "c1", "leave", "room", "", R"(["c1"])", 4, "2026-01-01T00:00:04Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto r = what_does_X_think_chain(*a, f, {"c1", "c2", "c3"}, "ball", T, AS);
    EXPECT_TRUE(r.has_belief);
    EXPECT_EQ(r.state_value, "B") << "all three present through the move -> B";
}

TEST(WhatDoesXThinkChain, OrderFour) {
    auto a = open_migrated();
    const char* T = "tc4";
    seed_event(*a, T, "k0", "c1", "find",  "ball", "A", R"([])",     1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "k1", "c4", "leave", "room", "", R"(["c4"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "k2", "c2", "move",  "ball", "B", R"(["c2"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "k3", "c3", "leave", "room", "", R"(["c3"])", 4, "2026-01-01T00:00:04Z");
    seed_event(*a, T, "k4", "c1", "leave", "room", "", R"(["c1"])", 5, "2026-01-01T00:00:05Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto r = what_does_X_think_chain(*a, f, {"c1", "c2", "c3", "c4"}, "ball", T, AS);
    EXPECT_TRUE(r.has_belief);
    EXPECT_EQ(r.state_value, "A") << "c4 left first; common-witnessed event is the initial A";
}

TEST(WhatDoesXThinkChain, EmptyChainAndUnknownCognizer) {
    auto a = scene_early_leave("tc5");
    starling::cognizer::KnowledgeFrontier f(*a);
    const char* AS = "2026-01-02T00:00:00Z";
    auto empty = what_does_X_think_chain(*a, f, {}, "ball", "tc5", AS);
    EXPECT_FALSE(empty.has_belief);
    auto unknown = what_does_X_think_chain(*a, f, {"c1", "nobody"}, "ball", "tc5", AS);
    EXPECT_FALSE(unknown.has_belief) << "deepest cognizer never perceived the theme";
}
