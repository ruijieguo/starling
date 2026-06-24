// detect_faux_pas (SP-B) — re-based on per-event perception (what_does_X_think.is_stale).
// Seeds perception_state state-changes directly: a theme moves while one cast member is
// absent, so that party holds an OUTDATED (stale) view while the co-present members hold
// the current one. The operator must flag the stale party with the current ones as knowers.
#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <memory>
#include <string>

using starling::tom::mentalizing::detect_faux_pas;
using starling::cognizer::KnowledgeFrontier;

namespace {

std::unique_ptr<starling::persistence::SqliteAdapter> make_adapter() {
    auto a = starling::persistence::SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Upsert one perception_state row (a cognizer's perceived state of a theme at a position).
void seed_perc(starling::persistence::SqliteAdapter& a, const char* T, const char* cog,
               const char* theme, const char* value, const char* at, long long pos,
               const char* ev) {
    starling::store::PerceptionStateStore ps(a.connection());
    starling::store::PerceptionStateRow row;
    row.tenant_id = T; row.cognizer_id = cog; row.theme_id = theme;
    row.state_dim = "location"; row.state_value = value;
    row.observed_at = at; row.position = pos; row.source_event_id = ev;
    ps.upsert(row);
}

}  // namespace

TEST(DetectFauxPas, StaleViewAsymmetryEmitsCandidate) {
    auto a = make_adapter();
    const char* T = "t1";
    // initial: B (and A,C) saw ball at basket (pos 0)
    for (const char* c : {"A", "B", "C"})
        seed_perc(*a, T, c, "ball", "basket", "2026-05-26T08:00:00Z", 0, "e0");
    // move: A,C saw ball -> box (pos 1); B absent (no row), so B stays on basket.
    seed_perc(*a, T, "A", "ball", "box", "2026-05-26T09:00:00Z", 1, "e1");
    seed_perc(*a, T, "C", "ball", "box", "2026-05-26T09:00:00Z", 1, "e1");

    KnowledgeFrontier frontier(*a);
    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    ASSERT_EQ(cands.size(), 1u);
    EXPECT_EQ(cands[0].ignorant, "B");
    EXPECT_EQ(cands[0].theme, "ball");
    EXPECT_EQ(cands[0].state_dim, "location");
    EXPECT_EQ(cands[0].stale_value, "basket");
    EXPECT_EQ(cands[0].actual_value, "box");
    auto& wk = cands[0].who_knows;
    EXPECT_NE(std::find(wk.begin(), wk.end(), "A"), wk.end());
    EXPECT_NE(std::find(wk.begin(), wk.end(), "C"), wk.end());
}

TEST(DetectFauxPas, NoAsymmetryWhenAllCurrent) {
    auto a = make_adapter();
    const char* T = "t2";
    for (const char* c : {"A", "B"})
        seed_perc(*a, T, c, "ball", "box", "2026-05-26T09:00:00Z", 1, "e1");
    KnowledgeFrontier frontier(*a);
    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    EXPECT_TRUE(cands.empty());
}

TEST(DetectFauxPas, SingleCastMemberNoCandidate) {
    auto a = make_adapter();
    const char* T = "t3";
    seed_perc(*a, T, "A", "ball", "box", "2026-05-26T09:00:00Z", 1, "e1");
    KnowledgeFrontier frontier(*a);
    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    EXPECT_TRUE(cands.empty()) << "single-member cast -> no asymmetry possible";
}
