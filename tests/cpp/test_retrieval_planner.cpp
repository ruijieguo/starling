// RetrievalPlanner 7 步管线(13_retrieval.md)。fixtures 直接 SQL 写
// statements(模式照 test_common_ground_read.cpp);StubEmbeddingAdapter
// 走真语义路径零网络。
#include "starling/retrieval/retrieval_planner.hpp"

#include "starling/embedding/embedding_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/vector/vector_index.hpp"

#include <gtest/gtest.h>

#include <cstdio>
#include <memory>
#include <string>

namespace starling::retrieval {

namespace {

constexpr const char* kNow = "2026-06-12T10:00:00Z";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void insert_statement(persistence::Connection& conn, const char* id,
                      const char* holder, const char* subject,
                      const char* predicate, const char* object,
                      const char* state = "consolidated",
                      double salience = 0.5,
                      const char* observed = "2026-06-10T00:00:00Z") {
    char sql[1200];
    std::snprintf(sql, sizeof(sql),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES("
        "'%s','default','%s','FIRST_PERSON','cognizer','%s','%s','str','%s',"
        "'h-%s','v1','KNOWS','POS',0.9,'%s',%f,'{}',0.0,'%s','user_input',"
        "'[{\"engram_id\":\"eng-%s\"}]','%s','approved',0,'%s','%s')",
        id, holder, subject, predicate, object, id, observed, salience,
        observed, id, state, observed, observed);
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql, nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

struct Rig {
    std::unique_ptr<persistence::SqliteAdapter> a = make_adapter();
    embedding::StubEmbeddingAdapter emb{8};
    vector::SqliteBlobVectorIndex idx;
    SemanticRetriever semantic{*a, emb, idx};
    RetrievalPlanner planner{*a, semantic};

    PlannerQuery q(QueryIntent intent) {
        PlannerQuery p;
        p.tenant_id = "default"; p.querier = "cog-self";
        p.intent = intent; p.as_of_iso8601 = kNow;
        p.trace_id = "tr-1"; p.query_id = "qy-1";
        return p;
    }
};

}  // namespace

TEST(RetrievalPlanner, FactLookupSevenStepsAndReceipt) {
    Rig rig;
    insert_statement(rig.a->connection(), "s1", "cog-self", "Bob",
                     "responsible_for", "auth");
    auto q = rig.q(QueryIntent::FACT_LOOKUP);
    q.subject_id = "Bob"; q.predicate = "responsible_for";
    const auto r = rig.planner.run(q);
    ASSERT_FALSE(r.abstained);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.id, "s1");
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::FACT);
    // 7 步各留痕。
    ASSERT_EQ(r.receipt.plan_steps.size(), 7u);
    EXPECT_EQ(r.receipt.plan_steps[0].step, "parse");
    EXPECT_EQ(r.receipt.plan_steps[6].step, "abstain");
    EXPECT_EQ(r.receipt.intent_name, "FACT_LOOKUP");
    EXPECT_EQ(r.receipt.sufficiency_status, Sufficiency::SUFFICIENT);
    EXPECT_FALSE(r.receipt.scope_plan.steps.empty());
    EXPECT_FALSE(r.receipt.score_breakdown.empty());
    EXPECT_NE(r.context_pack.find("[FACT]"), std::string::npos);
    // 中心化 emit:每条返回行一条 recalled。
    EXPECT_EQ(r.receipt.emitted_events.size(), 1u);
}

TEST(RetrievalPlanner, AbstainsOnEmptyWithLowScore) {
    Rig rig;
    auto q = rig.q(QueryIntent::FACT_LOOKUP);
    q.subject_id = "Nobody"; q.predicate = "responsible_for";
    const auto r = rig.planner.run(q);
    EXPECT_TRUE(r.abstained);
    EXPECT_EQ(r.receipt.abstention_reason, "low_score");
    EXPECT_EQ(r.receipt.sufficiency_status, Sufficiency::ABSTAINED);
    EXPECT_NE(r.context_pack.find("[ABSTAIN]"), std::string::npos);
    EXPECT_TRUE(r.receipt.emitted_events.empty());   // 拒答不发事件
}

TEST(RetrievalPlanner, BeliefOfOtherUsesTargetHolder) {
    Rig rig;
    insert_statement(rig.a->connection(), "s-alice", "Alice", "Bob",
                     "responsible_for", "deploy");
    auto q = rig.q(QueryIntent::BELIEF_OF_OTHER);
    q.target = "Alice";
    const auto r = rig.planner.run(q);
    ASSERT_FALSE(r.abstained);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.holder_id, "Alice");
    // 他者视角 + 单证据 → HEARSAY 标签(分类器联动)。
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::HEARSAY);
}

