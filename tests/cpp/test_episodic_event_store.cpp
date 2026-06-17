// sub-project A phase 2:episodic_events 表(0025)+ EpisodicEventStore 单属主。
// fixtures 直接 SQL 种 statements 行(modality='occurred'),镜像 statement_store 测试。
#include "starling/store/episodic_event_store.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <cstdio>
#include <memory>
#include <string>

namespace starling::store {
namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// 种一条 modality='occurred' 的 statements 行,object_value=theme(主题)。
// 30 列布局镜像 tests/cpp/test_tom_second_order.cpp 的 statements INSERT。
void seed_occurred(persistence::Connection& conn, const std::string& id,
                   const std::string& theme,
                   const std::string& observed = "2026-06-12T09:00:00Z") {
    const std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES('" + id +
        "','default','cog-self','FIRST_PERSON','entity','agent','moved','str','" +
        theme + "','h-" + id + "','v1','occurred','POS',0.9,'" + observed +
        "',0.5,'{}',0.0,'" + observed +
        "','user_input','[{\"engram_id\":\"eng-" + id +
        "\"}]','consolidated','approved',0,'" + observed + "','" + observed + "')";
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql.c_str(), nullptr, nullptr, &err),
              SQLITE_OK)
        << (err ? err : "");
}

bool table_exists(persistence::Connection& conn, const char* name) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", -1, &s,
        nullptr);
    sqlite3_bind_text(s, 1, name, -1, SQLITE_TRANSIENT);
    const bool found = sqlite3_step(s) == SQLITE_ROW;
    sqlite3_finalize(s);
    return found;
}

}  // namespace

// Task 2.1:迁移 0025 建表。
TEST(EpisodicEventStore, MigrationCreatesTable) {
    auto a = make_adapter();
    EXPECT_TRUE(table_exists(a->connection(), "episodic_events"));
}

// Task 2.2(a):upsert → get 全字段往返。
TEST(EpisodicEventStore, UpsertGetRoundTrip) {
    auto a = make_adapter();
    seed_occurred(a->connection(), "stmt-1", "ball");
    EpisodicEventStore store(a->connection());

    EpisodicEventRow row;
    row.statement_id = "stmt-1";
    row.tenant_id = "default";
    row.seq = 7;
    row.event_time = "2026-06-12T10:30:00Z";
    row.location = "basket";
    row.participants_json = R"(["alice","bob"])";
    row.action_raw = "moved";
    store.upsert(row);

    auto got = store.get("stmt-1", "default");
    ASSERT_TRUE(got.has_value());
    EXPECT_EQ(got->statement_id, "stmt-1");
    EXPECT_EQ(got->tenant_id, "default");
    EXPECT_EQ(got->seq, 7);
    EXPECT_EQ(got->event_time, "2026-06-12T10:30:00Z");
    EXPECT_EQ(got->location, "basket");
    EXPECT_EQ(got->participants_json, R"(["alice","bob"])");
    EXPECT_EQ(got->action_raw, "moved");
}

// upsert 二次写同主键覆盖(NULL 字段经空串往返)。
TEST(EpisodicEventStore, UpsertOverwritesAndNullRoundTrips) {
    auto a = make_adapter();
    seed_occurred(a->connection(), "stmt-1", "ball");
    EpisodicEventStore store(a->connection());

    EpisodicEventRow row;
    row.statement_id = "stmt-1";
    row.tenant_id = "default";
    row.seq = 1;
    store.upsert(row);  // event_time/location/action_raw 全空 → NULL

    row.seq = 2;
    row.location = "box";
    store.upsert(row);  // 覆盖

    auto got = store.get("stmt-1", "default");
    ASSERT_TRUE(got.has_value());
    EXPECT_EQ(got->seq, 2);
    EXPECT_EQ(got->location, "box");
    EXPECT_EQ(got->event_time, "");      // NULL → ""
    EXPECT_EQ(got->action_raw, "");      // NULL → ""
    EXPECT_EQ(got->participants_json, "[]");

    // missing 行返回 nullopt。
    EXPECT_FALSE(store.get("nope", "default").has_value());
}

// Task 2.2(b):两条 OCCURRED 主题 "ball" 事件,events_for_theme 按 seq 返回二者。
// Task 2.2(c):latest_event_location 取最高 seq 的 location。
TEST(EpisodicEventStore, EventsForThemeOrderedAndLatestLocation) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_occurred(conn, "stmt-1", "ball", "2026-06-12T09:00:00Z");
    seed_occurred(conn, "stmt-2", "ball", "2026-06-12T11:00:00Z");
    // 一条无关主题,不应出现在 ball 结果里。
    seed_occurred(conn, "stmt-x", "cup", "2026-06-12T09:30:00Z");

    EpisodicEventStore store(conn);
    EpisodicEventRow r1;
    r1.statement_id = "stmt-1";
    r1.tenant_id = "default";
    r1.seq = 1;
    r1.event_time = "2026-06-12T09:00:00Z";
    r1.location = "basket";
    store.upsert(r1);

    EpisodicEventRow r2;
    r2.statement_id = "stmt-2";
    r2.tenant_id = "default";
    r2.seq = 2;
    r2.event_time = "2026-06-12T11:00:00Z";
    r2.location = "box";
    store.upsert(r2);

    EpisodicEventRow rx;
    rx.statement_id = "stmt-x";
    rx.tenant_id = "default";
    rx.seq = 5;
    rx.location = "shelf";
    store.upsert(rx);

    auto events = store.events_for_theme("default", "ball");
    ASSERT_EQ(events.size(), 2u);
    EXPECT_EQ(events[0].statement_id, "stmt-1");
    EXPECT_EQ(events[0].seq, 1);
    EXPECT_EQ(events[0].location, "basket");
    EXPECT_EQ(events[1].statement_id, "stmt-2");
    EXPECT_EQ(events[1].seq, 2);
    EXPECT_EQ(events[1].location, "box");

    EXPECT_EQ(store.latest_event_location("default", "ball"), "box");
    EXPECT_EQ(store.latest_event_location("default", "cup"), "shelf");
    EXPECT_EQ(store.latest_event_location("default", "absent"), "");
}

}  // namespace starling::store
