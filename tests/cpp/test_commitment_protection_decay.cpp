#include "starling/replay/consolidation_ops.hpp"
#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling;
namespace {
// seed a COMMITS statement that WILL decay (S(t)<0.05 at far-future now): low salience, old last_accessed.
void seed_decayable_commits(sqlite3* db, const std::string& id) {
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,access_count,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
      "'bob','will_send','str','report','"+std::string(64,'a')+"','v1','COMMITS','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.05,'{}',0.0,'2026-05-30T09:00:00Z',0,'user_input','consolidated',"
      "'approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
std::string scol(sqlite3* db, const std::string& q){std::string o;sqlite3_exec(db,q.c_str(),[](void*p,int,char**v,char**){*(std::string*)p=v[0]?v[0]:"";return 0;},&o,nullptr);return o;}
}

// CONTROL: confirm the seed decays without protection (validates the test setup).
TEST(CommitmentProtectionDecay, ControlUnprotectedDecays) {
    auto a = persistence::SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_decayable_commits(c.raw(), "u1");  // NO commitment created → unprotected
    replay::op_decay(c, {"u1"}, "default", "2030-01-01T00:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT consolidation_state FROM statements WHERE id='u1'"), "archived");
}

// TC-A9-001 [CRITICAL]: ACTIVE commitment 保护 → 不 archive
TEST(CommitmentProtectionDecay, ActiveHoldingPreventsArchive) {
    auto a = persistence::SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_decayable_commits(c.raw(), "c1");
    prospective::CommitmentEngine(*a).create_from_statement(c, "c1", "default", "", "2026-05-30T10:00:00Z");
    replay::op_decay(c, {"c1"}, "default", "2030-01-01T00:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT consolidation_state FROM statements WHERE id='c1'"), "consolidated");
}

// TC-A9-002 [CRITICAL]: terminal → 解除 → archive
TEST(CommitmentProtectionDecay, TerminalReleasesProtection) {
    auto a = persistence::SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_decayable_commits(c.raw(), "c1");
    prospective::CommitmentEngine eng(*a);
    eng.create_from_statement(c, "c1", "default", "", "2026-05-30T10:00:00Z");
    eng.fulfill(c, "c1", "2026-05-30T11:00:00Z");
    replay::op_decay(c, {"c1"}, "default", "2030-01-01T00:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT consolidation_state FROM statements WHERE id='c1'"), "archived");
}

// TC-A9-003 [CRITICAL]: 新实例后保护 durable
TEST(CommitmentProtectionDecay, ProtectionDurableAcrossNewInstance) {
    auto a = persistence::SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_decayable_commits(c.raw(), "c1");
    prospective::CommitmentEngine(*a).create_from_statement(c, "c1", "default", "", "2026-05-30T10:00:00Z");
    prospective::CommitmentEngine fresh(*a); (void)fresh;  // 新实例,无 in-memory 状态
    replay::op_decay(c, {"c1"}, "default", "2030-01-01T00:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT consolidation_state FROM statements WHERE id='c1'"), "consolidated");
}
