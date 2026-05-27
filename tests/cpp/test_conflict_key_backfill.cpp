// Tests for conflict_key_backfill::tick_one_batch + is_complete.
// Scenarios:
//   1. is_complete returns false initially, true after completion.
//   2. Empty DB -> tick_one_batch sets completed_now=true on first call.
//   3. N pre-existing NULL-key conflicts_with edges -> tick fills them in.
//   4. Two edges that recompute to same key -> second is deleted (rows_deduped).
//   5. tick_one_batch is idempotent after completion (returns empty stats).

#include "starling/bus/conflict_key_backfill.hpp"
#include "starling/bus/conflict_key.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <optional>
#include <string>

namespace starling::bus::conflict_key_backfill {
namespace {

using starling::extractor::ExtractedStatement;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;

std::unique_ptr<SqliteAdapter> open_fresh() {
    auto a = SqliteAdapter::open(":memory:");
    MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Count rows matching a single-column COUNT(*) SQL.
int count_rows(Connection& conn, const std::string& sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr));
    StmtHandle h(raw);
    EXPECT_EQ(SQLITE_ROW, sqlite3_step(h.get()));
    return sqlite3_column_int(h.get(), 0);
}

// Insert a minimal statement row (bypasses StatementWriter).
void insert_stmt_row(Connection& conn,
                     const std::string& id,
                     const std::string& holder_id = "holder-a",
                     const std::string& subject_kind = "entity",
                     const std::string& subject_id = "subj-1",
                     const std::string& predicate = "knows",
                     const std::string& obj_hash = "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222",
                     const std::string& modality = "believes",
                     const std::string& tenant_id = "default") {
    const char* sql =
        "INSERT INTO statements("
        "id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,"
        "polarity,confidence,observed_at,salience,affect_json,activation,"
        "last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    int i = 1;
    sqlite3_bind_text(h.get(), i++, id.c_str(),          -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, tenant_id.c_str(),   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, holder_id.c_str(),   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "first_person",       -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, subject_kind.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, subject_id.c_str(),   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, predicate.c_str(),    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "str",                -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "val",                -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, obj_hash.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "v1",                 -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, modality.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "pos",                -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 0.8);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 0.5);
    sqlite3_bind_text(h.get(), i++, "{}",                 -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 1.0);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "user_input",         -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "consolidated",       -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "approved",           -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
}

// Insert a conflicts_with edge with NULL canonical_conflict_key.
void insert_null_key_edge(Connection& conn,
                          const std::string& edge_id,
                          const std::string& src_id,
                          const std::string& dst_id,
                          const std::string& tenant_id = "default") {
    const char* sql =
        "INSERT INTO statement_edges"
        "(id, tenant_id, src_id, dst_id, edge_kind, canonical_conflict_key, created_at)"
        " VALUES (?, ?, ?, ?, 'conflicts_with', NULL, '2026-01-01T00:00:00Z')";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    sqlite3_bind_text(h.get(), 1, edge_id.c_str(),    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 2, tenant_id.c_str(),  -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 3, src_id.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 4, dst_id.c_str(),     -1, SQLITE_TRANSIENT);
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
}

// Read completed_at from backfill state.
bool state_has_completed_at(Connection& conn) {
    const char* sql =
        "SELECT completed_at FROM conflict_key_backfill_state WHERE id = 1";
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    if (sqlite3_step(h.get()) != SQLITE_ROW) return false;
    return sqlite3_column_type(h.get(), 0) != SQLITE_NULL;
}

// ── Test 1: is_complete initially false ─────────────────────────────────────

TEST(ConflictKeyBackfill, IsCompleteInitiallyFalse) {
    auto a = open_fresh();
    EXPECT_FALSE(is_complete(a->connection()));
}

// ── Test 2: empty DB -> completed_now=true on first tick ─────────────────────

TEST(ConflictKeyBackfill, EmptyDbCompletesImmediately) {
    auto a = open_fresh();
    auto& conn = a->connection();

    EXPECT_FALSE(is_complete(conn));
    const TickStats s = tick_one_batch(conn, 100);

    EXPECT_TRUE(s.completed_now);
    EXPECT_EQ(0, s.rows_processed);
    EXPECT_EQ(0, s.rows_backfilled);
    EXPECT_EQ(0, s.rows_deduped);
    EXPECT_TRUE(is_complete(conn));
    EXPECT_TRUE(state_has_completed_at(conn));
}

// ── Test 3: N NULL-key edges -> all backfilled ───────────────────────────────