TEST(RetrievalPlanner, HistoryFollowsSupersedesChain) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "old", "cog-self", "Bob", "responsible_for", "auth",
                     "archived", 0.4, "2026-05-01T00:00:00Z");
    insert_statement(conn, "new", "cog-self", "Bob", "responsible_for", "deploy",
                     "consolidated", 0.6, "2026-06-01T00:00:00Z");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,"
        "weight,created_at) VALUES('e1','default','new','old','supersedes',"
        "1.0,'2026-06-01T00:00:00Z')", nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
    auto q = rig.q(QueryIntent::HISTORY);
    q.subject_id = "Bob"; q.predicate = "responsible_for"; q.k = 10;
    const auto r = rig.planner.run(q);
    ASSERT_FALSE(r.abstained);
    EXPECT_EQ(r.entries.size(), 2u);   // 主路时间线 + supersedes 链补全
}

TEST(RetrievalPlanner, CommitmentDueReturnsTodoLabel) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "cmt", "cog-self", "cog-self", "promises", "ship Friday");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "INSERT INTO commitments(tenant_id,stmt_id,state,broken_count,deadline,"
        "created_at,updated_at) VALUES('default','cmt','ACTIVE',0,"
        "'2026-06-13T00:00:00Z','2026-06-10T00:00:00Z','2026-06-10T00:00:00Z')",
        nullptr, nullptr, &err), SQLITE_OK) << (err ? err : "");
    const auto r = rig.planner.run(rig.q(QueryIntent::COMMITMENT_DUE));
    ASSERT_FALSE(r.abstained);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::TODO);
    EXPECT_NE(r.context_pack.find("[TODO]"), std::string::npos);
}

TEST(RetrievalPlanner, PreferenceFiltersPredicate) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "pref", "cog-self", "cog-self", "prefers", "dark roast");
    insert_statement(conn, "fact", "cog-self", "Bob", "responsible_for", "auth");
    const auto r = rig.planner.run(rig.q(QueryIntent::PREFERENCE));
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.predicate, "prefers");
}

TEST(RetrievalPlanner, NormLookupFiltersRegistryPredicates) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "norm1", "cog-self", "team", "requires", "code review");
    insert_statement(conn, "norm2", "cog-self", "team", "forbids", "force push");
    insert_statement(conn, "fact", "cog-self", "Bob", "responsible_for", "auth");
    const auto r = rig.planner.run(rig.q(QueryIntent::NORM_LOOKUP));
    EXPECT_EQ(r.entries.size(), 2u);
}

TEST(RetrievalPlanner, CommonGroundIntentReturnsGroundedOnly) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "g1", "cog-self", "team", "knows", "v2 goal");
    insert_statement(conn, "u1", "cog-self", "team", "knows", "draft idea");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "INSERT INTO common_ground(id,tenant_id,statement_id,status,parties_json,"
        "grounded_at,created_at,updated_at) VALUES"
        "('cg1','default','g1','grounded','[\"Alice\",\"cog-self\"]',"
        "'2026-06-11T00:00:00Z','2026-06-11T00:00:00Z','2026-06-11T00:00:00Z'),"
        "('cg2','default','u1','asserted_unack','[\"Alice\",\"cog-self\"]',"
        "NULL,'2026-06-11T00:00:00Z','2026-06-11T00:00:00Z')",
        nullptr, nullptr, &err), SQLITE_OK) << (err ? err : "");
    auto q = rig.q(QueryIntent::COMMON_GROUND);
    q.target = "Alice";
    const auto r = rig.planner.run(q);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.id, "g1");
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::COMMON);
}

TEST(RetrievalPlanner, MetaBeliefRequiresNestedRows) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "flat", "cog-self", "Bob", "responsible_for", "auth");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "UPDATE statements SET nesting_depth=1 WHERE id='flat'",
        nullptr, nullptr, &err), SQLITE_OK) << (err ? err : "");
    const auto r = rig.planner.run(rig.q(QueryIntent::META_BELIEF));
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.id, "flat");
}

TEST(RetrievalPlanner, RejectsScopeFilterMix) {
    Rig rig;
    auto q = rig.q(QueryIntent::BELIEF_OF_OTHER);
    q.target = "Alice";
    q.global_holder_filter = "cog-self";   // 全局 holder 与 step holder(Alice)冲突
    const auto r = rig.planner.run(q);
    EXPECT_TRUE(r.abstained);
    EXPECT_EQ(r.receipt.abstention_reason, "invalid_scope_filter_mix");
    EXPECT_TRUE(r.entries.empty());
}

}  // namespace starling::retrieval
