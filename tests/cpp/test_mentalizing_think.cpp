// sub-project B phase 1 Task 1.3: what_does_X_think —— 第 8 个 mentalizing 原语。
// 用 Task 1.2 的 seed_event + PerceptionReconstructor 把 ground-truth episodic_events
// (ball 终于 box)与 perception_state(Sally 见 basket、Anne 见 basket+box)一起种好,
// 再调 what_does_X_think 断言 has_belief / state_value / is_stale。
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

// Issue 1+2 regression: NULL-location event at latest seq must NOT zero out ground-truth,
// and ground truth must be bounded by as_of (historical query).
// Seed: put ball→basket at seq1 (observed_at T1), then take ball (empty location) at seq2 (T2).
// Ground truth = basket (latest NON-NULL located state).
// Also verify historical as_of before T2 still gives basket (not empty).
TEST(WhatDoesXThink, NullLocationAndAsOfBounded) {
    auto a = open_migrated();
    const char* T = "t-null";
    // seq1: Bob puts ball in basket (both Bob and Alice present)
    seed_event(*a, T, "n0", "Bob",  "put",  "ball", "basket",
               R"(["Bob","Alice"])", 1, "2026-01-01T00:00:01Z");
    // seq2: Bob takes ball (no resulting location — empty location like a take event)
    seed_event(*a, T, "n1", "Bob",  "take", "ball", "",
               R"(["Bob","Alice"])", 2, "2026-01-01T00:00:02Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);

    starling::cognizer::KnowledgeFrontier frontier(*a);

    // Both Bob and Alice saw basket (the only non-empty location event).
    // Ground truth must be basket (not "" from the take event).
    // A cognizer believing "basket" → is_stale=false.
    // A cognizer believing "box"    → is_stale=true.
    const char* AS_OF_AFTER = "2026-01-01T00:00:03Z";  // after both events

    auto alice = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Alice", "ball", T, AS_OF_AFTER);
    EXPECT_TRUE(alice.has_belief);
    EXPECT_EQ(alice.state_value, "basket");
    // Alice believes basket; ground truth = basket → NOT stale
    EXPECT_FALSE(alice.is_stale) << "basket==basket must not be stale";

    // Seed a separate cognizer that only ever heard 'box' to verify is_stale=true
    // when ground truth basket != belief box. We inject via direct upsert.
    {
        starling::store::PerceptionStateStore ps(a->connection());
        starling::store::PerceptionStateRow row;
        row.tenant_id = T; row.cognizer_id = "Charlie";
        row.theme_id = "ball"; row.state_dim = "location"; row.state_value = "box";
        row.observed_at = "2026-01-01T00:00:00Z"; row.position = 0;
        row.source_event_id = "fake-c0";
        ps.upsert(row);
    }
    auto charlie = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Charlie", "ball", T, AS_OF_AFTER);
    EXPECT_TRUE(charlie.has_belief);
    EXPECT_EQ(charlie.state_value, "box");
    // Ground truth = basket, Charlie believes box → IS stale
    EXPECT_TRUE(charlie.is_stale) << "box!=basket must be stale";

    // Historical as_of: before seq1, ground truth is "" → no perception_state rows.
    // Bob had no belief before the first event.
    const char* AS_OF_BEFORE = "2026-01-01T00:00:00Z";  // strictly before seq1
    auto bob_early = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Bob", "ball", T, AS_OF_BEFORE);
    EXPECT_FALSE(bob_early.has_belief) << "no perception before first event";
}

TEST(WhatDoesXThink, FirstOrderStaleAndFresh) {
    auto a = open_migrated();
    const char* T = "t1";
    // ground truth: ball ends in box (put@basket then move@box, like Task 1.2).
    // perception_state via reconstruct: Sally saw basket(left first), Anne saw box.
    seed_event(*a, T, "e0", "Sally", "put",  "ball", "basket", R"(["Sally"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "e1", "Sally", "leave", "room", "",       R"(["Sally"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "e2", "Anne",  "move", "ball", "box",    R"(["Anne"])",  3, "2026-01-01T00:00:03Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);

    starling::cognizer::KnowledgeFrontier frontier(*a);
    const char* AS_OF = "2026-01-02T00:00:00Z";

    auto sally = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Sally", "ball", T, AS_OF);
    EXPECT_TRUE(sally.has_belief);
    EXPECT_EQ(sally.state_value, "basket");
    EXPECT_TRUE(sally.is_stale);            // basket != ground-truth box

    auto anne = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Anne", "ball", T, AS_OF);
    EXPECT_TRUE(anne.has_belief);
    EXPECT_EQ(anne.state_value, "box");
    EXPECT_FALSE(anne.is_stale);

    auto nobody = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Charlie", "ball", T, AS_OF);
    EXPECT_FALSE(nobody.has_belief);        // never perceived → unknown
}

// Phase 3: Second-order via perception intersection.
// Sally-Anne setup (same 3 events):
//   e0 Sally put ball→basket (Sally present, Anne present)
//   e1 Sally leave room       (Sally departs)
//   e2 Anne  move ball→box    (Anne present only)
//
// Anne's model of Sally (observer=Anne, x=Sally):
//   Intersection of Anne's and Sally's perceived events for "ball".
//   Sally perceived: {e0=basket}.  Anne perceived: {e0=basket, e2=box}.
//   Intersection = {e0} → highest-position in intersection = basket.
//   → what_does_X_think(Sally, ball, observer=Anne) == "basket"
//
// Sally's model of Anne (observer=Sally, x=Anne):
//   Anne perceived: {e0=basket, e2=box}.  Sally perceived: {e0=basket}.
//   Intersection = {e0} → highest-position = basket.
//   → what_does_X_think(Anne, ball, observer=Sally) == "basket"
//   (Sally only co-saw the put with Anne; she left before the move.)
TEST(WhatDoesXThink, SecondOrderObserverIntersection) {
    auto a = open_migrated();
    const char* T = "t2";
    seed_event(*a, T, "f0", "Sally", "put",   "ball", "basket", R"(["Sally","Anne"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "f1", "Sally", "leave", "room", "",        R"(["Sally"])",        2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "f2", "Anne",  "move",  "ball", "box",     R"(["Anne"])",          3, "2026-01-01T00:00:03Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);

    starling::cognizer::KnowledgeFrontier frontier(*a);
    const char* AS_OF = "2026-01-02T00:00:00Z";

    // Anne's model of Sally: Anne co-perceived e0 (put→basket) with Sally;
    // Sally was gone for e2 (move→box). Intersection = {e0} → basket.
    auto sally_via_anne = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Sally", "ball", T, AS_OF, "Anne");
    EXPECT_TRUE(sally_via_anne.has_belief);
    EXPECT_EQ(sally_via_anne.state_value, "basket")
        << "Anne's model of Sally: only co-perceived e0=basket";

    // First-order Anne stays box (control: observer="" path unchanged).
    auto anne_first = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Anne", "ball", T, AS_OF);
    EXPECT_TRUE(anne_first.has_belief);
    EXPECT_EQ(anne_first.state_value, "box")
        << "First-order Anne must still return box";
    EXPECT_FALSE(anne_first.is_stale);

    // Sally's model of Anne: Sally only co-perceived e0 with Anne (not e2 which
    // occurred after Sally left). Intersection = {e0} → basket.
    auto anne_via_sally = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Anne", "ball", T, AS_OF, "Sally");
    EXPECT_TRUE(anne_via_sally.has_belief);
    EXPECT_EQ(anne_via_sally.state_value, "basket")
        << "Sally's model of Anne: only co-perceived e0=basket (Sally left before move)";
}

// Phase 4: Unexpected-contents false belief, with dim inference.
// A closed labelled "Smarties tube" really holds pencils:
//   c0 Anne see   Smarties tube → "Smarties" (apparent)
//   c1 Anne leave room                         (Anne departs before the reveal)
//   c2 Tom  open  Smarties tube → "pencils"   (actual; ground truth)
// what_does_X_think infers state_dim="content" (the theme has content rows) and
// uses latest_actual(...,"content",...) = "pencils" as ground truth.
//   Anne → content/Smarties, is_stale=true (Smarties != actual pencils)
//   Tom  → content/pencils,  is_stale=false (Tom opened it; he holds the truth)
TEST(WhatDoesXThink, UnexpectedContentsDimInferenceAndStale) {
    auto a = open_migrated();
    const char* T = "t-content";
    seed_event(*a, T, "c0", "Anne", "see",   "Smarties tube", "Smarties", R"(["Anne"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "c1", "Anne", "leave", "room",          "",         R"(["Anne"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "c2", "Tom",  "open",  "Smarties tube", "pencils",  R"(["Tom"])",  3, "2026-01-01T00:00:03Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);

    starling::cognizer::KnowledgeFrontier frontier(*a);
    const char* AS_OF = "2026-01-02T00:00:00Z";

    // Anne: apparent Smarties, dim inferred as content, stale vs actual pencils.
    auto anne = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Anne", "Smarties tube", T, AS_OF);
    EXPECT_TRUE(anne.has_belief);
    EXPECT_EQ(anne.state_dim, "content");
    EXPECT_EQ(anne.state_value, "Smarties");
    EXPECT_TRUE(anne.is_stale) << "Smarties != actual pencils → stale";

    // Tom: actual pencils, not stale (he opened it; ground truth == his belief).
    auto tom = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Tom", "Smarties tube", T, AS_OF);
    EXPECT_TRUE(tom.has_belief);
    EXPECT_EQ(tom.state_dim, "content");
    EXPECT_EQ(tom.state_value, "pencils");
    EXPECT_FALSE(tom.is_stale) << "Tom opened the tube → not stale";
}

// Phase 4 regression: a location-only theme must still infer state_dim="location"
// (dim inference returns "location" when no content rows exist). Sally-Anne ball.
TEST(WhatDoesXThink, LocationThemeStillInfersLocationDim) {
    auto a = open_migrated();
    const char* T = "t-loc-dim";
    seed_event(*a, T, "g0", "Sally", "put",  "ball", "basket", R"(["Sally"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "g1", "Sally", "leave", "room", "",       R"(["Sally"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "g2", "Anne",  "move", "ball", "box",    R"(["Anne"])",  3, "2026-01-01T00:00:03Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);

    starling::cognizer::KnowledgeFrontier frontier(*a);
    const char* AS_OF = "2026-01-02T00:00:00Z";

    auto sally = starling::tom::mentalizing::what_does_X_think(
        *a, frontier, "Sally", "ball", T, AS_OF);
    EXPECT_TRUE(sally.has_belief);
    EXPECT_EQ(sally.state_dim, "location") << "location-only theme must infer location dim";
    EXPECT_EQ(sally.state_value, "basket");
    EXPECT_TRUE(sally.is_stale);  // basket != ground-truth box
}
