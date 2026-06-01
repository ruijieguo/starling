// test_common_ground_read.cpp -- P2.e CommonGroundContainer.read
#include "starling/neocortex/common_ground_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
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
    std::string s = "INSERT INTO common_ground(id,tenant_id,statement_id,status,created_at,updated_at)"
        " VALUES('cg-" + sid + "','default','" + sid + "','" + status +
        "','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
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
