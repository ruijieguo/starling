#include "starling/replay/replay_scheduler.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>
#include <vector>

using namespace starling::replay;
using starling::persistence::SqliteAdapter;

namespace {

// ── Seed helpers ────────────────────────────────────────────────────────────

void seed_volatile(sqlite3* db, const std::string& id,
                   const std::string& created_at,
                   double salience = 0.8,
                   int replay_count = 0,
                   const std::string& provenance = "user_input",
                   const std::string& tenant = "default") {
    std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,consolidation_state,review_status,replay_count,"
        "created_at,updated_at) VALUES('" + id + "','" + tenant + "','alice','first_person',"
        "'cognizer','bob','knows','str','x','" + std::string(64,'a') + "','v1',"
        "'assumes','pos',0.9,'2025-01-01T00:00:00Z'," + std::to_string(salience) +
        ",'{}',0.0,'" + created_at + "','" + provenance + "',"
        "'volatile','approved'," + std::to_string(replay_count) +
        ",'" + created_at + "','" + created_at + "')";
    sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr);
}

void seed_consolidated(sqlite3* db, const std::string& id,
                       const std::string& last_accessed,
                       double salience = 0.0,
                       const std::string& tenant = "default") {
    std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,consolidation_state,review_status,replay_count,"
        "created_at,updated_at) VALUES('" + id + "','" + tenant + "','alice','first_person',"
        "'cognizer','bob','knows','str','x','" + std::string(64,'a') + "','v1',"
        "'assumes','pos',0.9,'2025-01-01T00:00:00Z'," + std::to_string(salience) +
        ",'{}',0.0,'" + last_accessed + "','user_input',"
        "'consolidated','approved',0,"
        "'2025-01-01T00:00:00Z','2025-01-01T00:00:00Z')";
    sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr);
}

int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    std::string v;
    const auto* t = sqlite3_column_text(s, 0);
    if (t) v = reinterpret_cast<const char*>(t);
    sqlite3_finalize(s);
    return v;
}

}  // namespace

// ── Test 1: enforce_oscillation_guard → replay_count=5 becomes consolidated+pending_review ──

TEST(ReplayScheduler, OscillationGuard_HighReplayCount_Forced) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    // Seed a VOLATILE stmt with replay_count=5
    seed_volatile(c.raw(), "stmt1", "2026-05-01T00:00:00Z", 0.8, 5);

    ReplayScheduler sched(*a);
    const int count = sched.enforce_oscillation_guard(c);
    EXPECT_EQ(count, 1);

    EXPECT_EQ(scol(c.raw(),
        "SELECT consolidation_state FROM statements WHERE id='stmt1'"),
        "consolidated");
    EXPECT_EQ(scol(c.raw(),
        "SELECT review_status FROM statements WHERE id='stmt1'"),
        "pending_review");
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='statement.consolidation_forced' AND primary_id='stmt1'"),
        1);
}

// ── Test 2: enforce_oscillation_guard → replay_count=4 → unchanged ──

TEST(ReplayScheduler, OscillationGuard_LowReplayCount_Unchanged) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_volatile(c.raw(), "stmt2", "2026-05-01T00:00:00Z", 0.8, 4);

    ReplayScheduler sched(*a);
    const int count = sched.enforce_oscillation_guard(c);
    EXPECT_EQ(count, 0);

    EXPECT_EQ(scol(c.raw(),
        "SELECT consolidation_state FROM statements WHERE id='stmt2'"),
        "volatile");
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='statement.consolidation_forced'"),
        0);
}

// ── Test 3: sweep_volatile_ttl → old stmt archived, recent unchanged ──

TEST(ReplayScheduler, SweepVolatileTTL_OldArchived_RecentUnchanged) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();

    // created_at 8 days before now=2026-05-27
    seed_volatile(c.raw(), "old_stmt", "2026-05-19T00:00:00Z", 0.8, 0);
    // created_at 2 days before now
    seed_volatile(c.raw(), "new_stmt", "2026-05-25T00:00:00Z", 0.8, 0);

    ReplayScheduler sched(*a);
    const int count = sched.sweep_volatile_ttl(c, "2026-05-27T00:00:00Z");
    EXPECT_EQ(count, 1);

    EXPECT_EQ(scol(c.raw(),
        "SELECT consolidation_state FROM statements WHERE id='old_stmt'"),
        "archived");
    EXPECT_EQ(scol(c.raw(),
        "SELECT consolidation_state FROM statements WHERE id='new_stmt'"),
        "volatile");
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='statement.archived' AND primary_id='old_stmt'"),
        1);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='statement.archived' AND primary_id='new_stmt'"),
        0);
}

