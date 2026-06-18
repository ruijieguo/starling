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
