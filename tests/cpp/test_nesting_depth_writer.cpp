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
                          int nesting_depth,
                          const std::string& tenant_id = "t1") {
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
        "  ?,  ?, 'alice', 'first_person',"
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
    sqlite3_bind_text(h.get(), 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(h.get(), 3, nesting_depth);
    ASSERT_EQ(sqlite3_step(h.get()), SQLITE_DONE) << sqlite3_errmsg(db);
}

// Directly INSERT a NESTED statement row (object_kind='statement') whose
// object_value points at `points_at`. Used to build real ancestor chains and
// cycles for the ancestor-walk depth computation.
void insert_nested_statement(persistence::Connection& conn,
                             const std::string& id,
                             const std::string& points_at,
                             int nesting_depth,
                             const std::string& tenant_id = "t1") {
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
        "  ?,  ?, 'alice', 'first_person',"
        "  'cognizer', 'alice', 'knows', 'statement', ?,"
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
    sqlite3_bind_text(h.get(), 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 3, points_at.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(h.get(), 4, nesting_depth);
    ASSERT_EQ(sqlite3_step(h.get()), SQLITE_DONE) << sqlite3_errmsg(db);
}

// Build a flat leaf "L0" (object_kind='str') then nested rows L1..LN each
// pointing at the previous, so that Lk has ancestor-walk depth k. Returns the
// id of the deepest row ("LN").
std::string seed_chain(persistence::Connection& conn, int n) {
    insert_raw_statement(conn, "L0", /*nesting_depth=*/0);
    for (int i = 1; i <= n; ++i) {
        insert_nested_statement(conn, "L" + std::to_string(i),
                                /*points_at=*/"L" + std::to_string(i - 1),
                                /*nesting_depth=*/i);
    }
    return "L" + std::to_string(n);
}

// Insert two nested rows whose object_value point at each other, forming a
// cycle (a -> b -> a).
void seed_cyclic_pair(persistence::Connection& conn,
                      const std::string& a,
                      const std::string& b) {
    insert_nested_statement(conn, a, /*points_at=*/b, /*nesting_depth=*/0);
    insert_nested_statement(conn, b, /*points_at=*/a, /*nesting_depth=*/0);
}

// Build a fresh (not-yet-persisted) nested ExtractedStatement that points at
// `points_at` (object_kind='statement', object_value=points_at).
extractor::ExtractedStatement make_nested_stmt(const std::string& points_at) {
    return make_stmt("statement", points_at);
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

    // Real chain: flat str leaf root, nested middle pointing at root.
    const std::string root_id   = "root-stmt-001";
    const std::string middle_id = "middle-stmt-001";
    insert_raw_statement(conn, root_id, 0);
    insert_nested_statement(conn, middle_id, /*points_at=*/root_id,
                            /*nesting_depth=*/1);

    // Child points at middle → walk is child→middle→root(leaf) → depth 2.
    auto s = make_stmt("statement", middle_id);
    EXPECT_EQ(nesting_depth_writer::compute_nesting_depth(conn, s), 2);
}

TEST(NestingDepthWriter, NestingCycleTypeCarriesId) {
    starling::tom::NestingCycle e("stmt-42");
    EXPECT_EQ(e.cycle_id, "stmt-42");
    EXPECT_NE(std::string(e.what()).find("cycle"), std::string::npos);
}

TEST(NestingDepthWriter, AcceptsDepthThreeFourFiveUnderDefaultCeiling) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Flat leaf L0 + nested L1..L4 (L4 has ancestor-walk depth 4).
    const std::string deepest = seed_chain(conn, /*n=*/4);
    EXPECT_EQ(deepest, "L4");

    // A fresh statement pointing at the depth-4 row computes depth 5,
    // accepted under the default soft ceiling (32).
    auto s = make_nested_stmt(deepest);
    EXPECT_EQ(nesting_depth_writer::compute_nesting_depth(conn, s), 5);
}

TEST(NestingDepthWriter, SoftCeilingOverflowThrows) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Chain L0(leaf) <- L1 <- L2; a fresh stmt onto L2 would compute depth 3.
    const std::string deepest = seed_chain(conn, /*n=*/2);
    auto s = make_nested_stmt(deepest);

    // Accepted under default ceiling...
    EXPECT_EQ(nesting_depth_writer::compute_nesting_depth(conn, s), 3);
    // ...but rejected when max_depth = 2.
    EXPECT_THROW(
        nesting_depth_writer::compute_nesting_depth(conn, s, /*max_depth=*/2),
        starling::tom::NestingDepthOverflow);
}

TEST(NestingDepthWriter, SoftCeilingOverflowCarriesComputedDepth) {
    auto a = make_adapter();
    auto& conn = a->connection();

    const std::string deepest = seed_chain(conn, /*n=*/2);
    auto s = make_nested_stmt(deepest);
    try {
        nesting_depth_writer::compute_nesting_depth(conn, s, /*max_depth=*/2);
        FAIL() << "Expected NestingDepthOverflow";
    } catch (const NestingDepthOverflow& e) {
        EXPECT_EQ(e.computed_depth, 3);
    }
}

TEST(NestingDepthWriter, CycleInExistingChainThrows) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // Two nested rows whose object_value point at each other.
    seed_cyclic_pair(conn, "C1", "C2");

    // A fresh stmt pointing at C1 walks C1 -> C2 -> C1 -> cycle.
    auto s = make_nested_stmt("C1");
    EXPECT_THROW(
        nesting_depth_writer::compute_nesting_depth(conn, s),
        starling::tom::NestingCycle);
}

TEST(NestingDepthWriter, UnboundedCeilingAcceptsDeepChain) {
    auto a = make_adapter();
    auto& conn = a->connection();

    // A chain deeper than the default ceiling is accepted when max_depth=0.
    const std::string deepest = seed_chain(conn, /*n=*/40);
    auto s = make_nested_stmt(deepest);
    EXPECT_EQ(
        nesting_depth_writer::compute_nesting_depth(conn, s, /*max_depth=*/0),
        41);
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

TEST(NestingDepthWriter, SameStatementIdInOtherTenantDoesNotSatisfyLookup) {
    auto a = make_adapter();
    auto& conn = a->connection();

    const std::string parent_id = "shared-parent";
    insert_raw_statement(conn, parent_id, 0, "other-tenant");

    auto s = make_stmt("statement", parent_id);
    s.holder_tenant_id = "t1";
    EXPECT_THROW(
        nesting_depth_writer::compute_nesting_depth(conn, s),
        std::runtime_error);
}

}  // namespace starling::tom
