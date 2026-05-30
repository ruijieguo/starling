// test_embedding_worker.cpp -- M0.9 EmbeddingWorker (TC-EMBED-WORKER)
//
// EmbedsPendingAndEmitsEvent:        pending stmt → embedded row + vector.embedded event.
// SecondTickNoOpAlreadyEmbedded:     re-tick after embed is a no-op (embedded==0).
// FailureMarksFailedWithRetry:       transient embed failure → status='failed', retry_count>=1.
// PatternSeparationBuildsOverlapEdge: identical text → cosine 1.0 > theta_sep → MAY_OVERLAP_WITH.

#include "starling/embedding/embedding_worker.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using starling::embedding::EmbeddingWorker;
using starling::embedding::StubEmbeddingAdapter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::vector::SqliteBlobVectorIndex;

namespace {

// Seed a statement. object_value (`obj`) controls render_text and thus the stub
// embedding, so tests can drive similarity. render_text = subject_id+" "+predicate+" "+obj
// = "bob knows <obj>".
void seed_stmt(sqlite3* db, const std::string& id, const std::string& obj = "x",
               const std::string& state = "consolidated") {
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
      "'bob','knows','str','"+obj+"','"+std::string(64,'a')+"','v1','believes','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','"+state+
      "','approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

int count(sqlite3* db, const std::string& q) {
    int n=0; sqlite3_exec(db,q.c_str(),[](void*p,int,char**v,char**){*(int*)p=v[0]?atoi(v[0]):0;return 0;},&n,nullptr); return n;
}

}  // namespace

TEST(EmbeddingWorker, EmbedsPendingAndEmitsEvent) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1");

    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 1);
    EXPECT_EQ(count(db,
        "SELECT COUNT(*) FROM statement_vectors WHERE stmt_id='s1' AND status='embedded'"), 1);
    EXPECT_EQ(count(db,
        "SELECT COUNT(*) FROM bus_events WHERE event_type='vector.embedded' AND primary_id='s1'"), 1);
}

TEST(EmbeddingWorker, SecondTickNoOpAlreadyEmbedded) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1");

    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto first = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(first.embedded, 1);

    auto second = w.tick_one_batch(conn, "2026-05-30T10:01:00Z");
    EXPECT_EQ(second.embedded, 0);
}

TEST(EmbeddingWorker, FailureMarksFailedWithRetry) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "boom");

    StubEmbeddingAdapter emb(8);
    emb.fail_next("bob knows x");  // render_text of the seeded stmt
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.failed, 1);
    EXPECT_GE(count(db,
        "SELECT retry_count FROM statement_vectors WHERE stmt_id='boom' AND status='failed'"), 1);
}

TEST(EmbeddingWorker, PatternSeparationBuildsOverlapEdge) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();

    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    // Embed "a" first so it becomes a neighbor in the index.
    seed_stmt(db, "a", "x");
    auto st1 = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st1.embedded, 1);

    // Seed "b" with identical text → identical stub embedding → cosine 1.0 > theta_sep.
    seed_stmt(db, "b", "x");
    auto st2 = w.tick_one_batch(conn, "2026-05-30T10:01:00Z");
    EXPECT_EQ(st2.embedded, 1);

    EXPECT_GE(count(db,
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='MAY_OVERLAP_WITH'"), 1);
}
