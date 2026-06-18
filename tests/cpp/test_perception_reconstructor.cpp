// sub-project B phase 1 Task 1.2: PerceptionReconstructor —— 扫描租户全部 OCCURRED
// 事件,重建场景级在场时间线,按物理见证者把结果 location 写入 perception_state。
// seed_event 直接种 statements(modality='occurred')行(镜像 test_episodic_event_store.cpp
// 的 seed_occurred 26 列布局)+ EpisodicEventStore::upsert 一条 episodic_events 行。
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/store/episodic_event_store.hpp"
#include "starling/store/perception_state_store.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using starling::cognizer::PerceptionReconstructor;
using starling::store::PerceptionStateStore;

namespace {

std::unique_ptr<starling::persistence::SqliteAdapter> open_migrated() {
    auto a = starling::persistence::SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Seed an OCCURRED event = one statements row (modality='occurred', subject_id=actor,
// predicate=action, object_value=theme, observed_at) + one episodic_events row
// (seq, location, participants_json) via EpisodicEventStore::upsert. The 26-column
// statements INSERT mirrors seed_occurred in tests/cpp/test_episodic_event_store.cpp.
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
    row.location = location;                  // "" → NULL
    row.participants_json = participants_json;
    row.action_raw = action;
    ep.upsert(row);
}

}  // namespace

// Issue 3: double-reconstruct must produce identical results (idempotent upserts,
// no duplicate rows).
TEST(PerceptionReconstructor, IdempotentDoubleReconstruct) {
    auto a = open_migrated();
    const char* T = "t-idem";
    // Same Sally-Anne seeding as the main test.
    seed_event(*a, T, "i0", "Sally", "put",  "ball", "basket", R"(["Sally"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "i1", "Sally", "leave", "room", "",       R"(["Sally"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "i2", "Anne",  "move", "ball", "box",    R"(["Anne"])",  3, "2026-01-01T00:00:03Z");

    PerceptionReconstructor recon(a->connection());
    const char* AS_OF = "2026-01-02T00:00:00Z";

    // First reconstruct.
    recon.reconstruct(T);
    PerceptionStateStore ps(a->connection());
    auto sally1 = ps.last_known(T, "Sally", "ball", "location", AS_OF);
    auto anne1  = ps.last_known(T, "Anne",  "ball", "location", AS_OF);
    ASSERT_TRUE(sally1.has_value());
    ASSERT_TRUE(anne1.has_value());
    EXPECT_EQ(sally1->state_value, "basket");
    EXPECT_EQ(anne1->state_value,  "box");
    auto rows_after_1st = ps.perceived_for_theme(T, "Anne", "ball", AS_OF);

    // Second reconstruct — must produce identical last_known, no extra rows.
    recon.reconstruct(T);
    auto sally2 = ps.last_known(T, "Sally", "ball", "location", AS_OF);
    auto anne2  = ps.last_known(T, "Anne",  "ball", "location", AS_OF);
    ASSERT_TRUE(sally2.has_value());
    ASSERT_TRUE(anne2.has_value());
    EXPECT_EQ(sally2->state_value, "basket");
    EXPECT_EQ(anne2->state_value,  "box");
    auto rows_after_2nd = ps.perceived_for_theme(T, "Anne", "ball", AS_OF);

    // No duplicate rows: same count after both runs.
    EXPECT_EQ(rows_after_1st.size(), rows_after_2nd.size())
        << "double reconstruct must not insert duplicate perception_state rows";
}

TEST(PerceptionReconstructor, SallyAnneLocationPresence) {
    auto a = open_migrated();
    const char* T = "t1";
    seed_event(*a, T, "e0", "Sally", "put",  "ball", "basket", R"(["Sally"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "e1", "Sally", "leave", "room", "",       R"(["Sally"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "e2", "Anne",  "move", "ball", "box",    R"(["Anne"])",  3, "2026-01-01T00:00:03Z");

    PerceptionReconstructor recon(a->connection());
    recon.reconstruct(T);

    PerceptionStateStore ps(a->connection());
    const char* AS_OF = "2026-01-02T00:00:00Z";
    // Sally saw the put (default-present) but LEFT before the move → basket.
    auto sally = ps.last_known(T, "Sally", "ball", "location", AS_OF);
    ASSERT_TRUE(sally.has_value());
    EXPECT_EQ(sally->state_value, "basket");
    // Anne was present throughout → box (and earlier basket, but box is later).
    auto anne = ps.last_known(T, "Anne", "ball", "location", AS_OF);
    ASSERT_TRUE(anne.has_value());
    EXPECT_EQ(anne->state_value, "box");
}

// Task 2.2: told channel.
// Carol tells Dave the ball is in the box. Dave is named ONLY in the tell —
// he must (a) learn the told state (last_known=box) and (b) NOT be credited
// as a physical witness of the put/move events (exactly 1 perception row).
// A purely-absent outsider (Eve) has no perception row at all.
TEST(PerceptionReconstructor, ToldChannelRecipientLearnsStateNotPhysicalWitness) {
    auto a = open_migrated();
    const char* T = "t-tell";
    // Physical events: Sally puts ball in basket, Anne moves it to box.
    seed_event(*a, T, "f0", "Sally", "put",  "ball", "basket", R"(["Sally"])",        1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "f1", "Anne",  "move", "ball", "box",    R"(["Anne"])",         2, "2026-01-01T00:00:02Z");
    // Tell event: Carol (actor) tells Dave (recipient) the ball is in the box.
    // Dave appears ONLY in this tell — never in a physical event.
    seed_event(*a, T, "f2", "Carol", "tell", "ball", "box",    R"(["Carol","Dave"])", 3, "2026-01-01T00:00:03Z");

    PerceptionReconstructor recon(a->connection());
    recon.reconstruct(T);

    PerceptionStateStore ps(a->connection());
    const char* AS_OF = "2026-01-02T00:00:00Z";

    // Dave was told ball is in box → last_known = box.
    auto dave = ps.last_known(T, "Dave", "ball", "location", AS_OF);
    ASSERT_TRUE(dave.has_value()) << "Dave should know about the ball via tell";
    EXPECT_EQ(dave->state_value, "box");

    // Dave must NOT be a physical witness of f0/f1 — he has exactly ONE perception row
    // (from the tell, source_event_id = "f2"), not three.
    auto dave_rows = ps.perceived_for_theme(T, "Dave", "ball", AS_OF);
    EXPECT_EQ(dave_rows.size(), 1u)
        << "Dave should have exactly 1 perception row (the tell), not rows for put/move";
    if (!dave_rows.empty()) {
        EXPECT_EQ(dave_rows[0].source_event_id, "f2")
            << "Dave's perception row must come from the tell event";
    }

    // A purely-absent outsider (Eve) has no perception row at all.
    auto eve = ps.last_known(T, "Eve", "ball", "location", AS_OF);
    EXPECT_FALSE(eve.has_value()) << "Eve was never in a physical event or tell — no perception";
}

// Phase 4: Unexpected contents (apparent vs actual).
// A closed labelled "Smarties tube" really holds pencils.
//   c0 Anne see   Smarties tube → "Smarties"  (APPARENT content from the label)
//   c1 Anne leave room                          (Anne departs before the reveal)
//   c2 Tom  open  Smarties tube → "pencils"    (ACTUAL content on opening)
// Both see and open write state_dim="content" (NOT "location") to the present
// witnesses. see/open actors ARE physically present (unlike tell), so each is a
// witness of their own event. Anne left before the open → her last content
// perception stays "Smarties"; Tom (present, the opener) learns "pencils".
TEST(PerceptionReconstructor, UnexpectedContentsSeeApparentOpenActual) {
    auto a = open_migrated();
    const char* T = "t-content";
    seed_event(*a, T, "c0", "Anne", "see",   "Smarties tube", "Smarties", R"(["Anne"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "c1", "Anne", "leave", "room",          "",         R"(["Anne"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "c2", "Tom",  "open",  "Smarties tube", "pencils",  R"(["Tom"])",  3, "2026-01-01T00:00:03Z");

    PerceptionReconstructor recon(a->connection());
    recon.reconstruct(T);

    PerceptionStateStore ps(a->connection());
    const char* AS_OF = "2026-01-02T00:00:00Z";

    // Anne saw the closed tube → apparent content "Smarties" (state_dim="content").
    auto anne = ps.last_known(T, "Anne", "Smarties tube", "content", AS_OF);
    ASSERT_TRUE(anne.has_value()) << "Anne's see must write a content perception";
    EXPECT_EQ(anne->state_value, "Smarties");
    // The see must NOT write a location row (content events are content-dim only).
    auto anne_loc = ps.last_known(T, "Anne", "Smarties tube", "location", AS_OF);
    EXPECT_FALSE(anne_loc.has_value()) << "see/open must write content, not location";

    // Tom opened the tube → actual content "pencils".
    auto tom = ps.last_known(T, "Tom", "Smarties tube", "content", AS_OF);
    ASSERT_TRUE(tom.has_value()) << "Tom's open must write a content perception";
    EXPECT_EQ(tom->state_value, "pencils");

    // Anne left before the open, so her last content perception is still Smarties
    // (she is NOT a default-present witness of Tom's open).
    EXPECT_EQ(anne->state_value, "Smarties")
        << "Anne's last content perception must remain the apparent Smarties";
}

// Phase 4 / code-review fix: close events must NOT write any perception row.
// close is in kActionPredicates but matched no B branch, so a close carrying a
// non-empty location fell through to the physical-location branch and wrote a
// spurious state_dim="location" row on a content-typed container.
//
// Scenario:
//   d0 Anne see   tube → "Smarties" (seq 1) — Anne learns apparent content
//   d1 Anne leave room               (seq 2) — Anne departs
//   d2 Tom  open  tube → "pencils"  (seq 3) — Tom learns actual content (Anne absent)
//   d3 Tom  close tube, location="shelf" (seq 4) — resting-place annotation on the
//                                                   close event; must write NO
//                                                   perception for any witness.
TEST(PerceptionReconstructor, CloseEventWritesNoPerception) {
    auto a = open_migrated();
    const char* T = "t-close";
    seed_event(*a, T, "d0", "Anne", "see",   "tube", "Smarties", R"(["Anne"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "d1", "Anne", "leave", "room", "",         R"(["Anne"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "d2", "Tom",  "open",  "tube", "pencils",  R"(["Tom"])",  3, "2026-01-01T00:00:03Z");
    // close carries a non-empty location ("shelf") — the bug caused this to write
    // a spurious state_dim="location" row for all present witnesses (Tom, here).
    seed_event(*a, T, "d3", "Tom",  "close", "tube", "shelf",    R"(["Tom"])",  4, "2026-01-01T00:00:04Z");

    PerceptionReconstructor recon(a->connection());
    recon.reconstruct(T);

    PerceptionStateStore ps(a->connection());
    const char* AS_OF = "2026-01-02T00:00:00Z";

    // --- close must NOT write a spurious location row ---
    auto tom_loc = ps.last_known(T, "Tom", "tube", "location", AS_OF);
    EXPECT_FALSE(tom_loc.has_value())
        << "close must NOT write a location perception row (spurious location bug)";
    auto anne_loc = ps.last_known(T, "Anne", "tube", "location", AS_OF);
    EXPECT_FALSE(anne_loc.has_value())
        << "close must NOT write a location perception row for Anne either";

    // --- prior content perceptions remain intact ---
    auto anne_content = ps.last_known(T, "Anne", "tube", "content", AS_OF);
    ASSERT_TRUE(anne_content.has_value()) << "Anne's see must write a content perception";
    EXPECT_EQ(anne_content->state_value, "Smarties");

    auto tom_content = ps.last_known(T, "Tom", "tube", "content", AS_OF);
    ASSERT_TRUE(tom_content.has_value()) << "Tom's open must write a content perception";
    EXPECT_EQ(tom_content->state_value, "pencils");
}