// ── Test 4: tick_online counter increments, sampling on 3rd call ──

TEST(ReplayScheduler, TickOnline_SamplingOnThirdCall) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();

    // Seed 3 volatile stmts so sampling has material
    seed_volatile(c.raw(), "v1", "2026-05-27T00:00:00Z", 0.9, 0);
    seed_volatile(c.raw(), "v2", "2026-05-27T00:00:00Z", 0.8, 0);
    seed_volatile(c.raw(), "v3", "2026-05-27T00:00:00Z", 0.7, 0);

    ReplayScheduler sched(*a);

    // Call 1: counter=1, no sampling
    auto stats1 = sched.tick_online(c, "2026-05-27T10:00:00Z");
    EXPECT_EQ(stats1.sampled, 0);
    EXPECT_TRUE(stats1.replay_batch_id.empty());
    EXPECT_EQ(icol(c.raw(),
        "SELECT online_trigger_counter FROM replay_scheduler_state WHERE id=1"),
        1);

    // Call 2: counter=2, no sampling
    auto stats2 = sched.tick_online(c, "2026-05-27T10:00:01Z");
    EXPECT_EQ(stats2.sampled, 0);
    EXPECT_EQ(icol(c.raw(),
        "SELECT online_trigger_counter FROM replay_scheduler_state WHERE id=1"),
        2);

    // Call 3: counter reaches 3, sampling runs, counter resets to 0
    auto stats3 = sched.tick_online(c, "2026-05-27T10:00:02Z");
    EXPECT_GT(stats3.sampled, 0);
    EXPECT_FALSE(stats3.replay_batch_id.empty());
    EXPECT_EQ(icol(c.raw(),
        "SELECT online_trigger_counter FROM replay_scheduler_state WHERE id=1"),
        0);
    // A replay_ledger row should have been written
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM replay_ledger WHERE mode='online'"),
        1);
}

// ── Test 5: run_decay → consolidated old/low-salience stmt archived + event emitted ──
//           + duplicate candidate id only archived once

TEST(ReplayScheduler, RunDecay_ArchivesOldConsolidated) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();

    seed_consolidated(c.raw(), "old_cons", "2025-01-01T00:00:00Z", 0.0);

    ReplayScheduler sched(*a);
    // Pass duplicate id to test deduplication
    const int archived = sched.run_decay(c, {"old_cons", "old_cons"},
                                          "2026-05-27T00:00:00Z");
    EXPECT_EQ(archived, 1);

    EXPECT_EQ(scol(c.raw(),
        "SELECT consolidation_state FROM statements WHERE id='old_cons'"),
        "archived");
    // statement.archived event emitted exactly once
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='statement.archived' AND primary_id='old_cons'"),
        1);
}

TEST(ReplayScheduler, RunDecayHandlesSharedStmtIdAcrossTenants) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();

    seed_consolidated(c.raw(), "shared", "2025-01-01T00:00:00Z", 0.0, "tenant-a");
    seed_consolidated(c.raw(), "shared", "2025-01-01T00:00:00Z", 0.0, "tenant-b");

    ReplayScheduler sched(*a);
    const int archived = sched.run_decay(c, {"shared"},
                                         "2026-05-27T00:00:00Z");
    EXPECT_EQ(archived, 2);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM statements WHERE id='shared' "
        "AND consolidation_state='archived'"), 2);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' "
        "AND primary_id='shared'"), 2);
}

// ── Test 6: run_idle writes a replay_ledger row with mode='idle' ──

TEST(ReplayScheduler, RunIdle_WritesLedger) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();

    seed_volatile(c.raw(), "vi1", "2026-05-27T00:00:00Z", 0.9, 0);

    ReplayScheduler sched(*a);
    auto stats = sched.run_idle(c, "2026-05-27T10:00:00Z");
    EXPECT_GT(stats.sampled, 0);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM replay_ledger WHERE mode='idle'"),
        1);
}

TEST(ReplayScheduler, RunIdleCompressesMixedTenantBatch) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();

    seed_volatile(c.raw(), "vi-a", "2026-05-27T00:00:00Z", 0.9, 0,
                  "user_input", "tenant-a");
    seed_volatile(c.raw(), "vi-b", "2026-05-27T00:00:00Z", 0.8, 0,
                  "user_input", "tenant-b");

    ReplayScheduler sched(*a);
    auto stats = sched.run_idle(c, "2026-05-27T10:00:00Z");

    EXPECT_EQ(stats.sampled, 2);
    EXPECT_EQ(stats.compressed, 2);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='consolidated'"),
        2);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.derived'"),
        2);
}
