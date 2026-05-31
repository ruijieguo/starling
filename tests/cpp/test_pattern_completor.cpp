// test_pattern_completor.cpp -- P2.d Pattern Completion (CA3 spreading-activation)
#include "starling/retrieval/pattern_completor.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/embedding/embedding_worker.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>
#include <unordered_map>

using starling::embedding::EmbeddingWorker;
using starling::embedding::StubEmbeddingAdapter;  // declared in embedding_adapter.hpp
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::retrieval::CompletionResult;
using starling::retrieval::PatternCompletionParams;
using starling::retrieval::PatternCompletor;
using starling::retrieval::SemanticRetriever;
using starling::vector::SqliteBlobVectorIndex;

namespace {

// Seed a visible statement. render_text = "<subj> <pred> <obj>" = "bob knows <obj>".
// holder/perspective/tenant overridable for privacy/tenant tests.
[[maybe_unused]] void seed_stmt(sqlite3* db, const std::string& id, const std::string& obj = "x",
               const std::string& holder = "alice",
               const std::string& perspective = "first_person",
               const std::string& tenant = "default",
               const std::string& state = "consolidated",
               const std::string& review = "approved") {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('"
        + id + "','" + tenant + "','" + holder + "','" + perspective + "','cognizer',"
        "'bob','knows','str','" + obj + "','" + std::string(64, 'a') + "','v1',"
        "'believes','pos',0.9,'2026-05-31T09:00:00Z',0.5,'{}',0.0,"
        "'2026-05-31T09:00:00Z','user_input','" + state + "','" + review + "',"
        "'2026-05-31T09:00:00Z','2026-05-31T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

// Insert a statement_edges row. Default kind MAY_OVERLAP_WITH, tenant default.
[[maybe_unused]] void seed_edge(sqlite3* db, const std::string& id, const std::string& src,
               const std::string& dst, double weight,
               const std::string& kind = "MAY_OVERLAP_WITH",
               const std::string& tenant = "default") {
    std::string s =
        "INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,weight,"
        "created_at,metadata_json) VALUES('"
        + id + "','" + tenant + "','" + src + "','" + dst + "','" + kind + "',"
        + std::to_string(weight) + ",'2026-05-31T00:00:00Z','{\"resolved\":false}')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

// Embed exactly the already-inserted statements (call BEFORE inserting walk-only
// target nodes so the worker doesn't auto-create overlap edges among them).
[[maybe_unused]] void embed_existing(SqliteAdapter& adapter, StubEmbeddingAdapter& emb,
                    SqliteBlobVectorIndex& idx, Connection& conn) {
    EmbeddingWorker worker(adapter, emb, idx);
    worker.tick_one_batch(conn, "2026-05-31T10:00:00Z");
}

}  // namespace

TEST(PatternCompletor, ConstructsAndReturnsEmptyWhenNoSeeds) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);

    PatternCompletionParams p;
    p.tenant_id = "default";
    p.holder_id = "alice";
    p.cue_text  = "bob knows nothing";  // 无任何向量 → 无种子

    auto res = pc.complete(conn, p);
    EXPECT_TRUE(res.rows.empty());
    EXPECT_FALSE(res.completion_truncated);
}

TEST(PatternCompletor, SeedsOnlyNoEdges) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);   // 只嵌入 seed

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);

    PatternCompletionParams p;
    p.tenant_id = "default";
    p.holder_id = "alice";
    p.holder_perspective = "first_person";
    p.cue_text  = "bob knows cats";  // == seed render_text
    p.seed_k    = 5;

    auto res = pc.complete(conn, p);
    ASSERT_EQ(res.rows.size(), 1u);
    EXPECT_EQ(res.rows[0].row.id, "seed");
    EXPECT_DOUBLE_EQ(res.rows[0].activation, 1.0);
    EXPECT_FALSE(res.completion_truncated);
    EXPECT_FALSE(res.degraded);
}

// 单跳前向:seed→A(w=0.9)、seed→B(w=0.5)。decay=0.5 →
//   A=0.9*0.5=0.45, B=0.5*0.5=0.25。存储相似度参与(高权更高)。
TEST(PatternCompletor, OneHopForwardUsesStoredWeight) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);   // 只嵌入 seed
    seed_stmt(db, "A", "a");                     // walk-only 目标,无向量
    seed_stmt(db, "B", "b");
    seed_edge(db, "e1", "seed", "A", 0.9);
    seed_edge(db, "e2", "seed", "B", 0.5);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats"; p.seed_k = 5;

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("A")); ASSERT_TRUE(act.count("B"));
    EXPECT_DOUBLE_EQ(act["A"], 0.45);
    EXPECT_DOUBLE_EQ(act["B"], 0.25);
    EXPECT_GT(act["A"], act["B"]);
}

