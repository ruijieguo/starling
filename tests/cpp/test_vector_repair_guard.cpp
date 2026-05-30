// test_vector_repair_guard.cpp -- TC-VEC-REPAIR (CRITICAL)
//
// Closes M0.8 finding #6's dormant truncation guard: proj_vector_payload is the
// first projection whose ground_truth (embedded vectors) and rebuilt
// (materialized rows) are GENUINELY different — so §16.3-3/-6 can actually fire.
//
// TruncationSuspectedKeepsActive:
//   seed 3 stmts → embed 3 → project 3 rows in proj_vector_payload.
//   rebuild_projection_with_injected_count(..., 2) → rebuilt(2) < ground_truth(3)
//   → report.truncation_suspected; active NOT replaced (still 3 rows);
//   projection.rebuild_failed emitted; rebuild_state status='truncation_suspected'.
//
// HealthyRebuildReplaces:
//   same setup → rebuild_projection (no injection, rebuilt==ground_truth==3)
//   → report.truncation_suspected=false; 3 rows; status='active'.

#include "starling/projection/projection_maintainer.hpp"
#include "starling/embedding/embedding_worker.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using starling::embedding::EmbeddingWorker;
using starling::embedding::StubEmbeddingAdapter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::projection::ProjectionMaintainer;
using starling::projection::RebuildReport;
using starling::vector::SqliteBlobVectorIndex;

namespace {

// object_value (`obj`) varies so each statement gets a distinct stub embedding
// (avoids spurious MAY_OVERLAP edges; irrelevant to the guard but keeps it clean).
void seed_stmt(sqlite3* db, const std::string& id, const std::string& obj,
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

std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    const char* t = reinterpret_cast<const char*>(sqlite3_column_text(s, 0));
    std::string v = t ? t : "";
    sqlite3_finalize(s);
    return v;
}

// Seed 3 statements, embed them, and materialize proj_vector_payload (3 rows).
void seed_embed_project(SqliteAdapter& adapter, Connection& conn, sqlite3* db) {
    seed_stmt(db, "s1", "alpha");
    seed_stmt(db, "s2", "beta");
    seed_stmt(db, "s3", "gamma");

    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    EmbeddingWorker(adapter, emb, idx).tick_one_batch(conn, "2026-05-30T10:00:00Z");

    ProjectionMaintainer(adapter).tick_one_batch(conn, "2026-05-30T10:01:00Z");
}

}  // namespace

TEST(VectorRepairGuard, TruncationSuspectedKeepsActive) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();

    seed_embed_project(*adapter, conn, db);
    ASSERT_EQ(count(db, "SELECT COUNT(*) FROM proj_vector_payload"), 3);

    ProjectionMaintainer pm(*adapter);
    // Inject rebuilt=2 < ground_truth=3 → truncation guard fires.
    RebuildReport report = pm.rebuild_projection_with_injected_count(
        conn, "proj_vector_payload", /*injected_rebuilt=*/2,
        "2026-05-30T11:00:00Z");

    EXPECT_TRUE(report.truncation_suspected);
    EXPECT_EQ(report.ground_truth_count, 3);
    EXPECT_EQ(report.rebuilt_count, 2);

    // Active projection NOT replaced — still 3 rows.
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM proj_vector_payload"), 3);

    // projection.rebuild_failed emitted exactly once.
    EXPECT_EQ(count(db,
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='projection.rebuild_failed'"), 1);

    // Rebuild-state row marked truncation_suspected.
    EXPECT_EQ(scol(db,
        "SELECT status FROM projection_rebuild_state "
        "WHERE projection_name='proj_vector_payload'"), "truncation_suspected");
}

TEST(VectorRepairGuard, HealthyRebuildReplaces) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();

    seed_embed_project(*adapter, conn, db);
    ASSERT_EQ(count(db, "SELECT COUNT(*) FROM proj_vector_payload"), 3);

    ProjectionMaintainer pm(*adapter);
    // No injection → rebuilt == ground_truth == 3 → healthy.
    RebuildReport report =
        pm.rebuild_projection(conn, "proj_vector_payload", "2026-05-30T11:05:00Z");

    EXPECT_FALSE(report.truncation_suspected);
    EXPECT_EQ(report.ground_truth_count, 3);
    EXPECT_EQ(report.rebuilt_count, 3);
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM proj_vector_payload"), 3);
    EXPECT_EQ(scol(db,
        "SELECT status FROM projection_rebuild_state "
        "WHERE projection_name='proj_vector_payload'"), "active");
}
