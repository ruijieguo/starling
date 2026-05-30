// test_policy_engine_tick.cpp -- P2.c PolicyEngine.tick (Task 9).
//
// TimeTriggerFires: an armed 'time' trigger whose {"at"} is past → commitment.fire
//   emitted, trigger status='fired', stats.fired>=1.
// DeadlineExpiryBreaks: an ACTIVE commitment whose deadline has passed →
//   on_deadline_expired transitions it to BROKEN, stats.broken>=1.

#include "starling/prospective/policy_engine.hpp"
#include "starling/prospective/commitment_engine.hpp"

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <string>

using namespace starling::prospective;
using starling::persistence::SqliteAdapter;

namespace {

// Seed a COMMITS statement (copied from test_commitment_engine.cpp).
void seed_commits_stmt(sqlite3* db, const std::string& id) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('" + id + "','default','alice','first_person','cognizer',"
        "'bob','will_send','str','report','" + std::string(64, 'a') + "','v1','COMMITS','pos',0.9,"
        "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','consolidated',"
        "'approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

void insert_armed_time_trigger(sqlite3* db, const std::string& id,
                               const std::string& commitment_stmt_id,
                               const std::string& at_iso) {
    std::string s =
        "INSERT INTO commitment_triggers"
        "(id, commitment_stmt_id, tenant_id, kind, spec_json, status, created_at)"
        " VALUES('" + id + "','" + commitment_stmt_id + "','default','time',"
        "'{\"at\":\"" + at_iso + "\"}','armed','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

std::string scol(sqlite3* db, const std::string& q) {
    std::string out;
    sqlite3_exec(db, q.c_str(),
        [](void* p, int, char** v, char**) { *(std::string*)p = v[0] ? v[0] : ""; return 0; },
        &out, nullptr);
    return out;
}

int icol(sqlite3* db, const std::string& q) {
    int n = 0;
    sqlite3_exec(db, q.c_str(),
        [](void* p, int, char** v, char**) { *(int*)p = v[0] ? atoi(v[0]) : 0; return 0; },
        &n, nullptr);
    return n;
}

}  // namespace

TEST(PolicyEngineTick, TimeTriggerFires) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    // ACTIVE commitment, no deadline (so deadline-expiry path is not triggered).
    CommitmentEngine(*a).create_from_statement(c, "c1", "default", "",
                                               "2026-05-30T10:00:00Z");
    insert_armed_time_trigger(c.raw(), "trig-1", "c1", "2026-05-30T09:00:00Z");

    PolicyTickStats stats = PolicyEngine(*a).tick(c, "2026-05-30T12:00:00Z");

    EXPECT_GE(stats.fired, 1);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.fire' AND primary_id='c1'"),
        1);
    EXPECT_EQ(scol(c.raw(), "SELECT status FROM commitment_triggers WHERE id='trig-1'"),
        "fired");
}

TEST(PolicyEngineTick, DeadlineExpiryBreaks) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c2");
    // ACTIVE commitment with a deadline already in the past relative to tick now.
    CommitmentEngine(*a).create_from_statement(c, "c2", "default",
                                               "2026-05-30T11:00:00Z",
                                               "2026-05-30T10:00:00Z");

    PolicyTickStats stats = PolicyEngine(*a).tick(c, "2026-05-30T12:00:00Z");

    EXPECT_GE(stats.broken, 1);
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='c2'"), "BROKEN");
}
