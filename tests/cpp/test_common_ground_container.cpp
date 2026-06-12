// test_common_ground_container.cpp — CommonGroundContainer::rebuild tests.
//
// TC-CGC-001  MaterializesGroupedByStatus
// TC-CGC-002  EmptyCommonGroundProducesEmptyGroups
// TC-CGC-003  RebuildIncrementsVersion

#include "starling/neocortex/common_ground_container.hpp"
#include "starling/neocortex/persona_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling::neocortex;
using starling::persistence::SqliteAdapter;

namespace {

// Open fresh in-memory DB with all migrations applied.
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

void seed_cg(sqlite3* db, const std::string& id, const std::string& sid,
             const std::string& status) {
    std::string s =
        "INSERT INTO common_ground(id,tenant_id,statement_id,status,parties_json,"
        "created_at,updated_at) VALUES('" +
        id + "','default','" + sid + "','" + status + "','[]'," +
        "'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

}  // namespace

// ── TC-CGC-001: MaterializesGroupedByStatus ──────────────────────────────────

TEST(CommonGroundContainer, MaterializesGroupedByStatus) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundContainer cgc(*adapter);

    seed_cg(conn.raw(), "cg1", "stmt-grounded",  "grounded");
    seed_cg(conn.raw(), "cg2", "stmt-unack",      "asserted_unack");
    seed_cg(conn.raw(), "cg3", "stmt-diverge",    "suspected_diverge");
    // These should be ignored in the materialized view:
    seed_cg(conn.raw(), "cg4", "stmt-expired",    "expired");
    seed_cg(conn.raw(), "cg5", "stmt-recanted",   "recanted");

    cgc.rebuild(conn, "default", "cgref-1", "2026-05-30T10:00:00Z");

    std::string cj = scol(conn.raw(),
        "SELECT content_json FROM containers "
        "WHERE holder_id='cgref-1' AND kind='common_ground'");
    EXPECT_FALSE(cj.empty());

    // grounded group contains stmt-grounded
    EXPECT_NE(cj.find("stmt-grounded"), std::string::npos)
        << "Expected stmt-grounded in content_json: " << cj;
    // asserted_unack group contains stmt-unack
    EXPECT_NE(cj.find("stmt-unack"), std::string::npos)
        << "Expected stmt-unack in content_json: " << cj;
    // suspected_diverge group contains stmt-diverge
    EXPECT_NE(cj.find("stmt-diverge"), std::string::npos)
        << "Expected stmt-diverge in content_json: " << cj;

    // Expired and recanted must not appear
    EXPECT_EQ(cj.find("stmt-expired"),  std::string::npos)
        << "Did not expect stmt-expired in content_json: " << cj;
    EXPECT_EQ(cj.find("stmt-recanted"), std::string::npos)
        << "Did not expect stmt-recanted in content_json: " << cj;

    // JSON structure must have all three group keys
    EXPECT_NE(cj.find("\"grounded\""),        std::string::npos);
    EXPECT_NE(cj.find("\"asserted_unack\""),  std::string::npos);
    EXPECT_NE(cj.find("\"suspected_diverge\""), std::string::npos);
}

// ── TC-CGC-002: EmptyCommonGroundProducesEmptyGroups ─────────────────────────

TEST(CommonGroundContainer, EmptyCommonGroundProducesEmptyGroups) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundContainer cgc(*adapter);

    // No common_ground rows seeded.
    cgc.rebuild(conn, "default", "cgref-empty", "2026-05-30T10:00:00Z");

    std::string cj = scol(conn.raw(),
        "SELECT content_json FROM containers "
        "WHERE holder_id='cgref-empty' AND kind='common_ground'");
    EXPECT_FALSE(cj.empty()) << "Container should have been created even with no CG rows";

    // All three groups should be empty arrays
    EXPECT_NE(cj.find("\"grounded\":[]"),          std::string::npos)
        << "Expected grounded:[] in: " << cj;
    EXPECT_NE(cj.find("\"asserted_unack\":[]"),    std::string::npos)
        << "Expected asserted_unack:[] in: " << cj;
    EXPECT_NE(cj.find("\"suspected_diverge\":[]"), std::string::npos)
        << "Expected suspected_diverge:[] in: " << cj;
}

// ── TC-CGC-003: RebuildIncrementsVersion ─────────────────────────────────────

TEST(CommonGroundContainer, RebuildIncrementsVersion) {
    auto adapter = open_fresh();
    auto& conn   = adapter->connection();
    CommonGroundContainer cgc(*adapter);

    seed_cg(conn.raw(), "cg1", "stmt-a", "grounded");

    // First rebuild → version 1
    cgc.rebuild(conn, "default", "cgref-ver", "2026-05-30T10:00:00Z");
    int v1 = icol(conn.raw(),
        "SELECT version FROM containers "
        "WHERE holder_id='cgref-ver' AND kind='common_ground'");
    EXPECT_EQ(v1, 1);

    // Second rebuild → version 2
    cgc.rebuild(conn, "default", "cgref-ver", "2026-05-30T10:00:00Z");
    int v2 = icol(conn.raw(),
        "SELECT version FROM containers "
        "WHERE holder_id='cgref-ver' AND kind='common_ground'");
    EXPECT_EQ(v2, 2);
}

// ── P3.a2: sorted-pair cg_ref 的 parties 过滤(P2.j 遗留修复) ────────────────

namespace {
void seed_cg_pair(sqlite3* db, const std::string& id, const std::string& sid,
                  const std::string& parties_json) {
    std::string s =
        "INSERT INTO common_ground(id,tenant_id,statement_id,status,parties_json,"
        "created_at,updated_at) VALUES('" +
        id + "','default','" + sid + "','grounded','" + parties_json + "'," +
        "'2026-06-12T09:00:00Z','2026-06-12T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
}  // namespace

TEST(CommonGroundContainer, PairRefFiltersByParties) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();
    seed_cg_pair(conn.raw(), "cg-ab", "stmt-ab", "[\"alice\",\"bob\"]");
    seed_cg_pair(conn.raw(), "cg-cd", "stmt-cd", "[\"carol\",\"dave\"]");

    CommonGroundContainer cgc(*adapter);
    cgc.rebuild(conn, "default", "alice::bob", "2026-06-12T10:00:00Z");
    const std::string cj = scol(conn.raw(),
        "SELECT content_json FROM containers WHERE holder_id='alice::bob'");
    EXPECT_NE(cj.find("stmt-ab"), std::string::npos);
    EXPECT_EQ(cj.find("stmt-cd"), std::string::npos)
        << "carol/dave 的共识不得混入 alice::bob 容器: " << cj;

    // 旧语义兼容:无 "::" 的 ref 仍是全租户。
    cgc.rebuild(conn, "default", "legacy-ref", "2026-06-12T10:00:00Z");
    const std::string legacy = scol(conn.raw(),
        "SELECT content_json FROM containers WHERE holder_id='legacy-ref'");
    EXPECT_NE(legacy.find("stmt-ab"), std::string::npos);
    EXPECT_NE(legacy.find("stmt-cd"), std::string::npos);
}
