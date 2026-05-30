#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::prospective;
using starling::persistence::SqliteAdapter;
namespace {
void seed_commits_stmt(sqlite3* db, const std::string& id) {
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
      "'bob','will_send','str','report','"+std::string(64,'a')+"','v1','COMMITS','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','consolidated',"
      "'approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
std::string scol(sqlite3* db, const std::string& q) {
    std::string out; sqlite3_exec(db,q.c_str(),
        [](void*p,int,char**v,char**){*(std::string*)p=v[0]?v[0]:"";return 0;},&out,nullptr); return out;
}
int icol(sqlite3* db, const std::string& q) {
    int n=0; sqlite3_exec(db,q.c_str(),[](void*p,int,char**v,char**){*(int*)p=v[0]?atoi(v[0]):0;return 0;},&n,nullptr); return n;
}
}

TEST(CommitmentEngine, CreateActivates) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    CommitmentEngine(*a).create_from_statement(c, "c1", "default", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='c1'"), "ACTIVE");
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM commitment_protection WHERE protected_stmt_id='c1'"), 1);
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.active_holding' AND primary_id='c1'"), 1);
}

TEST(CommitmentEngine, ThreeBrokenAutoWithdrawn) {  // TC-A2-001 CRITICAL
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    CommitmentEngine eng(*a);
    eng.create_from_statement(c, "c1", "default", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z");
    for (int i = 0; i < 3; ++i) {
        eng.on_deadline_expired(c, "c1", "default", "2026-05-30T19:00:00Z");
        sqlite3_exec(c.raw(), "UPDATE commitments SET state='ACTIVE' WHERE stmt_id='c1'", nullptr,nullptr,nullptr);
    }
    eng.on_deadline_expired(c, "c1", "default", "2026-05-30T20:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='c1'"), "WITHDRAWN");
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.auto_withdrawn' AND primary_id='c1'"), 1);
}

TEST(CommitmentEngine, RenegotiationChainCappedAtThree) {  // TC-A2-002 CRITICAL
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c0");
    CommitmentEngine eng(*a);
    eng.create_from_statement(c, "c0", "default", "", "2026-05-30T10:00:00Z");
    seed_commits_stmt(c.raw(), "c1"); EXPECT_TRUE(eng.renegotiate(c, "c0", "c1", "default", "2026-05-30T11:00:00Z"));
    seed_commits_stmt(c.raw(), "c2"); EXPECT_TRUE(eng.renegotiate(c, "c1", "c2", "default", "2026-05-30T12:00:00Z"));
    seed_commits_stmt(c.raw(), "c3"); EXPECT_FALSE(eng.renegotiate(c, "c2", "c3", "default", "2026-05-30T13:00:00Z"));
    EXPECT_GE(icol(c.raw(), "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.renegotiation_blocked'"), 1);
}
