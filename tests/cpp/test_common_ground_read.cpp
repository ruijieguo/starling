// test_common_ground_read.cpp -- P2.e CommonGroundContainer.read
#include "starling/neocortex/common_ground_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/tom/common_ground.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>

using starling::neocortex::CommonGroundContainer;
using starling::neocortex::CommonGroundView;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;

namespace {
void seed_stmt(sqlite3* db, const std::string& id, const std::string& obj) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('" + id + "','default','alice','first_person','cognizer',"
        "'bob','knows','str','" + obj + "','" + std::string(64,'a') + "','v1','believes','pos',"
        "0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,'2026-06-01T09:00:00Z','user_input',"
        "'consolidated','approved','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
// common_ground columns: id, tenant_id, statement_id, status, parties_json,
// grounded_at, last_confirmed_at, superseded_by, expired_at, audit_actor,
// created_at, updated_at  (parties_json has DEFAULT '[]'; others nullable)
void seed_cg(sqlite3* db, const std::string& sid, const std::string& status) {
    // P3.a2 起 pair 形 cg_ref("alice::bob")按 parties 过滤,种子行必须挂
    // 对应 parties(此前 DEFAULT '[]' 依赖全租户镜像缺陷,roadmap 登记修复)。
    std::string s = "INSERT INTO common_ground(id,tenant_id,statement_id,status,"
        "parties_json,created_at,updated_at)"
        " VALUES('cg-" + sid + "','default','" + sid + "','" + status +
        "','[\"alice\",\"bob\"]','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

void seed_cg_parties(sqlite3* db, const std::string& id,
                     const std::string& sid, const std::string& parties_json) {
    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "INSERT INTO common_ground(id,tenant_id,statement_id,status,parties_json,"
        "created_at,updated_at) VALUES(?,'default',?,'grounded',?,"
        "'2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(db, sql, -1, &raw, nullptr));
    sqlite3_bind_text(raw, 1, id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, sid.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, parties_json.c_str(), -1, SQLITE_TRANSIENT);
    EXPECT_EQ(SQLITE_DONE, sqlite3_step(raw));
    sqlite3_finalize(raw);
}
}  // namespace

TEST(CommonGroundRead, RebuildThenRead) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1", "auth");
    seed_cg(db, "s1", "grounded");
    CommonGroundContainer cg(*adapter);
    cg.rebuild(conn, "default", "alice::bob", "2026-06-01T09:00:00Z");

    CommonGroundView v = cg.read(conn, "default", "alice::bob");
    EXPECT_TRUE(v.found);
    ASSERT_EQ(v.grounded.size(), 1u);
    EXPECT_NE(v.grounded[0].find("auth"), std::string::npos);  // rendered contains object
}

TEST(CommonGroundRead, MissingReturnsNotFound) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    CommonGroundContainer cg(*adapter);
    CommonGroundView v = cg.read(conn, "default", "none::none");
    EXPECT_FALSE(v.found);
}

TEST(CommonGroundRead, PartyLookupTreatsSqlWildcardsLiterally) {
    auto adapter = SqliteAdapter::open(":memory:");
    sqlite3* db = adapter->connection().raw();
    seed_stmt(db, "wild", "exact");
    seed_stmt(db, "lookalike", "wrong");
    seed_cg_parties(db, "cg-wild", "wild", R"(["a%","b_"])" );
    seed_cg_parties(db, "cg-lookalike", "lookalike", R"(["ax","bZ"])" );

    const auto rows = starling::tom::common_ground::query(
        *adapter, "a%", "b_", "default", "2026-06-01T10:00:00Z");
    ASSERT_EQ(rows.size(), 1u);
    EXPECT_EQ(rows[0].statement_id, "wild");
}
