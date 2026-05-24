#include "starling/retrieval/basic_retriever.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

namespace starling::retrieval {
namespace {

// Direct-insert helper that bypasses Bus.write — these tests exercise filter
// logic, not write-path validation. The schema is the 38-field statements
// table from migration 0001; we fix everything we don't care about to
// reasonable defaults and accept the variants used by the tests.
//
// Bind NULL for valid_from / valid_to when the caller passes "".
void insert_stmt(persistence::SqliteAdapter& a,
                 const std::string& id,
                 const std::string& tenant_id,
                 const std::string& holder_id,
                 const std::string& subject_id,
                 const std::string& predicate,
                 const std::string& object_value,
                 const std::string& consolidation_state,
                 const std::string& review_status,
                 const std::string& valid_from,
                 const std::string& valid_to,
                 const std::string& evidence_json = "[]") {
    static constexpr const char* kInsertSql =
        "INSERT INTO statements("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate,"
        "  object_kind, object_value, canonical_object_hash,"
        "  canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at,"
        "  valid_from, valid_to,"
        "  salience, affect_json, activation, last_accessed,"
        "  provenance, evidence_json, source_spans_json, perceived_by_json,"
        "  consolidation_state, review_status,"
        "  created_at, updated_at"
        ") VALUES ("
        "  ?, ?, ?, 'first_person',"
        "  'cognizer', ?, ?,"
        "  'str', ?, 'hash-x',"
        "  'v1',"
        "  'believes', 'pos', 0.9, '2026-04-15T00:00:00Z',"
        "  ?, ?,"
        "  0.5, '{}', 0.5, '2026-04-15T00:00:00Z',"
        "  'user_input', ?, '[]', '[]',"
        "  ?, ?,"
        "  '2026-04-15T00:00:00Z', '2026-04-15T00:00:00Z'"
        ")";

    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    ASSERT_EQ(sqlite3_prepare_v2(db, kInsertSql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h{raw};

    int i = 1;
    sqlite3_bind_text(raw, i++, id.c_str(),                  -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, tenant_id.c_str(),           -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, holder_id.c_str(),           -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, subject_id.c_str(),          -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, predicate.c_str(),           -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, object_value.c_str(),        -1, SQLITE_TRANSIENT);
    if (valid_from.empty()) {
        sqlite3_bind_null(raw, i++);
    } else {
        sqlite3_bind_text(raw, i++, valid_from.c_str(),      -1, SQLITE_TRANSIENT);
    }
    if (valid_to.empty()) {
        sqlite3_bind_null(raw, i++);
    } else {
        sqlite3_bind_text(raw, i++, valid_to.c_str(),        -1, SQLITE_TRANSIENT);
    }
    sqlite3_bind_text(raw, i++, evidence_json.c_str(),       -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, consolidation_state.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, review_status.c_str(),       -1, SQLITE_TRANSIENT);

    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(db);
}

BasicRetrieverParams params_at(const std::string& as_of) {
    BasicRetrieverParams p;
    p.tenant_id      = "t1";
    p.holder_id      = "alice";
    p.intent         = QueryIntent::FACT_LOOKUP;
    p.subject_id     = "bob";
    p.predicate      = "responsible_for";
    p.as_of_iso8601  = as_of;
    p.trace_id       = "trace-x";
    p.query_id       = "query-x";
    return p;
}

class BasicRetrieverFilterTest : public ::testing::Test {
 protected:
    void SetUp() override {
        adapter_ = persistence::SqliteAdapter::open(":memory:");
        persistence::MigrationRunner(adapter_->connection().raw())
            .migrate_to_latest();
    }
    std::unique_ptr<persistence::SqliteAdapter> adapter_;
};

TEST_F(BasicRetrieverFilterTest, ExcludesVolatile) {
    insert_stmt(*adapter_, "id-vol", "t1", "alice", "bob", "responsible_for",
                "auth", "volatile", "approved", "", "");
    insert_stmt(*adapter_, "id-cons", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");

    BasicRetriever r(*adapter_);
    auto result = r.run(params_at("2026-04-15T00:00:00Z"));
    ASSERT_EQ(result.rows.size(), 1u);
    EXPECT_EQ(result.rows[0].id, "id-cons");
    EXPECT_EQ(result.receipt.sufficiency_status, Sufficiency::SUFFICIENT);
}

TEST_F(BasicRetrieverFilterTest, ExcludesRejectedAndPending) {
    insert_stmt(*adapter_, "id-rej", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "rejected", "", "");
    insert_stmt(*adapter_, "id-pend", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "pending_review", "", "");
    insert_stmt(*adapter_, "id-app", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");

    BasicRetriever r(*adapter_);
    auto result = r.run(params_at("2026-04-15T00:00:00Z"));
    ASSERT_EQ(result.rows.size(), 1u);
    EXPECT_EQ(result.rows[0].id, "id-app");
}

TEST_F(BasicRetrieverFilterTest, IncludesArchived) {
    insert_stmt(*adapter_, "id-arch", "t1", "alice", "bob", "responsible_for",
                "auth", "archived", "approved", "", "");

    BasicRetriever r(*adapter_);
    auto result = r.run(params_at("2026-04-15T00:00:00Z"));
    ASSERT_EQ(result.rows.size(), 1u);
    EXPECT_EQ(result.rows[0].id, "id-arch");
    EXPECT_EQ(result.rows[0].consolidation_state, "archived");
}

TEST_F(BasicRetrieverFilterTest, ExcludesByValidToBoundary) {
    // The SELECT uses `valid_to > as_of`, so valid_to == as_of must be
    // EXCLUDED (closed-open interval). One second before must be INCLUDED.
    insert_stmt(*adapter_, "id-eq",     "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved",
                /*valid_from=*/"", /*valid_to=*/"2026-04-15T00:00:00Z");
    insert_stmt(*adapter_, "id-before", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved",
                /*valid_from=*/"", /*valid_to=*/"2026-04-15T00:00:01Z");

    BasicRetriever r(*adapter_);
    auto result = r.run(params_at("2026-04-15T00:00:00Z"));
    ASSERT_EQ(result.rows.size(), 1u);
    EXPECT_EQ(result.rows[0].id, "id-before");
}

TEST_F(BasicRetrieverFilterTest, ExcludesBeforeValidFrom) {
    // The SELECT uses `valid_from <= as_of`, so as_of == valid_from is
    // INCLUDED, and as_of < valid_from is EXCLUDED.
    insert_stmt(*adapter_, "id-future", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved",
                /*valid_from=*/"2026-04-15T01:00:00Z", /*valid_to=*/"");
    insert_stmt(*adapter_, "id-equal",  "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved",
                /*valid_from=*/"2026-04-15T00:00:00Z", /*valid_to=*/"");

    BasicRetriever r(*adapter_);
    auto result = r.run(params_at("2026-04-15T00:00:00Z"));
    ASSERT_EQ(result.rows.size(), 1u);
    EXPECT_EQ(result.rows[0].id, "id-equal");
}

TEST_F(BasicRetrieverFilterTest, IsolatesAcrossTenant) {
    // Same id+holder under tenant t2 must NOT leak into a t1 query —
    // TC-NEG-TENANT happy-path mirror at the row level.
    insert_stmt(*adapter_, "id-cross", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");
    insert_stmt(*adapter_, "id-cross", "t2", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");

    BasicRetriever r(*adapter_);
    auto result = r.run(params_at("2026-04-15T00:00:00Z"));
    ASSERT_EQ(result.rows.size(), 1u);
    EXPECT_EQ(result.rows[0].tenant_id, "t1");
}

}  // namespace
}  // namespace starling::retrieval
