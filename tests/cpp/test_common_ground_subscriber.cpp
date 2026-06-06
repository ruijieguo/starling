// test_common_ground_subscriber.cpp — CommonGroundSubscriber grounding lifecycle.
//
// TC-CGS-001  AssertCreatesAssertedUnack
//             scope_parties>=2 statement.written -> common_ground asserted_unack.
// TC-CGS-002  OtherPartyRestatementGrounds
//             other party restates same proposition (same polarity) -> grounded.
// TC-CGS-003  OppositePolarityRepairs
//             other party restates opposite polarity -> suspected_diverge.
// TC-CGS-004  ContainerRebuilt
//             after a tick, common_ground container (holder_id='bob::self') non-empty.

#include "starling/tom/common_ground_subscriber.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling::tom;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;

namespace {

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const auto* txt = sqlite3_column_text(s, 0);
    std::string v = txt ? reinterpret_cast<const char*>(txt) : "";
    sqlite3_finalize(s);
    return v;
}

int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

// Insert a statement row carrying scope_parties_json (covers required NOT NULL cols).
void insert_statement(Connection& conn,
                      const std::string& stmt_id,
                      const std::string& holder_id,
                      const std::string& polarity,
                      const std::string& scope_parties_json,
                      const std::string& tenant_id = "default",
                      const std::string& subject_id = "bob",
                      const std::string& predicate = "p",
                      const std::string& hash = "h") {
    const char* sql =
        "INSERT INTO statements("
        "id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,"
        "polarity,confidence,observed_at,salience,affect_json,activation,"
        "last_accessed,provenance,consolidation_state,review_status,"
        "scope_parties_json,created_at,updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    int i = 1;
    auto bs = [&](const std::string& v) {
        sqlite3_bind_text(h.get(), i++, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    auto bd = [&](double v) { sqlite3_bind_double(h.get(), i++, v); };
    bs(stmt_id);
    bs(tenant_id);
    bs(holder_id);
    bs("first_person");
    bs("entity");                 // subject_kind
    bs(subject_id);
    bs(predicate);
    bs("str");                    // object_kind
    bs("val");                    // object_value
    bs(hash);                     // canonical_object_hash
    bs("v1");
    bs("believes");               // modality
    bs(polarity);
    bd(0.8);                      // confidence
    bs("2026-01-01T00:00:00Z");   // observed_at
    bd(0.5);                      // salience
    bs("{}");                     // affect_json
    bd(1.0);                      // activation
    bs("2026-01-01T00:00:00Z");   // last_accessed
    bs("user_input");             // provenance
    bs("consolidated");           // consolidation_state
    bs("approved");               // review_status
    bs(scope_parties_json);       // scope_parties_json
    bs("2026-01-01T00:00:00Z");   // created_at
    bs("2026-01-01T00:00:00Z");   // updated_at
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
}

// Insert a statement.written bus_events row directly (deterministic outbox_sequence).
void insert_bus_event(Connection& conn,
                      const std::string& event_id,
                      const std::string& stmt_id,
                      int outbox_sequence,
                      const std::string& tenant_id = "default") {
    const char* sql =
        "INSERT INTO bus_events("
        "event_id,tenant_id,event_type,primary_id,aggregate_id,"
        "outbox_sequence,idempotency_key,payload_json,created_at"
        ") VALUES (?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    int i = 1;
    auto bs = [&](const std::string& v) {
        sqlite3_bind_text(h.get(), i++, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    bs(event_id);
    bs(tenant_id);
    bs("statement.written");
    bs(stmt_id);             // primary_id = statement id
    bs(stmt_id);             // aggregate_id
    sqlite3_bind_int(h.get(), i++, outbox_sequence);
    bs("ikey-" + event_id);  // idempotency_key
    bs("{}");                // payload_json
    bs("2026-06-06T00:00:00Z");  // created_at
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
}

}  // namespace

// ── TC-CGS-001: AssertCreatesAssertedUnack ────────────────────────────────────

TEST(CommonGroundSubscriber, AssertCreatesAssertedUnack) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    insert_statement(conn, "S1", "self", "pos", "[\"bob\",\"self\"]");
    insert_bus_event(conn, "ev1", "S1", 1);

    int n = CommonGroundSubscriber::tick_one_batch(
        *adapter, adapter->connection(), "2026-06-06T10:00:00Z");
    EXPECT_EQ(n, 1);

    int cnt = icol(conn.raw(),
        "SELECT COUNT(*) FROM common_ground WHERE status='asserted_unack'");
    EXPECT_EQ(cnt, 1);
}

// ── TC-CGS-002: OtherPartyRestatementGrounds ──────────────────────────────────

TEST(CommonGroundSubscriber, OtherPartyRestatementGrounds) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    // S1 asserted by self.
    insert_statement(conn, "S1", "self", "pos", "[\"bob\",\"self\"]");
    insert_bus_event(conn, "ev1", "S1", 1);
    CommonGroundSubscriber::tick_one_batch(
        *adapter, adapter->connection(), "2026-06-06T10:00:00Z");

    // S2: bob restates the same proposition (same subj/pred/hash, same polarity).
    insert_statement(conn, "S2", "bob", "pos", "[\"bob\",\"self\"]");
    insert_bus_event(conn, "ev2", "S2", 2);
    CommonGroundSubscriber::tick_one_batch(
        *adapter, adapter->connection(), "2026-06-06T10:01:00Z");

    std::string status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE statement_id='S1'");
    EXPECT_EQ(status, "grounded");

    // No second asserted row for S2 (it acknowledged, not re-asserted).
    int cnt = icol(conn.raw(), "SELECT COUNT(*) FROM common_ground");
    EXPECT_EQ(cnt, 1);
}

// ── TC-CGS-003: OppositePolarityRepairs ───────────────────────────────────────

TEST(CommonGroundSubscriber, OppositePolarityRepairs) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    insert_statement(conn, "S1", "self", "pos", "[\"bob\",\"self\"]");
    insert_bus_event(conn, "ev1", "S1", 1);
    CommonGroundSubscriber::tick_one_batch(
        *adapter, adapter->connection(), "2026-06-06T10:00:00Z");

    // S2: bob restates with OPPOSITE polarity -> repair.
    insert_statement(conn, "S2", "bob", "neg", "[\"bob\",\"self\"]");
    insert_bus_event(conn, "ev2", "S2", 2);
    CommonGroundSubscriber::tick_one_batch(
        *adapter, adapter->connection(), "2026-06-06T10:01:00Z");

    std::string status = scol(conn.raw(),
        "SELECT status FROM common_ground WHERE statement_id='S1'");
    EXPECT_EQ(status, "suspected_diverge");
}

// ── TC-CGS-004: ContainerRebuilt ──────────────────────────────────────────────

TEST(CommonGroundSubscriber, ContainerRebuilt) {
    auto adapter = open_fresh();
    auto& conn = adapter->connection();

    insert_statement(conn, "S1", "self", "pos", "[\"bob\",\"self\"]");
    insert_bus_event(conn, "ev1", "S1", 1);
    CommonGroundSubscriber::tick_one_batch(
        *adapter, adapter->connection(), "2026-06-06T10:00:00Z");

    // cg_ref = sorted parties "bob::self".
    std::string content = scol(conn.raw(),
        "SELECT content_json FROM containers "
        "WHERE kind='common_ground' AND holder_id='bob::self'");
    EXPECT_FALSE(content.empty());
    // Contains the asserted statement id.
    EXPECT_NE(content.find("S1"), std::string::npos);
}
