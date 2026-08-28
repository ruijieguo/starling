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

void seed_stmt(sqlite3* db, const std::string& id,
               const std::string& tenant = "default") {
    const std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,created_at,updated_at) VALUES('" + id + "','" + tenant +
        "','alice','first_person','cognizer','bob','knows','str','x','h-" + id +
        "','v1','believes','pos',0.9,'2026-05-30T00:00:00Z',0.5,'{}',0.0,"
        "'2026-05-30T00:00:00Z','user_input','2026-05-30T00:00:00Z',"
        "'2026-05-30T00:00:00Z')";
    ASSERT_EQ(sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr), SQLITE_OK);
}

std::string assert_cg(CommonGroundWriter& writer,
                      starling::persistence::Connection& conn,
                      const std::string& stmt_id,
                      const std::vector<std::string>& parties,
                      const std::string& now) {
    seed_stmt(conn.raw(), stmt_id);
    return writer.assert_(conn, "default", stmt_id, parties, now);
}

}  // namespace

// ── TC-CGW-001: AssertCreatesAssertedUnack ────────────────────────────────────

TEST(CommonGroundWriter, AssertCreatesAssertedUnack) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);

    const std::string now = "2026-05-30T10:00:00Z";
    std::string cg_id = assert_cg(writer, conn, "stmt-001", {"alice", "bob"}, now);

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

    std::string cg_id = assert_cg(writer, conn, "stmt-002", {}, now1);
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

    std::string cg_id = assert_cg(writer, conn, "stmt-003", {}, now1);
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

    std::string cg_id = assert_cg(writer, conn, "stmt-004", {}, now1);
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

    std::string cg_id = assert_cg(writer, conn, "stmt-005", {}, now1);
    seed_stmt(conn.raw(), new_stmt);
    writer.acknowledge(conn, cg_id, "bob", now2);
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
    std::string old_cg = assert_cg(writer, conn, "stmt-old", {}, old_now);

    // Seed a fresh asserted_unack row (1h ago = 2026-05-30T11:00:00Z).
    const std::string fresh_now = "2026-05-30T11:00:00Z";
    std::string fresh_cg = assert_cg(writer, conn, "stmt-fresh", {}, fresh_now);

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

// ── P3.a2: 七幕补全(expire / unground / 人工确认) ───────────────────────────

TEST(CommonGroundWriter, ExpireGroundOnlyFromGrounded) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);
    const std::string now = "2026-06-12T10:00:00Z";

    std::string cg = assert_cg(writer, conn, "stmt-x", {"alice"}, now);
    // 未 grounded 时 expire 是 no-op(状态机不允许 asserted_unack → expired)。
    writer.expire_ground(conn, cg, "policy", now);
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg + "'"),
        "asserted_unack");

    writer.acknowledge(conn, cg, "bob", now);
    writer.expire_ground(conn, cg, "policy", now);
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg + "'"), "expired");
    EXPECT_EQ(scol(conn.raw(),
        "SELECT expired_at FROM common_ground WHERE id='" + cg + "'"), now);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts WHERE common_ground_id='" + cg +
        "' AND act='expire'"), 1);
}

TEST(CommonGroundWriter, UngroundBackToSuspectedDiverge) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);
    const std::string now = "2026-06-12T10:00:00Z";

    std::string cg = assert_cg(writer, conn, "stmt-y", {"alice"}, now);
    writer.acknowledge(conn, cg, "bob", now);
    writer.unground(conn, cg, "erasure", now);
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg + "'"),
        "suspected_diverge");
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts WHERE common_ground_id='" + cg +
        "' AND act='unground'"), 1);
}

TEST(CommonGroundWriter, ManualAcknowledgeKeepsAuditActor) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundWriter writer(*adapter);
    const std::string now = "2026-06-12T10:00:00Z";

    std::string cg = assert_cg(writer, conn, "stmt-z", {"alice"}, now);
    writer.acknowledge_manual(conn, cg, "reviewer-jane", now);
    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg + "'"), "grounded");
    EXPECT_EQ(scol(conn.raw(),
        "SELECT audit_actor FROM common_ground WHERE id='" + cg + "'"),
        "reviewer-jane");
}

TEST(CommonGroundWriter, AssertRejectsMissingOrCrossTenantStatement) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();
    CommonGroundWriter writer(*adapter);
    seed_stmt(conn.raw(), "shared", "other");

    EXPECT_THROW(
        writer.assert_(conn, "default", "shared", {"alice", "bob"},
                       "2026-06-12T10:00:00Z"),
        std::invalid_argument);
    EXPECT_EQ(icol(conn.raw(), "SELECT COUNT(*) FROM common_ground"), 0);
    EXPECT_EQ(icol(conn.raw(), "SELECT COUNT(*) FROM grounding_acts"), 0);
}

TEST(CommonGroundWriter, MigrationRejectsCrossTenantSupersededReferenceOnInsert) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "current", "default");
    seed_stmt(conn.raw(), "replacement", "other");

    const char* sql =
        "INSERT INTO common_ground("
        "id,tenant_id,statement_id,status,parties_json,superseded_by,created_at,updated_at) "
        "VALUES('cg-cross','default','current','grounded','[]','replacement',"
        "'2026-06-12T10:00:00Z','2026-06-12T10:00:00Z')";
    EXPECT_EQ(sqlite3_exec(conn.raw(), sql, nullptr, nullptr, nullptr), SQLITE_CONSTRAINT);
    EXPECT_EQ(icol(conn.raw(), "SELECT COUNT(*) FROM common_ground"), 0);
}

TEST(CommonGroundWriter, TerminalStateCannotBeAcknowledgedOrAudited) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();
    CommonGroundWriter writer(*adapter);
    const std::string now = "2026-06-12T10:00:00Z";
    std::string cg = assert_cg(writer, conn, "stmt-terminal", {"alice", "bob"}, now);
    writer.withdraw(conn, cg, "alice", now);
    writer.acknowledge(conn, cg, "bob", now);

    EXPECT_EQ(scol(conn.raw(),
        "SELECT status FROM common_ground WHERE id='" + cg + "'"), "recanted");
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts WHERE common_ground_id='" + cg +
        "' AND act='acknowledge'"), 0);

    writer.acknowledge(conn, "missing-cg", "bob", now);
    EXPECT_EQ(icol(conn.raw(),
        "SELECT COUNT(*) FROM grounding_acts WHERE common_ground_id='missing-cg'"), 0);
}
