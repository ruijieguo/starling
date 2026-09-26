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
#include <limits>

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

// Scripted spy: drives each batch-failure branch of the worker, and counts
// embed vs embed_batch calls. embed_batch delegates to an INNER stub (not
// this->embed), so embed_calls counts ONLY the worker's per-row fallback.
class ScriptedAdapter : public starling::embedding::EmbeddingAdapter {
public:
    enum class BatchMode { Succeed, ThrowTransient, ThrowPermanent, WrongCount };
    BatchMode batch_mode = BatchMode::Succeed;
    std::string poison;  // a render_text that fails in the per-row fallback
    int embed_calls = 0;
    int embed_batch_calls = 0;

    starling::embedding::EmbeddingResult embed(std::string_view text) override {
        ++embed_calls;
        if (!poison.empty() && std::string(text) == poison) {
            throw starling::embedding::EmbeddingError("poison");
        }
        return inner_.embed(text);
    }
    std::vector<starling::embedding::EmbeddingResult>
    embed_batch(const std::vector<std::string>& texts) override {
        ++embed_batch_calls;
        if (batch_mode == BatchMode::ThrowTransient) {
            throw starling::embedding::EmbeddingError("batch transient");
        }
        if (batch_mode == BatchMode::ThrowPermanent) {
            throw std::runtime_error("permanent_batch");
        }
        std::vector<starling::embedding::EmbeddingResult> out;
        out.reserve(texts.size());
        for (const auto& text : texts) out.push_back(inner_.embed(text));
        if (batch_mode == BatchMode::WrongCount && !out.empty()) {
            out.pop_back();  // return N-1 → force the fail-closed per-row fallback
        }
        return out;
    }
    int dim() const override { return inner_.dim(); }
    std::string model() const override { return "scripted"; }
private:
    starling::embedding::StubEmbeddingAdapter inner_{8};
};

}  // namespace

TEST(EmbeddingHealth, RecoveredFailuresAreCompleteWithoutMoreEmbeddingCalls) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "s1");
    StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
    EmbeddingWorker worker(*adapter, emb, idx);
    EXPECT_EQ(worker.health(conn).missing, 1);
    emb.fail_next("bob knows x");
    EXPECT_EQ(worker.tick_one_batch(conn, "2026-09-26T00:00:00Z").failed, 1);
    auto failed = worker.health(conn);
    EXPECT_FALSE(failed.complete());
    EXPECT_EQ(failed.retryable_failed, 1);
    EXPECT_EQ(worker.tick_one_batch(conn, "2026-09-26T00:00:01Z").embedded, 1);
    const int changes = sqlite3_total_changes(conn.raw());
    auto recovered = worker.health(conn);
    EXPECT_TRUE(recovered.complete());
    EXPECT_EQ(recovered.total, 1);
    EXPECT_EQ(recovered.embedded, 1);
    EXPECT_EQ(sqlite3_total_changes(conn.raw()), changes);
    EXPECT_EQ(count(conn.raw(), "SELECT COUNT(*) FROM statement_vectors WHERE last_attempt_at IS NOT NULL"), 1);
}

TEST(EmbeddingHealth, ExhaustionAndIdleAreDifferent) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection(); seed_stmt(conn.raw(), "s1");
    StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
    EmbeddingWorker worker(*adapter, emb, idx);
    for (int i = 0; i < 3; ++i) {
        emb.fail_next("bob knows x");
        ASSERT_EQ(worker.tick_one_batch(conn, "2026-09-26T00:00:00Z").failed, 1);
    }
    EXPECT_EQ(worker.tick_one_batch(conn, "2026-09-26T00:00:01Z").failed, 0);
    auto health = worker.health(conn);
    EXPECT_FALSE(health.complete());
    EXPECT_EQ(health.exhausted, 1);
    EXPECT_EQ(health.retryable_failed, 0);
}

TEST(EmbeddingHealth, InvalidVectorsNeverCountAsComplete) {
    for (const auto& change : {"dim=9", "model='foreign'", "raw_embedding=x'00000000'",
                              "index_vector=zeroblob(32)", "retry_count=1"}) {
        SCOPED_TRACE(change);
        auto adapter = SqliteAdapter::open(":memory:");
        auto& conn = adapter->connection(); seed_stmt(conn.raw(), "s1");
        StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
        EmbeddingWorker worker(*adapter, emb, idx);
        ASSERT_EQ(worker.tick_one_batch(conn, "2026-09-26T00:00:00Z").embedded, 1);
        conn.exec(std::string("UPDATE statement_vectors SET ") + change);
        auto health = worker.health(conn);
        EXPECT_FALSE(health.complete()); EXPECT_EQ(health.invalid, 1);
    }
}

