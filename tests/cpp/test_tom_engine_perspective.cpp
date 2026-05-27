#include "starling/tom/tom_engine.hpp"

#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <algorithm>
#include <memory>
#include <string>

using starling::cognizer::CognizerHub;
using starling::cognizer::KnowledgeFrontier;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;
using starling::tom::ToMEngine;

namespace {

// Direct-insert helper: bypasses Bus.write for filter logic tests.
// Matches the schema used by test_basic_retriever_filter_predicates.cpp.
void insert_stmt(SqliteAdapter& a,
                 const std::string& id,
                 const std::string& tenant_id,
                 const std::string& holder_id,
                 const std::string& consolidation_state,
                 const std::string& review_status,
                 const std::string& valid_from = "",
                 const std::string& valid_to   = "") {
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
        "  'cognizer', 'subject-x', 'knows',"
        "  'str', 'value-x', 'hash-x',"
        "  'v1',"
        "  'believes', 'pos', 0.9, '2026-05-01T00:00:00Z',"
        "  ?, ?,"
        "  0.5, '{}', 0.5, '2026-05-01T00:00:00Z',"
        "  'user_input', '[]', '[]', '[]',"
        "  ?, ?,"
        "  '2026-05-01T00:00:00Z', '2026-05-01T00:00:00Z'"
        ")";

    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    ASSERT_EQ(sqlite3_prepare_v2(db, kInsertSql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    StmtHandle h{raw};

    int i = 1;
    sqlite3_bind_text(raw, i++, id.c_str(),                   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, tenant_id.c_str(),            -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, holder_id.c_str(),            -1, SQLITE_TRANSIENT);
    // valid_from
    if (valid_from.empty()) sqlite3_bind_null(raw, i++);
    else sqlite3_bind_text(raw, i++, valid_from.c_str(),      -1, SQLITE_TRANSIENT);
    // valid_to
    if (valid_to.empty()) sqlite3_bind_null(raw, i++);
    else sqlite3_bind_text(raw, i++, valid_to.c_str(),        -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, consolidation_state.c_str(),  -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, i++, review_status.c_str(),        -1, SQLITE_TRANSIENT);

    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(db);
}

class ToMEngineTest : public ::testing::Test {
protected:
    void SetUp() override {
        adapter_  = SqliteAdapter::open(":memory:");
        hub_      = std::make_unique<CognizerHub>(*adapter_);
        frontier_ = std::make_unique<KnowledgeFrontier>(*adapter_);
    }

    std::unique_ptr<SqliteAdapter>     adapter_;
    std::unique_ptr<CognizerHub>       hub_;
    std::unique_ptr<KnowledgeFrontier> frontier_;
};

// TC-TOM-EMPTY: fresh DB → all Context fields are empty.
TEST_F(ToMEngineTest, EmptyWhenNoData) {
    ToMEngine engine(*adapter_, *hub_, *frontier_);
    auto ctx = engine.perspective_take(
        "alice", "default", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(ctx.visible_engram_ids.empty());
    EXPECT_TRUE(ctx.target_beliefs.empty());
    EXPECT_TRUE(ctx.cg.empty());
}

// TC-TOM-VISIBLE: presence_log recorded via KnowledgeFrontier → appears in
// visible_engram_ids.
TEST_F(ToMEngineTest, VisibleEngramsFromFrontier) {
    frontier_->record_presence_from_statement(
        "default", {"alice"}, "engram-vis-1",
        "2026-05-26T09:00:00Z", adapter_->connection());
    frontier_->record_presence_from_statement(
        "default", {"alice"}, "engram-vis-2",
        "2026-05-26T09:30:00Z", adapter_->connection());

    ToMEngine engine(*adapter_, *hub_, *frontier_);
    auto ctx = engine.perspective_take(
        "alice", "default", "2026-05-26T10:00:00Z");

    EXPECT_EQ(ctx.visible_engram_ids.size(), 2u);
    // Order not guaranteed (comes from unordered_set) — check both IDs present.
    auto& v = ctx.visible_engram_ids;
    EXPECT_TRUE(std::find(v.begin(), v.end(), "engram-vis-1") != v.end());
    EXPECT_TRUE(std::find(v.begin(), v.end(), "engram-vis-2") != v.end());
}

// TC-TOM-BELIEFS: only statements with holder_id == target are returned.
TEST_F(ToMEngineTest, TargetBeliefsFromHolderQuery) {
    // alice's consolidated statement
    insert_stmt(*adapter_, "stmt-alice-1", "default", "alice",
                "consolidated", "approved");
    // bob's consolidated statement — should NOT appear for alice
    insert_stmt(*adapter_, "stmt-bob-1", "default", "bob",
                "consolidated", "approved");

    ToMEngine engine(*adapter_, *hub_, *frontier_);
    auto ctx = engine.perspective_take(
        "alice", "default", "2026-05-26T10:00:00Z");

    ASSERT_EQ(ctx.target_beliefs.size(), 1u);
    EXPECT_EQ(ctx.target_beliefs[0].id,        "stmt-alice-1");
    EXPECT_EQ(ctx.target_beliefs[0].holder_id, "alice");
}

// TC-TOM-CG-EMPTY: common ground always returns [] in P2.a.
TEST_F(ToMEngineTest, CommonGroundAlwaysEmptyInP2a) {
    ToMEngine engine(*adapter_, *hub_, *frontier_);
    auto ctx = engine.perspective_take(
        "alice", "default", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(ctx.cg.empty())
        << "P2.a spec §7.2: common_ground stub must return []";
}

// TC-TOM-AS-OF: statement with valid_from AFTER as_of must not appear.
TEST_F(ToMEngineTest, AsOfFiltersTimeAnchoredBeliefs) {
    // valid_from is in the future relative to our as_of
    insert_stmt(*adapter_, "stmt-future", "default", "alice",
                "consolidated", "approved",
                /*valid_from=*/"2026-05-27T00:00:00Z",
                /*valid_to=*/"");

    ToMEngine engine(*adapter_, *hub_, *frontier_);
    // Query as of a timestamp before valid_from
    auto ctx = engine.perspective_take(
        "alice", "default", "2026-05-26T10:00:00Z");

    EXPECT_TRUE(ctx.target_beliefs.empty())
        << "statement valid_from > as_of must be excluded";
}

// TC-TOM-TENANT: engrams recorded in tenant-a must not appear in tenant-b.
TEST_F(ToMEngineTest, TenantIsolation) {
    frontier_->record_presence_from_statement(
        "tenant-a", {"alice"}, "engram-ta",
        "2026-05-26T09:00:00Z", adapter_->connection());
    insert_stmt(*adapter_, "stmt-ta", "tenant-a", "alice",
                "consolidated", "approved");

    ToMEngine engine(*adapter_, *hub_, *frontier_);
    auto ctx = engine.perspective_take(
        "alice", "tenant-b", "2026-05-26T10:00:00Z");

    EXPECT_TRUE(ctx.visible_engram_ids.empty())
        << "cross-tenant visible_engrams must be empty";
    EXPECT_TRUE(ctx.target_beliefs.empty())
        << "cross-tenant target_beliefs must be empty";
}

}  // namespace
