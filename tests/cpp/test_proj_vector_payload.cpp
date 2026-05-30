// test_proj_vector_payload.cpp -- M0.9 §8: ProjectionMaintainer consumes
// vector.embedded → materializes the 7th projection proj_vector_payload, and
// retires the row when the statement is archived/forgotten.
//
// VectorEmbeddedEventMaterializesRow:
//   seed s1 → EmbeddingWorker tick (emits vector.embedded) →
//   ProjectionMaintainer tick → proj_vector_payload has 1 row for s1.
//
// RetireRemovesRow:
//   same setup (row=1) → archive s1 + emit a real statement.archived event →
//   ProjectionMaintainer tick → proj_vector_payload row for s1 is gone.

#include "starling/projection/projection_maintainer.hpp"
#include "starling/embedding/embedding_worker.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <chrono>
#include <memory>
#include <string>

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::embedding::EmbeddingWorker;
using starling::embedding::StubEmbeddingAdapter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::TransactionGuard;
using starling::projection::ProjectionMaintainer;
using starling::vector::SqliteBlobVectorIndex;

namespace {

// Seed a statement (mirrors test_embedding_worker.cpp). render_text drives the
// stub embedding; state controls consolidation_state.
void seed_stmt(sqlite3* db, const std::string& id,
               const std::string& state = "consolidated") {
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
      "'bob','knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','"+state+
      "','approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

int count(sqlite3* db, const std::string& q) {
    int n=0; sqlite3_exec(db,q.c_str(),[](void*p,int,char**v,char**){*(int*)p=v[0]?atoi(v[0]):0;return 0;},&n,nullptr); return n;
}

// Emit a real bus event the same way production does (OutboxWriter inside a tx).
void emit_event(Connection& conn, const std::string& event_type,
                const std::string& primary_id, const std::string& aggregate_id,
                const std::string& tenant_id) {
    TransactionGuard tx(conn);
    BusEvent ev;
    ev.tenant_id = tenant_id;
    ev.event_type = event_type;
    ev.primary_id = primary_id;
    ev.aggregate_id = aggregate_id;
    const std::string window_bucket =
        compute_window_bucket(event_type, std::chrono::system_clock::now());
    ev.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, primary_id, /*causation_root=*/"", window_bucket);
    ev.payload_json = "{}";
    OutboxWriter ow(conn);
    ow.append(ev);
    tx.commit();
}

}  // namespace

TEST(ProjVectorPayload, VectorEmbeddedEventMaterializesRow) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1");

    // Embed s1 → statement_vectors row + vector.embedded event.
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    EmbeddingWorker(*adapter, emb, idx)
        .tick_one_batch(conn, "2026-05-30T10:00:00Z");

    // Project: vector.embedded → proj_vector_payload row.
    ProjectionMaintainer(*adapter).tick_one_batch(conn, "2026-05-30T10:01:00Z");

    EXPECT_EQ(count(db,
        "SELECT COUNT(*) FROM proj_vector_payload WHERE stmt_id='s1'"), 1);
}

TEST(ProjVectorPayload, RetireRemovesRow) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1");

    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    EmbeddingWorker(*adapter, emb, idx)
        .tick_one_batch(conn, "2026-05-30T10:00:00Z");

    ProjectionMaintainer pm(*adapter);
    pm.tick_one_batch(conn, "2026-05-30T10:01:00Z");
    ASSERT_EQ(count(db,
        "SELECT COUNT(*) FROM proj_vector_payload WHERE stmt_id='s1'"), 1);

    // Archive s1 and emit a real statement.archived event so the projection
    // tick sees a retire through the production path (delete_vector_payload).
    sqlite3_exec(db,
        "UPDATE statements SET consolidation_state='archived' WHERE id='s1'",
        nullptr, nullptr, nullptr);
    emit_event(conn, "statement.archived", "s1", "alice", "default");

    pm.tick_one_batch(conn, "2026-05-30T10:02:00Z");

    EXPECT_EQ(count(db,
        "SELECT COUNT(*) FROM proj_vector_payload WHERE stmt_id='s1'"), 0);
}