TEST(ConflictKeyBackfill, NullKeyEdgesGetBackfilled) {
    auto a = open_fresh();
    auto& conn = a->connection();

    // Insert two distinct statements + two NULL-key conflicts_with edges.
    insert_stmt_row(conn, "stmt-A", "holder-a", "entity", "subj-1",
                    "knows", "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222");
    insert_stmt_row(conn, "stmt-B", "holder-a", "entity", "subj-2",
                    "likes", "bbbb1111cccc2222dddd3333eeee4444ffff5555aaaa6666bbbb1111cccc2222");

    // Edge from A -> B (and B -> A for 2 edges total)
    insert_null_key_edge(conn, "edge-AB", "stmt-A", "stmt-B");
    insert_null_key_edge(conn, "edge-BA", "stmt-B", "stmt-A");

    EXPECT_EQ(2, count_rows(conn,
        "SELECT COUNT(*) FROM statement_edges "
        "WHERE edge_kind='conflicts_with' AND canonical_conflict_key IS NULL"));

    const TickStats s = tick_one_batch(conn, 100);

    EXPECT_EQ(2, s.rows_processed);
    EXPECT_EQ(2, s.rows_backfilled);
    EXPECT_EQ(0, s.rows_deduped);
    // All NULL-key edges filled in.
    EXPECT_EQ(0, count_rows(conn,
        "SELECT COUNT(*) FROM statement_edges "
        "WHERE edge_kind='conflicts_with' AND canonical_conflict_key IS NULL"));
    // Two edges still exist with non-NULL keys.
    EXPECT_EQ(2, count_rows(conn,
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
}

// ── Test 4: two edges with same recomputed key -> second is deleted ──────────

TEST(ConflictKeyBackfill, DuplicateKeyEdgeIsDeleted) {
    auto a = open_fresh();
    auto& conn = a->connection();

    // Insert statements src A->B and src C->D where A and C have the same
    // conflict-key 7-tuple (same holder, subject, predicate, hash, modality,
    // no interval).  The second conflicts_with edge will collide on the UNIQUE
    // index after the first is backfilled.
    const std::string obj_hash =
        "deadbeef01234567deadbeef01234567deadbeef01234567deadbeef01234567";
    // stmt-A and stmt-C share the same 7-tuple -> same canonical_conflict_key.
    insert_stmt_row(conn, "stmt-A", "holder-x", "entity", "subj-x", "pred-x", obj_hash, "believes");
    insert_stmt_row(conn, "stmt-B", "holder-x", "entity", "subj-y", "pred-y", obj_hash, "believes");
    insert_stmt_row(conn, "stmt-C", "holder-x", "entity", "subj-x", "pred-x", obj_hash, "believes");
    insert_stmt_row(conn, "stmt-D", "holder-x", "entity", "subj-z", "pred-z", obj_hash, "believes");

    // Both edges use the same src 7-tuple -> same key.
    insert_null_key_edge(conn, "edge-1", "stmt-A", "stmt-B");
    insert_null_key_edge(conn, "edge-2", "stmt-C", "stmt-D");

    EXPECT_EQ(2, count_rows(conn,
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));

    const TickStats s = tick_one_batch(conn, 100);

    EXPECT_EQ(2, s.rows_processed);
    // One backfilled, one deduped.
    EXPECT_EQ(1, s.rows_backfilled);
    EXPECT_EQ(1, s.rows_deduped);
    // Only one edge remains.
    EXPECT_EQ(1, count_rows(conn,
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
    // No NULL-key edges remain.
    EXPECT_EQ(0, count_rows(conn,
        "SELECT COUNT(*) FROM statement_edges "
        "WHERE edge_kind='conflicts_with' AND canonical_conflict_key IS NULL"));
}

// ── Test 5: idempotent after completion ─────────────────────────────────────

TEST(ConflictKeyBackfill, IdempotentAfterCompletion) {
    auto a = open_fresh();
    auto& conn = a->connection();

    // First tick completes (empty DB).
    {
        const TickStats s1 = tick_one_batch(conn, 100);
        EXPECT_TRUE(s1.completed_now);
        EXPECT_TRUE(is_complete(conn));
    }

    // Subsequent ticks return early with zero stats.
    for (int i = 0; i < 3; ++i) {
        const TickStats s = tick_one_batch(conn, 100);
        EXPECT_EQ(0, s.rows_processed);
        EXPECT_EQ(0, s.rows_backfilled);
        EXPECT_EQ(0, s.rows_deduped);
        EXPECT_FALSE(s.completed_now);  // already complete; not "newly" completed
        EXPECT_TRUE(is_complete(conn));
    }
}

// ── Test 6: is_complete true after completion ────────────────────────────────

TEST(ConflictKeyBackfill, IsCompleteTrueAfterCompletion) {
    auto a = open_fresh();
    auto& conn = a->connection();

    EXPECT_FALSE(is_complete(conn));
    tick_one_batch(conn, 100);
    EXPECT_TRUE(is_complete(conn));
}

}  // namespace
}  // namespace starling::bus::conflict_key_backfill
