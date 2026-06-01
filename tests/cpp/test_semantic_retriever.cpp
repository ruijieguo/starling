// test_semantic_retriever.cpp -- M0.9 SemanticRetriever (TC-SEMANTIC-RETRIEVER)
//
// RanksByQuerySimilarityWithinVisibleScope: embed 3 visible stmts, query with
//   exact render_text of s1 → s1 ranks #1 (or verified as top scorer).
// HiddenStatementsExcluded: pending_review stmt never returned even when its
//   vector is identical to a visible stmt's vector.

#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/embedding/embedding_worker.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <algorithm>
#include <memory>
#include <string>

using starling::embedding::EmbeddingWorker;
using starling::embedding::StubEmbeddingAdapter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::retrieval::SemanticRetriever;
using starling::retrieval::SemanticRetrieverParams;
using starling::vector::SqliteBlobVectorIndex;

namespace {

// Seed a statement with optional consolidation_state and review_status.
// render_text = "bob knows <obj>"
void seed_stmt(sqlite3* db, const std::string& id, const std::string& obj = "x",
               const std::string& state = "consolidated",
               const std::string& review = "approved") {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('"
        + id + "','default','alice','first_person','cognizer',"
        "'bob','knows','str','" + obj + "','" + std::string(64, 'a') + "','v1',"
        "'believes','pos',0.9,'2026-05-30T09:00:00Z',0.5,'{}',0.0,"
        "'2026-05-30T09:00:00Z','user_input','" + state + "','" + review + "',"
        "'2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

}  // namespace

TEST(SemanticRetriever, RanksByQuerySimilarityWithinVisibleScope) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();

    // Seed 3 visible statements with distinct object texts.
    seed_stmt(db, "s1", "cats");
    seed_stmt(db, "s2", "stocks");
    seed_stmt(db, "s3", "dogs");

    // Use a single StubEmbeddingAdapter instance for both worker and retriever
    // to guarantee deterministic, consistent embeddings.
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    // Embed all three statements via the worker.
    EmbeddingWorker worker(*adapter, emb, idx);
    worker.tick_one_batch(conn, "2026-05-30T10:00:00Z");

    // Build retriever with the SAME embedder instance.
    SemanticRetriever sr(*adapter, emb, idx);

    SemanticRetrieverParams params;
    params.tenant_id = "default";
    params.holder_id = "alice";
    params.k         = 3;
    // Query with the exact render_text of s1: subject_id + " " + predicate + " " + object_value
    params.query_text = "bob knows cats";

    auto res = sr.vector_recall(conn, params);

    EXPECT_FALSE(res.degraded);
    ASSERT_GE(res.rows.size(), 1u);

    // s1's stored vector was computed from "bob knows cats" — the same text as
    // the query — so it should be the most similar result.
    // Primary assertion: s1 is at position 0 (strict).
    // Robust fallback: s1 appears in results AND has the highest score.
    bool s1_first = (res.rows[0].row.id == "s1");
    bool s1_in_results = false;
    double s1_score = -1.0;
    double max_score = res.rows[0].score;
    for (const auto& sr_row : res.rows) {
        if (sr_row.row.id == "s1") {
            s1_in_results = true;
            s1_score = sr_row.score;
        }
        if (sr_row.score > max_score) max_score = sr_row.score;
    }

    EXPECT_TRUE(s1_in_results) << "s1 must appear in vector_recall results";
    // s1's score must be the highest (or tied for highest).
    if (s1_in_results) {
        EXPECT_DOUBLE_EQ(s1_score, max_score)
            << "s1 must have the highest cosine score";
    }
    // Strict ordering check (preferred assertion per spec).
    EXPECT_TRUE(s1_first) << "s1 should be at rows[0] since query == s1's render_text";
}

TEST(SemanticRetriever, HiddenStatementsExcluded) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();

    // "vis" is visible; "hid" has the same text but is pending_review → not visible.
    seed_stmt(db, "vis", "cats", "consolidated", "approved");
    seed_stmt(db, "hid", "cats", "consolidated", "pending_review");

    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    // Embed both statements.
    EmbeddingWorker worker(*adapter, emb, idx);
    worker.tick_one_batch(conn, "2026-05-30T10:00:00Z");

    SemanticRetriever sr(*adapter, emb, idx);

    SemanticRetrieverParams params;
    params.tenant_id  = "default";
    params.holder_id  = "alice";
    params.k          = 10;
    params.query_text = "bob knows cats";

    auto res = sr.vector_recall(conn, params);

    // "hid" must never appear in results.
    for (const auto& row : res.rows) {
        EXPECT_NE(row.row.id, "hid") << "pending_review statement must not be returned";
    }

    // "vis" must be present.
    bool vis_found = false;
    for (const auto& row : res.rows) {
        if (row.row.id == "vis") {
            vis_found = true;
            break;
        }
    }
    EXPECT_TRUE(vis_found) << "visible consolidated/approved statement must be returned";
}

TEST(SemanticRetriever, CarriesAffectJson) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1", "cats");
    sqlite3_exec(db, "UPDATE statements SET affect_json='{\"valence\":0.7}' WHERE id='s1'",
                 nullptr, nullptr, nullptr);
    StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
    EmbeddingWorker(*adapter, emb, idx).tick_one_batch(conn, "2026-06-01T10:00:00Z");
    SemanticRetriever sr(*adapter, emb, idx);
    SemanticRetrieverParams p; p.tenant_id="default"; p.holder_id="alice";
    p.k=1; p.query_text="bob knows cats";
    auto res = sr.vector_recall(conn, p);
    ASSERT_GE(res.rows.size(), 1u);
    EXPECT_EQ(res.rows[0].row.affect_json, "{\"valence\":0.7}");
}
