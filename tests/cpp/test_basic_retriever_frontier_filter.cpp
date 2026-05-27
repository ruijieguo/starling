// tests/cpp/test_basic_retriever_frontier_filter.cpp
//
// C++ unit tests for the P2.a `apply_frontier_filter` param on BasicRetriever.
// Covers the four scenarios in 13_retrieval.md §"P2.a frontier filter":
//   1. DefaultFalsePreservesP1Behavior  — filter off => row visible w/o frontier setup
//   2. WithFrontierFilterFiltersOutNonVisible — filter on => row excluded when
//      evidence engram not in visible set
//   3. WithFrontierFilterIncludesVisible — filter on => row included when
//      evidence engram is in visible set (presence_log)
//   4. FrontierMaskedCountReflectsExcluded — 3 rows pre, 1 visible => masked == 2

#include "starling/retrieval/basic_retriever.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

namespace starling::retrieval {
namespace {

// ---- direct-insert helpers (same pattern as test_basic_retriever_filter_predicates) ----

void insert_stmt_with_evidence(persistence::SqliteAdapter& a,
                                const std::string& id,
                                const std::string& tenant_id,
                                const std::string& holder_id,
                                const std::string& subject_id,
                                const std::string& predicate,
                                const std::string& object_value,
                                const std::string& evidence_json) {
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
        "  NULL, NULL,"
        "  0.5, '{}', 0.5, '2026-04-15T00:00:00Z',"
        "  'user_input', ?, '[]', '[]',"
        "  'consolidated', 'approved',"
        "  '2026-04-15T00:00:00Z', '2026-04-15T00:00:00Z'"
        ")";

    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    ASSERT_EQ(sqlite3_prepare_v2(db, kInsertSql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h{raw};

    int i = 1;
    sqlite3_bind_text(raw, i++, id.c_str(),           -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, tenant_id.c_str(),    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, holder_id.c_str(),    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, subject_id.c_str(),   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, predicate.c_str(),    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, object_value.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, evidence_json.c_str(),-1, SQLITE_TRANSIENT);

    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(db);
}

// Insert a minimal engram row (needed so cognizer_presence_log FK passes).
// In-memory tests don't enforce FK by default, so this is belt-and-suspenders.
void insert_engram(persistence::SqliteAdapter& a,
                   const std::string& engram_id,
                   const std::string& tenant_id) {
    static constexpr const char* kSql =
        "INSERT INTO engrams("
        "  id, tenant_id, adapter_name, adapter_version, source_item_id, source_version,"
        "  chunk_index, source_kind, ingest_mode, privacy_class, retention_mode,"
        "  declared_transformations, byte_preserving, payload_bytes, redacted_content,"
        "  content_hash, content_hash_algorithm, created_at"
        ") VALUES ("
        "  ?, ?, 'test', '1.0', 'src1', 'v1',"
        "  0, 'user_input', 'whole_record', 'internal', 'audit_retain',"
        "  '', 1, '', NULL,"
        "  'abc123', 'sha256', '2026-04-15T00:00:00Z'"
        ")";
    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    if (sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr) != SQLITE_OK) return;
    persistence::StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, engram_id.c_str(),  -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, tenant_id.c_str(),  -1, SQLITE_TRANSIENT);
    sqlite3_step(raw);  // ignore error (FK not enforced in :memory:)
}

// Build a statement evidence_json that references a single engram_id.
std::string ev_json(const std::string& engram_id) {
    return "[{\"engram_ref\":\"" + engram_id + "\",\"content_hash\":\"abc\"}]";
}

BasicRetrieverParams base_params() {
    BasicRetrieverParams p;
    p.tenant_id      = "t1";
    p.holder_id      = "alice";
    p.intent         = QueryIntent::FACT_LOOKUP;
    p.subject_id     = "bob";
    p.predicate      = "knows";
    p.as_of_iso8601  = "2026-05-01T00:00:00Z";
    p.trace_id       = "tr";
    p.query_id       = "qid";
    return p;
}

class FrontierFilterTest : public ::testing::Test {
 protected:
    void SetUp() override {
        adapter_ = persistence::SqliteAdapter::open(":memory:");
        persistence::MigrationRunner(adapter_->connection().raw())
            .migrate_to_latest();
    }
    std::unique_ptr<persistence::SqliteAdapter> adapter_;
};

// 1. Default (apply_frontier_filter=false) returns a row even though
//    there is no frontier record for that engram.
TEST_F(FrontierFilterTest, DefaultFalsePreservesP1Behavior) {
    const std::string engram_id = "engram-no-frontier";
    insert_engram(*adapter_, engram_id, "t1");
    insert_stmt_with_evidence(*adapter_, "stmt-1", "t1", "alice",
                               "bob", "knows", "val",
                               ev_json(engram_id));

    BasicRetriever r(*adapter_);
    auto p = base_params();
    p.apply_frontier_filter = false;
    auto result = r.run(p);

    EXPECT_EQ(result.rows.size(), 1u) << "row should be visible without frontier filter";
    // frontier_applied entry must be "false"
    bool found = false;
    for (const auto& fa : result.receipt.filters_applied) {
        if (fa.name == "frontier_applied") {
            EXPECT_EQ(fa.value, "false");
            found = true;
        }
    }
    EXPECT_TRUE(found) << "frontier_applied must always appear in filters_applied";
    EXPECT_EQ(result.receipt.frontier_masked_count, 0);
}

// 2. apply_frontier_filter=true excludes a statement whose evidence engram
//    has no frontier record (not in visible set).
TEST_F(FrontierFilterTest, WithFrontierFilterFiltersOutNonVisible) {
    const std::string engram_id = "engram-invisible";
    insert_engram(*adapter_, engram_id, "t1");
    insert_stmt_with_evidence(*adapter_, "stmt-invisible", "t1", "alice",
                               "bob", "knows", "val",
                               ev_json(engram_id));
    // No frontier record => engram not in visible set.

    BasicRetriever r(*adapter_);
    auto p = base_params();
    p.apply_frontier_filter = true;
    auto result = r.run(p);

    EXPECT_EQ(result.rows.size(), 0u) << "row should be hidden by frontier filter";
    EXPECT_EQ(result.receipt.sufficiency_status, Sufficiency::MISSING_INFO);
    // frontier_applied must be "true"
    for (const auto& fa : result.receipt.filters_applied) {
        if (fa.name == "frontier_applied") {
            EXPECT_EQ(fa.value, "true");
        }
    }
}

// 3. apply_frontier_filter=true includes a statement whose evidence engram
//    IS recorded in cognizer_presence_log.
TEST_F(FrontierFilterTest, WithFrontierFilterIncludesVisible) {
    const std::string engram_id = "engram-visible";
    insert_engram(*adapter_, engram_id, "t1");
    insert_stmt_with_evidence(*adapter_, "stmt-visible", "t1", "alice",
                               "bob", "knows", "val",
                               ev_json(engram_id));

    // Record presence: alice saw engram-visible before as_of.
    cognizer::KnowledgeFrontier frontier(*adapter_);
    frontier.record_presence_from_statement(
        "t1", {"alice"}, engram_id,
        "2026-04-01T00:00:00Z",
        adapter_->connection());

    BasicRetriever r(*adapter_);
    auto p = base_params();
    p.apply_frontier_filter = true;
    auto result = r.run(p);

    EXPECT_EQ(result.rows.size(), 1u) << "row with visible engram should be included";
    EXPECT_EQ(result.receipt.frontier_masked_count, 0);
}

// 4. 3 statements, only 1 has a visible engram => frontier_masked_count == 2.
TEST_F(FrontierFilterTest, FrontierMaskedCountReflectsExcluded) {
    insert_engram(*adapter_, "e-vis", "t1");
    insert_engram(*adapter_, "e-hid1", "t1");
    insert_engram(*adapter_, "e-hid2", "t1");

    insert_stmt_with_evidence(*adapter_, "s1", "t1", "alice",
                               "bob", "knows", "v1", ev_json("e-vis"));
    insert_stmt_with_evidence(*adapter_, "s2", "t1", "alice",
                               "bob", "knows", "v2", ev_json("e-hid1"));
    insert_stmt_with_evidence(*adapter_, "s3", "t1", "alice",
                               "bob", "knows", "v3", ev_json("e-hid2"));

    // Only e-vis is visible (via presence_log).
    cognizer::KnowledgeFrontier frontier(*adapter_);
    frontier.record_presence_from_statement(
        "t1", {"alice"}, "e-vis",
        "2026-04-01T00:00:00Z",
        adapter_->connection());

    BasicRetriever r(*adapter_);
    auto p = base_params();
    p.apply_frontier_filter = true;
    auto result = r.run(p);

    EXPECT_EQ(result.rows.size(), 1u);
    EXPECT_EQ(result.receipt.frontier_masked_count, 2)
        << "two rows should be masked by frontier filter";

    // filters_applied["frontier_masked_count"] should also reflect this.
    for (const auto& fa : result.receipt.filters_applied) {
        if (fa.name == "frontier_masked_count") {
            EXPECT_EQ(fa.value, "2");
        }
    }
}

}  // namespace
}  // namespace starling::retrieval
