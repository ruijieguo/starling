// test_commitment_pending.cpp -- P2.e CommitmentEngine.pending
#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>

using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::prospective::CommitmentEngine;
using starling::prospective::CommitmentView;

namespace {
void seed_commit_stmt(sqlite3* db, const std::string& id, const std::string& obj) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('" + id + "','default','alice','first_person','cognizer',"
        "'bob','owes','str','" + obj + "','" + std::string(64,'a') + "','v1','commits','pos',"
        "0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,'2026-06-01T09:00:00Z','user_input',"
        "'consolidated','approved','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
void seed_fired_trigger(sqlite3* db, const std::string& cid) {
    std::string s = "INSERT INTO commitment_triggers(id,commitment_stmt_id,tenant_id,kind,"
        "spec_json,status,created_at) VALUES('t-" + cid + "','" + cid +
        "','default','time','{}','fired','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
}  // namespace

TEST(CommitmentPending, ActiveTowardInterlocutorWithFired) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_commit_stmt(db, "c1", "design doc");
    CommitmentEngine ce(*adapter);
    ce.create_from_statement(conn, "c1", "default", "2026-06-01T08:00:00Z", "2026-06-01T07:00:00Z");
    seed_fired_trigger(db, "c1");

    auto rows = ce.pending(conn, "default", "alice", "bob");
    ASSERT_EQ(rows.size(), 1u);
    EXPECT_EQ(rows[0].stmt_id, "c1");
    EXPECT_EQ(rows[0].state, "ACTIVE");
    EXPECT_TRUE(rows[0].fired);
    EXPECT_EQ(rows[0].object_value, "design doc");
    EXPECT_EQ(rows[0].subject_id, "bob");
}

TEST(CommitmentPending, InterlocutorFilterExcludesOthers) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_commit_stmt(db, "c1", "design doc");   // subject_id='bob'
    CommitmentEngine ce(*adapter);
    ce.create_from_statement(conn, "c1", "default", "", "2026-06-01T07:00:00Z");
    auto rows = ce.pending(conn, "default", "alice", "carol");  // does not match bob
    EXPECT_TRUE(rows.empty());
}
