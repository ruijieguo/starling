// test_common_ground_writer.cpp — CommonGroundWriter 5 Grounding Acts tests.
//
// TC-CGW-001  AssertCreatesAssertedUnack
// TC-CGW-002  AcknowledgeGrounds
// TC-CGW-003  RepairDiverges
// TC-CGW-004  WithdrawRecants
// TC-CGW-005  SupersedeSetsSupersededBy
// TC-CGW-006  TimeoutDowngrades

#include "starling/tom/common_ground_writer.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling::tom;
using starling::persistence::SqliteAdapter;

namespace {

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

// Read a single text column from a query.
std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const auto* txt = sqlite3_column_text(s, 0);
    std::string v = txt ? reinterpret_cast<const char*>(txt) : "";
    sqlite3_finalize(s);
    return v;
}

// Read a single int column from a query.
int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

}  // namespace

// ── TC-CGW-001: AssertCreatesAssertedUnack ────────────────────────────────────

TEST(CommonGroundWriter, AssertCreatesAssertedUnack) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);

    const std::string now = "2026-05-30T10:00:00Z";
    std::string cg_id = writer.assert_(conn, "default", "stmt-001",
                                       {"alice", "bob"}, now);

    EXPECT_FALSE(cg_id.empty());

    // common_ground row should exist with status asserted_unack
    std::string status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg_id + "'");
    EXPECT_EQ(status, "asserted_unack");

    // grounding_acts audit row should exist with act='assert'
    int act_count = icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts"
        " WHERE common_ground_id='" + cg_id + "' AND act='assert'");
    EXPECT_EQ(act_count, 1);
}

// ── TC-CGW-002: AcknowledgeGrounds ───────────────────────────────────────────

TEST(CommonGroundWriter, AcknowledgeGrounds) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);

    const std::string now1 = "2026-05-30T10:00:00Z";
    const std::string now2 = "2026-05-30T10:01:00Z";

    std::string cg_id = writer.assert_(conn, "default", "stmt-002", {}, now1);
    writer.acknowledge(conn, cg_id, "alice", now2);

    std::string status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg_id + "'");
    EXPECT_EQ(status, "grounded");

    std::string grounded_at = scol(conn.raw(),
        "SELECT grounded_at FROM common_ground WHERE id='" + cg_id + "'");
    EXPECT_EQ(grounded_at, now2);

    int act_count = icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts"
        " WHERE common_ground_id='" + cg_id + "' AND act='acknowledge'");
    EXPECT_EQ(act_count, 1);
}

// ── TC-CGW-003: RepairDiverges ────────────────────────────────────────────────

TEST(CommonGroundWriter, RepairDiverges) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);

    const std::string now1 = "2026-05-30T10:00:00Z";
    const std::string now2 = "2026-05-30T10:02:00Z";

    std::string cg_id = writer.assert_(conn, "default", "stmt-003", {}, now1);
    writer.repair(conn, cg_id, "bob", now2);

    std::string status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg_id + "'");
    EXPECT_EQ(status, "suspected_diverge");

    int act_count = icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts"
        " WHERE common_ground_id='" + cg_id + "' AND act='repair'");
    EXPECT_EQ(act_count, 1);
}

// ── TC-CGW-004: WithdrawRecants ───────────────────────────────────────────────

TEST(CommonGroundWriter, WithdrawRecants) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);

    const std::string now1 = "2026-05-30T10:00:00Z";
    const std::string now2 = "2026-05-30T10:03:00Z";

    std::string cg_id = writer.assert_(conn, "default", "stmt-004", {}, now1);
    writer.withdraw(conn, cg_id, "alice", now2);

    std::string status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg_id + "'");
    EXPECT_EQ(status, "recanted");

    int act_count = icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts"
        " WHERE common_ground_id='" + cg_id + "' AND act='withdraw'");
    EXPECT_EQ(act_count, 1);
}

// ── TC-CGW-005: SupersedeSetsSupersededBy ─────────────────────────────────────

TEST(CommonGroundWriter, SupersedeSetsSupersededBy) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);

    const std::string now1    = "2026-05-30T10:00:00Z";
    const std::string now2    = "2026-05-30T10:04:00Z";
    const std::string new_stmt = "stmt-new-001";

    std::string cg_id = writer.assert_(conn, "default", "stmt-005", {}, now1);
    writer.supersede_ground(conn, cg_id, new_stmt, now2);

    std::string superseded_by = scol(conn.raw(),
        "SELECT superseded_by FROM common_ground WHERE id='" + cg_id + "'");
    EXPECT_EQ(superseded_by, new_stmt);

    int act_count = icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts"
        " WHERE common_ground_id='" + cg_id + "' AND act='supersede'");
    EXPECT_EQ(act_count, 1);
}

// ── TC-CGW-006: TimeoutDowngrades ─────────────────────────────────────────────

TEST(CommonGroundWriter, TimeoutDowngrades) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);

    const std::string now = "2026-05-30T12:00:00Z";

    // Seed an old asserted_unack row (25h ago = 2026-05-29T11:00:00Z).
    const std::string old_now = "2026-05-29T11:00:00Z";
    std::string old_cg = writer.assert_(conn, "default", "stmt-old", {}, old_now);

    // Seed a fresh asserted_unack row (1h ago = 2026-05-30T11:00:00Z).
    const std::string fresh_now = "2026-05-30T11:00:00Z";
    std::string fresh_cg = writer.assert_(conn, "default", "stmt-fresh", {}, fresh_now);

    // Sweep with now = 2026-05-30T12:00:00Z (cutoff = 2026-05-29T12:00:00Z)
    int downgraded = writer.sweep_timeout_downgrade(conn, now);

    EXPECT_EQ(downgraded, 1) << "Exactly one row should be downgraded";

    std::string old_status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + old_cg + "'");
    EXPECT_EQ(old_status, "suspected_diverge");

    std::string fresh_status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + fresh_cg + "'");
    EXPECT_EQ(fresh_status, "asserted_unack")
        << "Fresh row should NOT be downgraded";
}
