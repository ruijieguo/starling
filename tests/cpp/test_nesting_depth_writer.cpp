#include "starling/tom/nesting_depth_writer.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <string>

namespace starling::tom {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

extractor::ExtractedStatement make_stmt(
        const std::string& object_kind,
        const std::string& object_value) {
    extractor::ExtractedStatement s;
    s.holder_id             = "alice";
    s.holder_tenant_id      = "t1";
    s.holder_perspective    = schema::Perspective::FIRST_PERSON;
    s.subject_kind          = "cognizer";
    s.subject_id            = "alice";
    s.predicate             = "knows";
    s.object_kind           = object_kind;
    s.object_value          = object_value;
    s.canonical_object_hash = "hash-x";
    s.modality              = schema::Modality::BELIEVES;
    s.polarity              = schema::Polarity::POS;
    s.confidence            = 0.9;
    s.observed_at           = "2026-05-26T00:00:00Z";
    s.chunk_index           = 0;
    s.source_hash           = "src";
    s.perceived_by          = {"alice"};
    s.provenance            = schema::StatementProvenance::USER_INPUT;
    s.review_status         = schema::ReviewStatus::APPROVED;
    return s;
}

// Directly INSERT a statement row with a given id and nesting_depth,
// bypassing StatementWriter (so we can set up the parent chain without
// triggering the writer's own nesting_depth logic).
void insert_raw_statement(persistence::Connection& conn,
                          const std::string& id,
                          int nesting_depth) {
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
        "  ?,  'default', 'alice', 'first_person',"
        "  'cognizer', 'alice', 'knows', 'str', 'math',"
        "  'hash-x', 'v1',"
        "  'believes', 'pos', 0.9, '2026-05-26T00:00:00Z',"
        "  0.0, '{}', 0.0, '2026-05-26T00:00:00Z',"
        "  'user_input', '[]', '[]', '[]',"
        "  'volatile', 'approved',"
        "  '[]', 0,"
        "  ?,"
        "  '2026-05-26T00:00:00Z', '2026-05-26T00:00:00Z'"
        ")";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h(raw);
    sqlite3_bind_text(h.get(), 1, id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(h.get(), 2, nesting_depth);
    ASSERT_EQ(sqlite3_step(h.get()), SQLITE_DONE) << sqlite3_errmsg(db);
}

}  // namespace

TEST(NestingDepthWriter, NonStatementObjectKindReturnsZero) {
    auto a = make_adapter();
    auto& conn = a->connection();

    auto s = make_stmt("str", "some-value");
    EXPECT_EQ(nesting_depth_writer::compute_nesting_depth(conn, s), 0);
}

TEST(NestingDepthWriter, NonStatementVariousKindsReturnZero) {
    auto a = make_adapter();
    auto& conn = a->connection();

    for (const auto& kind : {"bool", "int", "float", "datetime", "cognizer", "entity"}) {
        auto s = make_stmt(kind, "v");
        EXPECT_EQ(nesting_depth_writer::compute_nesting_depth(conn, s), 0)
            << "Expected 0 for object_kind=" << kind;
    }
}

TEST(NestingDepthWriter, StatementObjectIncreasesParentDepthByOne) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert parent with nesting_depth=0.
    const std::string parent_id = "parent-stmt-001";
    insert_raw_statement(conn, parent_id, 0);

    auto s = make_stmt("statement", parent_id);
    EXPECT_EQ(nesting_depth_writer::compute_nesting_depth(conn, s), 1);
}

TEST(NestingDepthWriter, GrandchildDepthTwo) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // depth-0 root, depth-1 middle, child should compute 2.
    const std::string root_id   = "root-stmt-001";
    const std::string middle_id = "middle-stmt-001";
    insert_raw_statement(conn, root_id, 0);
    insert_raw_statement(conn, middle_id, 1);

    // Child points at middle (nesting_depth=1) → should return 2.
    auto s = make_stmt("statement", middle_id);
    EXPECT_EQ(nesting_depth_writer::compute_nesting_depth(conn, s), 2);
}

TEST(NestingDepthWriter, DepthThreeThrowsOverflow) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Insert a statement already at depth 2 as the "parent".
    const std::string depth2_id = "depth2-stmt-001";
    insert_raw_statement(conn, depth2_id, 2);

    // Child would be depth 3 — must throw NestingDepthOverflow.
    auto s = make_stmt("statement", depth2_id);
    EXPECT_THROW(
        nesting_depth_writer::compute_nesting_depth(conn, s),
        NestingDepthOverflow);
}

TEST(NestingDepthWriter, DepthThreeOverflowHasCorrectComputedDepth) {
    auto a = make_adapter();
    auto& conn = a->connection();

    const std::string depth2_id = "depth2-stmt-002";
    insert_raw_statement(conn, depth2_id, 2);

    auto s = make_stmt("statement", depth2_id);
    try {
        nesting_depth_writer::compute_nesting_depth(conn, s);
        FAIL() << "Expected NestingDepthOverflow";
    } catch (const NestingDepthOverflow& e) {
        EXPECT_EQ(e.computed_depth, 3);
    }
}

TEST(NestingDepthWriter, MissingParentThrows) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // No parent row inserted — must throw runtime_error.
    auto s = make_stmt("statement", "nonexistent-stmt-id");
    EXPECT_THROW(
        nesting_depth_writer::compute_nesting_depth(conn, s),
        std::runtime_error);
}

}  // namespace starling::tom
