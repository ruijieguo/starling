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