// clamp:w=1.5→1.0→A=0.5;w=-0.2→0→contrib=0<θ→B 被剪。
TEST(PatternCompletor, EdgeWeightClamped) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "A", "a");
    seed_stmt(db, "B", "b");
    seed_edge(db, "e1", "seed", "A", 1.5);   // → clamp 1.0
    seed_edge(db, "e2", "seed", "B", -0.2);  // → clamp 0 → 剪

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("A"));
    EXPECT_DOUBLE_EQ(act["A"], 0.5);
    EXPECT_FALSE(act.count("B")) << "negative-weight edge must be pruned";
}

// 对称反向:边写 src=A dst=seed;种子=seed → A 经反向 UNION 可达,act=0.5。
TEST(PatternCompletor, SymmetricReverseTraversal) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "A", "a");
    seed_edge(db, "e1", "A", "seed", 1.0);   // seed 作为 dst

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("A"));
    EXPECT_DOUBLE_EQ(act["A"], 0.5);
}

// 严格逐跳:overlap 边连到别 perspective 的陈述 → 该节点不进结果。
TEST(PatternCompletor, StrictPerHopExcludesOtherPerspective) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats", "alice", "first_person");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "other", "cats", "alice", "third_person");  // 别 perspective
    seed_edge(db, "e1", "seed", "other", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    for (const auto& r : res.rows)
        EXPECT_NE(r.row.id, "other") << "cross-perspective node must never be activated";
}

// 别 holder 同理被排除。
TEST(PatternCompletor, StrictPerHopExcludesOtherHolder) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats", "alice", "first_person");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "bobstmt", "cats", "bob", "first_person");  // 别 holder
    seed_edge(db, "e1", "seed", "bobstmt", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    for (const auto& r : res.rows)
        EXPECT_NE(r.row.id, "bobstmt") << "cross-holder node must never be activated";
}

// 跨租户边不可桥:边在 default,dst 仅存在于 tenant 'other' → JOIN 无果。
TEST(PatternCompletor, TenantIsolationNotBridged) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats", "alice", "first_person", "default");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "xt", "cats", "alice", "first_person", "other");  // 别租户
    seed_edge(db, "e1", "seed", "xt", 1.0, "MAY_OVERLAP_WITH", "default");

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    for (const auto& r : res.rows)
        EXPECT_NE(r.row.id, "xt") << "cross-tenant node must never be bridged";
}

// 菱形:seed→A,seed→B,A→D,B→D(全 w=1.0,decay=0.5)。
//   A=B=0.5;D 经两路各得 0.5*0.5=0.25,max 合并 → 0.25(非 sum 0.5)。
TEST(PatternCompletor, DiamondMaxNotAccumulate) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "A", "a"); seed_stmt(db, "B", "b"); seed_stmt(db, "D", "d");
    seed_edge(db, "e1", "seed", "A", 1.0);
    seed_edge(db, "e2", "seed", "B", 1.0);
    seed_edge(db, "e3", "A", "D", 1.0);
    seed_edge(db, "e4", "B", "D", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("D"));
    EXPECT_DOUBLE_EQ(act["D"], 0.25) << "max-merge, not sum";
    EXPECT_DOUBLE_EQ(act["A"], 0.5);
}

// 衰减链 seed→n1→n2→n3→n4→n5(全 w=1.0)。activation=0.5^depth:
//   n1=.5 n2=.25 n3=.125 n4=.0625 n5=.03125<θ(0.05) → n5 被剪。
TEST(PatternCompletor, DecayChainThetaCutoff) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    for (int i = 1; i <= 5; ++i) seed_stmt(db, "n" + std::to_string(i), "n" + std::to_string(i));
    seed_edge(db, "c0", "seed", "n1", 1.0);
    seed_edge(db, "c1", "n1", "n2", 1.0);
    seed_edge(db, "c2", "n2", "n3", 1.0);
    seed_edge(db, "c3", "n3", "n4", 1.0);
    seed_edge(db, "c4", "n4", "n5", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats"; p.result_k = 20;

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    EXPECT_TRUE(act.count("n4")); EXPECT_DOUBLE_EQ(act["n4"], 0.0625);
    EXPECT_FALSE(act.count("n5")) << "activation 0.03125 < theta 0.05 → pruned";
}

// node_cap 截断:seed 连 1100 个目标(w=1.0)→ node_count≥1000 → truncated,结果≤result_k。
TEST(PatternCompletor, NodeCapTruncation) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    for (int i = 0; i < 1100; ++i) {
        std::string nid = "t" + std::to_string(i);
        seed_stmt(db, nid, nid);
        seed_edge(db, "edge" + std::to_string(i), "seed", nid, 1.0);
    }

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats"; p.result_k = 20; p.node_cap = 1000;

    auto res = pc.complete(conn, p);
    EXPECT_TRUE(res.completion_truncated);
    EXPECT_LE(res.rows.size(), 20u);
}
