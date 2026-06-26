// test_mentalizing_common_knowledge: 5 ctest for is_common_knowledge operator.
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

using starling::tom::mentalizing::is_common_knowledge;

// All of A/B/C enter room1 and witness A's move ball->L. No later event.
static std::unique_ptr<starling::persistence::SqliteAdapter> scene_public(const char* T) {
    auto a = open_migrated();
    seed_event(*a, T, "e1", "A", "enter", "room1", "", R"(["A"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "e2", "B", "enter", "room1", "", R"(["B"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "e3", "C", "enter", "room1", "", R"(["C"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "m1", "A", "move",  "ball",  "L", R"(["A"])", 4, "2026-01-01T00:00:04Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    return a;
}

TEST(IsCommonKnowledge, PublicEstablishmentIsCK) {
    auto a = scene_public("ck1");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", "ck1", "2026-01-02T00:00:00Z");
    EXPECT_TRUE(r.is_ck);
    EXPECT_EQ(r.ck_value, "L");
}

TEST(IsCommonKnowledge, PrivateTellBreaksCK) {
    // Public L1 to all, then D privately tells A ball->L2 (only A learns it).
    auto a = scene_public("ck2");
    seed_event(*a, "ck2", "t1", "D", "tell", "ball", "L2", R"(["D","A"])", 5, "2026-01-01T00:00:05Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct("ck2");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", "ck2", "2026-01-02T00:00:00Z");
    EXPECT_FALSE(r.is_ck);             // A's latest (L2) is not co-witnessed by B/C
    EXPECT_EQ(r.ck_value, "L");        // last all-co-witnessed value
}

TEST(IsCommonKnowledge, SubsetMoveBreaksCK) {
    // Public L1; A leaves; B moves ball->L2 (A does not see it).
    auto a = scene_public("ck3");
    seed_event(*a, "ck3", "l1", "A", "leave", "room1", "",  R"(["A"])", 5, "2026-01-01T00:00:05Z");
    seed_event(*a, "ck3", "m2", "B", "move",  "ball",  "L2", R"(["B"])", 6, "2026-01-01T00:00:06Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct("ck3");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", "ck3", "2026-01-02T00:00:00Z");
    EXPECT_FALSE(r.is_ck);             // B/C's latest (L2) not witnessed by A
}

TEST(IsCommonKnowledge, NonGroupPrivateMoveDoesNotBreakGroupCK) {
    // A/B/C/D all see ball@L1; A/B/C leave; D moves ball->L2 (only D, not in queried G).
    auto a = open_migrated();
    const char* T = "ck4";
    seed_event(*a, T, "e1", "A", "enter", "room1", "", R"(["A"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "e2", "B", "enter", "room1", "", R"(["B"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "e3", "C", "enter", "room1", "", R"(["C"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "e4", "D", "enter", "room1", "", R"(["D"])", 4, "2026-01-01T00:00:04Z");
    seed_event(*a, T, "m1", "A", "move",  "ball",  "L1", R"(["A"])", 5, "2026-01-01T00:00:05Z");
    seed_event(*a, T, "l1", "A", "leave", "room1", "",   R"(["A"])", 6, "2026-01-01T00:00:06Z");
    seed_event(*a, T, "l2", "B", "leave", "room1", "",   R"(["B"])", 7, "2026-01-01T00:00:07Z");
    seed_event(*a, T, "l3", "C", "leave", "room1", "",   R"(["C"])", 8, "2026-01-01T00:00:08Z");
    seed_event(*a, T, "m2", "D", "move",  "ball",  "L2", R"(["D"])", 9, "2026-01-01T00:00:09Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", T, "2026-01-02T00:00:00Z");
    EXPECT_TRUE(r.is_ck);             // among {A,B,C}, latest co-witnessed is L1; D's L2 is outside G
    EXPECT_EQ(r.ck_value, "L1");
}

TEST(IsCommonKnowledge, SingletonGroupKnows) {
    auto a = scene_public("ck5");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A"}, "ball", "ck5", "2026-01-02T00:00:00Z");
    EXPECT_TRUE(r.is_ck);
    EXPECT_EQ(r.ck_value, "L");
}
