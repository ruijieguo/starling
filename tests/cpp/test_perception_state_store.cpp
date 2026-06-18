// sub-project B phase 1 Task 1.1: perception_state 表(0026)+ PerceptionStateStore 单属主。
// 镜像 tests/cpp/test_episodic_event_store.cpp 的 in-memory adapter + 全迁移 helper。
#include "starling/store/perception_state_store.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <string>

using starling::store::PerceptionStateStore;
using starling::store::PerceptionStateRow;

namespace {

// Open an in-memory adapter with all migrations applied. Mirrors the helper at
// the top of tests/cpp/test_episodic_event_store.cpp (make_adapter()).
std::unique_ptr<starling::persistence::SqliteAdapter> open_migrated() {
    auto a = starling::persistence::SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

PerceptionStateRow mk(const char* cog, const char* theme, const char* dim,
                      const char* val, const char* obs, long long pos, const char* ev) {
    PerceptionStateRow r;
    r.tenant_id = "t1"; r.cognizer_id = cog; r.theme_id = theme;
    r.state_dim = dim; r.state_value = val; r.observed_at = obs;
    r.position = pos; r.source_event_id = ev;
    return r;
}

}  // namespace

TEST(PerceptionStateStore, LastKnownPicksHighestPositionWithinAsOf) {
    auto adapter = open_migrated();
    PerceptionStateStore store(adapter->connection());
    store.upsert(mk("Sally", "ball", "location", "basket", "2026-01-01T00:00:00Z", 0, "e0"));
    store.upsert(mk("Sally", "ball", "location", "box",    "2026-01-02T00:00:00Z", 2, "e2"));

    auto now = store.last_known("t1", "Sally", "ball", "location", "2026-01-03T00:00:00Z");
    ASSERT_TRUE(now.has_value());
    EXPECT_EQ(now->state_value, "box");          // highest position
    EXPECT_EQ(now->source_event_id, "e2");

    // as_of in the past excludes the later row.
    auto past = store.last_known("t1", "Sally", "ball", "location", "2026-01-01T12:00:00Z");
    ASSERT_TRUE(past.has_value());
    EXPECT_EQ(past->state_value, "basket");

    // unknown cognizer → nullopt.
    EXPECT_FALSE(store.last_known("t1", "Nobody", "ball", "location", "2026-01-03T00:00:00Z").has_value());
}

TEST(PerceptionStateStore, UpsertIsIdempotentOnCognizerSourceEvent) {
    auto adapter = open_migrated();
    PerceptionStateStore store(adapter->connection());
    store.upsert(mk("Sally", "ball", "location", "basket", "2026-01-01T00:00:00Z", 0, "e0"));
    store.upsert(mk("Sally", "ball", "location", "basket", "2026-01-01T00:00:00Z", 0, "e0"));  // re-run
    auto r = store.last_known("t1", "Sally", "ball", "location", "2026-01-03T00:00:00Z");
    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r->state_value, "basket");  // one row, not two; no error
}
