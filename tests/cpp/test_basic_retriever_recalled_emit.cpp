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

// Direct-insert helper. Copy-pasted from test_basic_retriever_filter_predicates.cpp
// because the helpers are small and these tests are independent — refactoring
// into a shared header would be scope creep for this task.
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

BasicRetrieverParams std_params(const std::string& query_id = "q-1") {
    BasicRetrieverParams p;
    p.tenant_id      = "t1";
    p.holder_id      = "alice";
    p.intent         = QueryIntent::FACT_LOOKUP;
    p.subject_id     = "bob";
    p.predicate      = "responsible_for";
    p.as_of_iso8601  = "2026-04-15T00:00:00Z";
    p.trace_id       = "trace-x";
    p.query_id       = query_id;
    return p;
}

int count_recalled_events(persistence::SqliteAdapter& a) {
    sqlite3* db = a.connection().raw();
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(db,
        "SELECT COUNT(*) FROM bus_events WHERE event_type = 'statement.recalled'",
        -1, &raw, nullptr), SQLITE_OK);
    persistence::StmtHandle h{raw};
    EXPECT_EQ(sqlite3_step(raw), SQLITE_ROW);
    return sqlite3_column_int(raw, 0);
}

class BasicRetrieverRecalledEmitTest : public ::testing::Test {
 protected:
    void SetUp() override {
        adapter_ = persistence::SqliteAdapter::open(":memory:");
        persistence::MigrationRunner(adapter_->connection().raw())
            .migrate_to_latest();
    }
    std::unique_ptr<persistence::SqliteAdapter> adapter_;
};

TEST_F(BasicRetrieverRecalledEmitTest, OneEventPerReturnedRow) {
    insert_stmt(*adapter_, "s-1", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");
    insert_stmt(*adapter_, "s-2", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");

    BasicRetriever r(*adapter_);
    auto result = r.run(std_params());
    ASSERT_EQ(result.rows.size(), 2u);

    EXPECT_EQ(count_recalled_events(*adapter_), 2);
}

TEST_F(BasicRetrieverRecalledEmitTest, NoEventsWhenEmpty) {
    BasicRetriever r(*adapter_);
    auto result = r.run(std_params());
    ASSERT_EQ(result.rows.size(), 0u);

    EXPECT_EQ(count_recalled_events(*adapter_), 0);
}

TEST_F(BasicRetrieverRecalledEmitTest, IdempotentWithin2sWindow) {
    insert_stmt(*adapter_, "s-1", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");

    BasicRetriever r(*adapter_);
    // Two retrieves with the SAME query_id back-to-back. Second emit's
    // idempotency_key collides on the 2s window bucket -> UNIQUE-debounced.
    auto r1 = r.run(std_params("q-1"));
    auto r2 = r.run(std_params("q-1"));
    ASSERT_EQ(r1.rows.size(), 1u);
    ASSERT_EQ(r2.rows.size(), 1u);

    EXPECT_EQ(count_recalled_events(*adapter_), 1);
}

TEST_F(BasicRetrieverRecalledEmitTest, DistinctQueryIdsAreDistinctEvents) {
    insert_stmt(*adapter_, "s-1", "t1", "alice", "bob", "responsible_for",
                "auth", "consolidated", "approved", "", "");

    BasicRetriever r(*adapter_);
    // Different query_id -> different causation_root -> different
    // idempotency_key -> both events land in bus_events.
    auto r1 = r.run(std_params("q-1"));
    auto r2 = r.run(std_params("q-2"));
    ASSERT_EQ(r1.rows.size(), 1u);
    ASSERT_EQ(r2.rows.size(), 1u);

    EXPECT_EQ(count_recalled_events(*adapter_), 2);
}

}  // namespace
}  // namespace starling::retrieval