TEST(EmbeddingHealth, NonFiniteBlobIsRejectedAtCorrectLength) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection(); seed_stmt(conn.raw(), "s1");
    StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
    EmbeddingWorker worker(*adapter, emb, idx);
    ASSERT_EQ(worker.tick_one_batch(conn, "2026-09-26T00:00:00Z").embedded, 1);
    for (float bad : {std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN()}) {
        float values[8] = {bad, 1, 1, 1, 1, 1, 1, 1};
        sqlite3_stmt* stmt = nullptr;
        ASSERT_EQ(sqlite3_prepare_v2(conn.raw(), "UPDATE statement_vectors SET raw_embedding=?", -1, &stmt, nullptr), SQLITE_OK);
        sqlite3_bind_blob(stmt, 1, values, sizeof(values), SQLITE_TRANSIENT);
        ASSERT_EQ(sqlite3_step(stmt), SQLITE_DONE); sqlite3_finalize(stmt);
        EXPECT_EQ(worker.health(conn).invalid, 1);
    }
}

TEST(EmbeddingHealth, TenantJoinCannotBorrowAnotherTenantsVector) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection(); seed_stmt(conn.raw(), "s1");
    StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
    EmbeddingWorker worker(*adapter, emb, idx);
    ASSERT_EQ(worker.tick_one_batch(conn, "2026-09-26T00:00:00Z").embedded, 1);
    conn.exec("PRAGMA foreign_keys=OFF");
    conn.exec("UPDATE statement_vectors SET tenant_id='other'");
    auto health = worker.health(conn);
    EXPECT_FALSE(health.complete()); EXPECT_EQ(health.missing, 1);
}

TEST(EmbeddingHealth, ArchivedAndForgottenFollowWorkerScope) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "s1", "x", "archived");
    seed_stmt(conn.raw(), "s2", "x", "forgotten");
    StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
    EmbeddingWorker worker(*adapter, emb, idx);
    EXPECT_EQ(worker.health(conn).total, 0);
    EXPECT_TRUE(worker.health(conn).complete());
}

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

TEST(EmbeddingWorker, FastPathCallsEmbedBatchOnce) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1", "x0");
    seed_stmt(db, "s2", "x1");
    seed_stmt(db, "s3", "x2");

    ScriptedAdapter emb;  // Succeed
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 3);
    EXPECT_EQ(emb.embed_batch_calls, 1);  // ONE batched call...
    EXPECT_EQ(emb.embed_calls, 0);        // ...no per-row fallback
}

TEST(EmbeddingWorker, TransientBatchFailureMarksAllThenRecovers) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "a", "x0");
    seed_stmt(db, "b", "x1");
    seed_stmt(db, "c", "x2");

    ScriptedAdapter emb;
    emb.batch_mode = ScriptedAdapter::BatchMode::ThrowTransient;
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st1 = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st1.failed, 3);          // whole batch marked failed...
    EXPECT_EQ(st1.embedded, 0);
    EXPECT_EQ(emb.embed_calls, 0);     // ...WITHOUT a per-row retry storm
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM statement_vectors WHERE status='failed'"), 3);

    emb.batch_mode = ScriptedAdapter::BatchMode::Succeed;  // transient outage over
    auto st2 = w.tick_one_batch(conn, "2026-05-30T10:01:00Z");
    EXPECT_EQ(st2.embedded, 3);        // all re-embed
}

TEST(EmbeddingWorker, PermanentBatchFailureIsolatesPoisonRow) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "a", "x0");
    seed_stmt(db, "b", "x1");
    seed_stmt(db, "c", "x2");

    ScriptedAdapter emb;
    emb.batch_mode = ScriptedAdapter::BatchMode::ThrowPermanent;  // batch 400s
    emb.poison = "bob knows x1";  // only row b fails in the per-row fallback
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 2);  // a and c embed via the per-row fallback...
    EXPECT_EQ(st.failed, 1);    // ...only the poison row b is marked failed
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM statement_vectors WHERE stmt_id='b' AND status='failed'"), 1);
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM statement_vectors WHERE status='embedded'"), 2);
}

TEST(EmbeddingWorker, WrongResultCountFallsBackToPerRow) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "a", "x0");
    seed_stmt(db, "b", "x1");

    ScriptedAdapter emb;
    emb.batch_mode = ScriptedAdapter::BatchMode::WrongCount;  // returns N-1
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 2);        // fail-closed → per-row fallback embeds all
    EXPECT_GE(emb.embed_calls, 2);    // fallback used embed()
}
