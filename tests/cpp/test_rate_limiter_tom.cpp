#include "starling/tom/rate_limiter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <string>

namespace starling::tom::rate_limiter {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Insert a minimal tom_inferred (or other provenance) statement row directly
// into the statements table, bypassing StatementWriter, so we can set
// observed_at to an arbitrary timestamp.
void insert_raw_statement(persistence::Connection& conn,
                          const std::string& id,
                          const std::string& tenant_id,
                          const std::string& holder_id,
                          const std::string& subject_id,
                          const std::string& predicate,
                          const std::string& canonical_object_hash,
                          const std::string& provenance,
                          const std::string& observed_at) {
    sqlite3* db = conn.raw();
    const std::string sql =
        "INSERT INTO statements("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate, object_kind, object_value,"
        "  canonical_object_hash, canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at,"
        "  salience, affect_json, activation, last_accessed,"
        "  provenance, evidence_json, source_spans_json, perceived_by_json,"
        "  consolidation_state, review_status,"
        "  derived_from_json, derived_depth,"
        "  nesting_depth,"
        "  created_at, updated_at"
        ") VALUES ("
        "  ?, ?, ?, 'first_person',"
        "  'cognizer', ?, ?, 'str', 'some-value',"
        "  ?, 'v1',"
        "  'believes', 'pos', 0.9, ?,"
        "  0.0, '{}', 0.0, ?,"
        "  ?, '[]', '[]', '[]',"
        "  'volatile', 'approved',"
        "  '[]', 0,"
        "  0,"
        "  ?, ?"
        ")";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h(raw);

    auto bind = [&](int idx, const std::string& v) {
        sqlite3_bind_text(h.get(), idx, v.c_str(), -1, SQLITE_TRANSIENT);
    };

    bind(1,  id);
    bind(2,  tenant_id);
    bind(3,  holder_id);
    bind(4,  subject_id);
    bind(5,  predicate);
    bind(6,  canonical_object_hash);
    bind(7,  observed_at);   // observed_at
    bind(8,  observed_at);   // last_accessed (same for test purposes)
    bind(9,  provenance);
    bind(10, observed_at);   // created_at
    bind(11, observed_at);   // updated_at

    ASSERT_EQ(sqlite3_step(h.get()), SQLITE_DONE) << sqlite3_errmsg(db);
}

}  // namespace

// ----- Tests ---------------------------------------------------------------

TEST(RateLimiterTom, AllowsWhenNoPriorWrite) {
    auto a = make_adapter();
    auto& conn = a->connection();

    const bool ok = allow_tom_inferred_write(
        conn,
        "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "2026-05-26T12:00:00Z");

    EXPECT_TRUE(ok);
}

TEST(RateLimiterTom, RejectsSameKeyWithinWindow) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert at t-5min (300 seconds before as_of).
    insert_raw_statement(conn,
        "stmt-001", "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "tom_inferred",
        "2026-05-26T11:55:00Z");  // t - 5min

    // Check at t — should be rejected (within 600s window).
    const bool ok = allow_tom_inferred_write(
        conn,
        "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "2026-05-26T12:00:00Z");

    EXPECT_FALSE(ok);
}

TEST(RateLimiterTom, AllowsSameKeyOutsideWindow) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert at t-15min (900 seconds before as_of — outside 600s window).
    insert_raw_statement(conn,
        "stmt-002", "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "tom_inferred",
        "2026-05-26T11:45:00Z");  // t - 15min

    // Check at t — should be allowed.
    const bool ok = allow_tom_inferred_write(
        conn,
        "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "2026-05-26T12:00:00Z");

    EXPECT_TRUE(ok);
}

TEST(RateLimiterTom, AllowsDifferentKey) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert with predicate "knows_emotion".
    insert_raw_statement(conn,
        "stmt-003", "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "tom_inferred",
        "2026-05-26T11:55:00Z");

    // Check with different predicate "knows_mood" — should be allowed.
    const bool ok = allow_tom_inferred_write(
        conn,
        "tenant-1", "alice", "bob",
        "knows_mood", "hash-abc",
        "2026-05-26T12:00:00Z");

    EXPECT_TRUE(ok);
}

TEST(RateLimiterTom, AllowsDifferentProvenance) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert with provenance='observed' (not tom_inferred).
    insert_raw_statement(conn,
        "stmt-004", "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "observed",  // NOT tom_inferred
        "2026-05-26T11:55:00Z");

    // Rate limiter only cares about tom_inferred rows — should be allowed.
    const bool ok = allow_tom_inferred_write(
        conn,
        "tenant-1", "alice", "bob",
        "knows_emotion", "hash-abc",
        "2026-05-26T12:00:00Z");

    EXPECT_TRUE(ok);
}

TEST(RateLimiterTom, TenantIsolation) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert in tenant-a.
    insert_raw_statement(conn,
        "stmt-005", "tenant-a", "alice", "bob",
        "knows_emotion", "hash-abc",
        "tom_inferred",
        "2026-05-26T11:55:00Z");

    // Check in tenant-b — should be allowed (different tenant).
    const bool ok = allow_tom_inferred_write(
        conn,
        "tenant-b", "alice", "bob",
        "knows_emotion", "hash-abc",
        "2026-05-26T12:00:00Z");

    EXPECT_TRUE(ok);
}

}  // namespace starling::tom::rate_limiter
