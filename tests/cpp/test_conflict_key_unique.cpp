// Tests for insert_statement_edge canonical_conflict_key UNIQUE dedup behaviour.
// Per spec §8.4:
//   - Two conflicts_with edges with same canonical_conflict_key → second is
//     noop (no exception, no second row).
//   - Two conflicts_with edges with different canonical_conflict_key → both
//     rows persist.
//   - supersedes edges with NULL canonical_conflict_key → all rows persist
//     (partial UNIQUE index excludes NULL).

#include "starling/bus/bus.hpp"
#include "starling/bus/conflict_probe.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <optional>
#include <string>

namespace starling::bus {
namespace {

using starling::extractor::ExtractedStatement;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;

// Open an in-memory DB migrated to latest schema.
std::unique_ptr<SqliteAdapter> open_fresh() {
    auto a = SqliteAdapter::open(":memory:");
    MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Count rows matching a SQL expression (must return a single integer).
int count_rows(Connection& conn, const std::string& sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr));
    StmtHandle h(raw);
    EXPECT_EQ(SQLITE_ROW, sqlite3_step(h.get()));
    return sqlite3_column_int(h.get(), 0);
}

// Insert a minimal statement row so that statement_edges FK constraints pass.
// Uses direct INSERT (bypasses StatementWriter) to keep the test self-contained.
void insert_stmt_row(Connection& conn, const std::string& id,
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
    sqlite3_bind_text(h.get(), i++, id.c_str(),         -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, tenant_id.c_str(),  -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "holder-x",         -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "first_person",      -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "entity",            -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "subj-x",            -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "knows",             -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "str",               -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "val-x",             -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++,
        "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222",
        -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "v1",                -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "believes",          -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "pos",               -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 0.8);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 0.5);
    sqlite3_bind_text(h.get(), i++, "{}",                -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 1.0);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "user_input",        -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "consolidated",      -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "approved",          -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "2026-01-01T00:00:00Z", -1, SQLITE_STATIC);
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
}

// ---- Helper: call the private insert_statement_edge via Bus by doing a
// direct SQL insert that mirrors what insert_statement_edge does, but using
// the same parameters, so we can test the UNIQUE constraint logic end-to-end
// through Bus::write_impl.  We can't call insert_statement_edge directly
// because it lives in an anonymous namespace.  Instead, we drive the test
// through Bus::write which naturally invokes insert_statement_edge.
//
// The tests below use two ExtractedStatements arranged to produce a
// PartialOverlap conflict (both below θ_severe=0.6 so severity is clamped).
// The same canonical_conflict_key will be produced for both because the
// 7-tuple {tenant, holder, subject_kind, subject_id, predicate, object_kind,
// canonical_object_hash} is identical for all statements in make_stmt().

ExtractedStatement make_stmt(
    const std::string& predicate = "responsible_for",
    const std::string& object_value = "auth",
    const std::string& polarity = "pos") {
    ExtractedStatement s;
    s.holder_id             = "cog-self";
    s.holder_tenant_id      = "default";
    s.holder_perspective    = schema::Perspective::FIRST_PERSON;
    s.subject_kind          = "cognizer";
    s.subject_id            = "cog-bob";
    s.predicate             = predicate;
    s.object_kind           = "str";
    s.object_value          = object_value;
    s.canonical_object_hash =
        "deadbeef01234567deadbeef01234567deadbeef01234567deadbeef01234567";
    s.modality              = schema::Modality::BELIEVES;
    s.polarity              = (polarity == "pos") ? schema::Polarity::POS
                                                  : schema::Polarity::NEG;
    // Confidence below θ_severe (0.6) → forces PartialOverlap classification.
    s.confidence            = 0.50;
    s.observed_at           = "2026-05-24T10:00:00Z";
    s.source_hash           = "fff";
    // Overlapping intervals to trigger PartialOverlap.
    s.valid_from            = std::string("2026-01-01T00:00:00Z");
    s.valid_to              = std::string("2026-12-31T00:00:00Z");
    return s;
}

