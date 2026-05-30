// test_commitment_tenant_isolation.cpp -- P2.c hardening regression.
//
// commitments / commitment_protection key by (tenant_id, stmt_id); statements PK
// is (id, tenant_id). Two tenants may legitimately share a stmt_id. This test
// proves they no longer collide: two commitments under the SAME stmt_id "x" but
// distinct tenants "A"/"B" coexist, and a transition on one does not affect the
// other.

#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <string>

using namespace starling::prospective;
using starling::persistence::SqliteAdapter;

namespace {

// Seed a COMMITS statement with an explicit (id, tenant_id). The composite PK
// lets the same id exist under two tenants.
void seed_commits_stmt(sqlite3* db, const std::string& id, const std::string& tenant) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('" + id + "','" + tenant + "','alice','first_person','cognizer',"
        "'bob','will_send','str','report','" + std::string(64, 'a') + "','v1','COMMITS','pos',0.9,"
        "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','consolidated',"
        "'approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
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

// Two tenants sharing a stmt_id must not collide; a transition on one tenant's
// commitment leaves the other's untouched.
TEST(CommitmentTenantIsolation, SharedStmtIdNoCollision) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();

    seed_commits_stmt(c.raw(), "x", "A");
    seed_commits_stmt(c.raw(), "x", "B");

    CommitmentEngine eng(*a);
    eng.create_from_statement(c, "x", "A", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z");
    eng.create_from_statement(c, "x", "B", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z");

    // Both commitments exist under the shared stmt_id — no collision.
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM commitments WHERE stmt_id='x'"), 2);
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='x' AND tenant_id='A'"), "ACTIVE");
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='x' AND tenant_id='B'"), "ACTIVE");

    // Fulfilling A's commitment must not touch B's.
    eng.fulfill(c, "x", "A", "2026-05-30T11:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='x' AND tenant_id='A'"), "FULFILLED");
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='x' AND tenant_id='B'"), "ACTIVE");

    // Protection rows are tenant-scoped too: one per (tenant, stmt).
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM commitment_protection WHERE protected_stmt_id='x'"), 2);
}