// Insert an initial "old" statement (below θ_severe) via Bus::write, and then
// drive subsequent writes that trigger PartialOverlap path.
//
// TC1: same canonical_conflict_key → second insert_statement_edge is noop,
//      only one conflicts_with row in DB.
TEST(ConflictKeyUnique, SameKeySecondEdgeIsNoop) {
    auto a = open_fresh();
    Bus bus(*a);

    // Write S_old (pos, below θ_severe) — establishes the first row.
    bus.write(make_stmt("responsible_for", "auth", "pos"), "engram-old", "span-old",
              std::nullopt);
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements"));

    // S_new1 (neg) → PartialOverlap → one conflicts_with edge (canonical_conflict_key set).
    bus.write(make_stmt("responsible_for", "auth", "neg"), "engram-1", "span-1",
              std::nullopt);
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));

    // S_new2 (neg, same 7-tuple) → same canonical_conflict_key → UNIQUE hit → noop.
    // No exception must be thrown.
    EXPECT_NO_THROW(
        bus.write(make_stmt("responsible_for", "auth", "neg"), "engram-2", "span-2",
                  std::nullopt)
    );
    // Still only one conflicts_with edge.
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
}

// TC2: different canonical_conflict_key (different predicate) → both rows persist.
TEST(ConflictKeyUnique, DifferentKeysBothEdgesPersist) {
    auto a = open_fresh();
    Bus bus(*a);

    // Write S_old_1 (predicate=responsible_for, pos).
    bus.write(make_stmt("responsible_for", "auth", "pos"), "engram-old1", "span-old1",
              std::nullopt);
    // Write S_old_2 (predicate=manages, pos) — different subject so no conflict
    // between the two olds; but we need them consolidated to be probe candidates.
    bus.write(make_stmt("manages", "auth", "pos"), "engram-old2", "span-old2",
              std::nullopt);

    // Write S_new1 (neg vs responsible_for) → conflicts_with edge, key_A.
    bus.write(make_stmt("responsible_for", "auth", "neg"), "engram-1", "span-1",
              std::nullopt);
    // Write S_new2 (neg vs manages) → conflicts_with edge, key_B (different predicate
    // → different 7-tuple → different canonical_conflict_key).
    bus.write(make_stmt("manages", "auth", "neg"), "engram-2", "span-2",
              std::nullopt);

    // Each conflict target produced its own key so both edges should persist.
    // (We may have more than 2 if inter-S_new conflicts also fire, so we
    // assert >= 2.)
    EXPECT_GE(count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"), 2);
}

// TC3: supersedes edges with NULL canonical_conflict_key are NOT constrained —
//      multiple supersedes edges can coexist without triggering UNIQUE.
TEST(ConflictKeyUnique, SupersedesEdgesNullKeyUnlimited) {
    auto a = open_fresh();
    Bus bus(*a);

    // We can't easily drive two independent supersedes paths through Bus::write
    // because supersedes archives S_old.  Instead verify directly by inserting
    // two statement_edges rows with edge_kind='supersedes' and NULL
    // canonical_conflict_key via raw SQL — the partial UNIQUE index should not
    // fire because it only applies to conflicts_with edges.
    insert_stmt_row(a->connection(), "stmt-A");
    insert_stmt_row(a->connection(), "stmt-B");
    insert_stmt_row(a->connection(), "stmt-C");

    const char* ins =
        "INSERT INTO statement_edges"
        "(id, tenant_id, src_id, dst_id, edge_kind, canonical_conflict_key, created_at)"
        " VALUES (?, 'default', ?, ?, 'supersedes', NULL, '2026-01-01T00:00:00Z')";

    auto do_insert = [&](const char* eid, const char* src, const char* dst) {
        sqlite3_stmt* raw = nullptr;
        ASSERT_EQ(SQLITE_OK,
            sqlite3_prepare_v2(a->connection().raw(), ins, -1, &raw, nullptr));
        StmtHandle h(raw);
        sqlite3_bind_text(h.get(), 1, eid, -1, SQLITE_STATIC);
        sqlite3_bind_text(h.get(), 2, src, -1, SQLITE_STATIC);
        sqlite3_bind_text(h.get(), 3, dst, -1, SQLITE_STATIC);
        EXPECT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
    };

    do_insert("edge-AB", "stmt-A", "stmt-B");
    do_insert("edge-AC", "stmt-A", "stmt-C");

    // Both supersedes edges inserted without UNIQUE violation.
    EXPECT_EQ(2, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"));
}

}  // namespace
}  // namespace starling::bus
