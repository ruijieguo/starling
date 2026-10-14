// test_persona_subscriber.cpp — PersonaSubscriber materialization unit.
//
// Rebuilds a subject's PersonaContainer from its consolidated statements when a
// statement.derived / statement.consolidated / statement.superseded event lands.
// Subject is resolved via the event's primary_id (never aggregate_id).
//
//   DerivedSelfAnchorMaterializes  self-anchor (holder==subject) → persona value.
//   ProfileAnchorAndCheckpoint     profile anchor + checkpoint advance/idempotent.
//   IgnoresVolatileAndRejected     volatile/non-approved excluded → no persona.
//   SupersededTriggersRebuild      statement.superseded also drives a rebuild.

#include "starling/tom/persona_subscriber.hpp"
#include "starling/neocortex/persona_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

using namespace starling;

namespace {
// Purpose-built seed helpers (explicit object_value / consolidation_state /
// review_status / event_type — the CG helpers hardcode these).
void seed_statement(persistence::Connection& conn, const std::string& sid,
                    const std::string& holder, const std::string& subject,
                    const std::string& predicate, const std::string& object_value,
                    const std::string& consolidation_state,
                    const std::string& review_status) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,consolidation_state,review_status,scope_parties_json,"
        "created_at,updated_at) VALUES "
        "(?,'default',?,'first_person','entity',?,?,'str',?,'h','v1','believes',"
        "'pos',0.8,'2026-01-01T00:00:00Z',0.5,'{}',1.0,'2026-01-01T00:00:00Z',"
        "'user_input',?,?,'[]','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')",
        -1, &raw, nullptr);
    persistence::StmtHandle handle(raw);
    persistence::detail::bind_sv(handle.get(), 1, sid);
    persistence::detail::bind_sv(handle.get(), 2, holder);
    persistence::detail::bind_sv(handle.get(), 3, subject);
    persistence::detail::bind_sv(handle.get(), 4, predicate);
    persistence::detail::bind_sv(handle.get(), 5, object_value);
    persistence::detail::bind_sv(handle.get(), 6, consolidation_state);
    persistence::detail::bind_sv(handle.get(), 7, review_status);
    sqlite3_step(handle.get());
}
void seed_event(persistence::Connection& conn, const std::string& eid,
                const std::string& event_type, const std::string& primary_id, int seq,
                const std::string& aggregate_id = "") {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,aggregate_id,"
        "outbox_sequence,idempotency_key,payload_json,created_at) VALUES "
        "(?,'default',?,?,?,?,?,'{}','2026-07-01T00:00:00Z')", -1, &raw, nullptr);
    persistence::StmtHandle handle(raw);
    persistence::detail::bind_sv(handle.get(), 1, eid);
    persistence::detail::bind_sv(handle.get(), 2, event_type);
    persistence::detail::bind_sv(handle.get(), 3, primary_id);
    persistence::detail::bind_sv(handle.get(), 4, aggregate_id.empty() ? primary_id : aggregate_id);
    sqlite3_bind_int(handle.get(), 5, seq);
    persistence::detail::bind_sv(handle.get(), 6, std::string("ik-") + eid);
    sqlite3_step(handle.get());
}
int persona_checkpoint(persistence::Connection& conn) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT last_processed_outbox_sequence FROM persona_subscriber_checkpoint WHERE id=1",
        -1, &raw, nullptr);
    persistence::StmtHandle handle(raw);
    sqlite3_step(handle.get());
    return sqlite3_column_int(handle.get(), 0);
}
}  // namespace

// statement.derived (normal consolidation) on a self-anchor → persona materializes.
TEST(PersonaSubscriber, DerivedSelfAnchorMaterializes) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    // review_requested is the DEFAULT for a remembered self-fact (BLOCKER-3):
    seed_statement(conn, "S1", "self", "self", "trait_curiosity", "high",
                   "consolidated", "review_requested");
    seed_event(conn, "E1", "statement.derived", "S1", 1);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    const auto view = neocortex::PersonaContainer(*adapter).read(conn, "default", "self");
    EXPECT_TRUE(view.found);
    EXPECT_EQ(view.dimensions.at("trait_curiosity"), "high");
}

// profile anchor (holder != subject) classified; checkpoint advances; idempotent.
TEST(PersonaSubscriber, ProfileAnchorAndCheckpoint) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S2", "alice", "bob", "role", "engineer",
                   "consolidated", "approved");
    seed_event(conn, "E2", "statement.derived", "S2", 5);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    EXPECT_EQ(neocortex::PersonaContainer(*adapter).read(conn, "default", "bob")
                  .dimensions.at("role"), "engineer");
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:05:00Z"), 0);
}

// volatile / rejected are excluded → no materialization.
TEST(PersonaSubscriber, IgnoresVolatileAndRejected) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S3", "self", "self", "trait_x", "y", "volatile", "review_requested");
    seed_event(conn, "E3", "statement.derived", "S3", 2);
    // consolidated+rejected must also be excluded (discriminates the review_status IN filter):
    seed_statement(conn, "S3b", "self", "self", "secret", "hidden", "consolidated", "rejected");
    seed_event(conn, "E3b", "statement.derived", "S3b", 3);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 2);
    EXPECT_FALSE(neocortex::PersonaContainer(*adapter).read(conn, "default", "self").found);
}

// statement.superseded (correction) also triggers rebuild — the primary_id is
// the NEW (forked) row, which carries the subject (Global Constraint: subject
// via primary_id, never aggregate_id).
TEST(PersonaSubscriber, SupersededTriggersRebuild) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S4new", "self", "self", "role", "staff_engineer",
                   "consolidated", "review_requested");
    seed_event(conn, "E4", "statement.superseded", "S4new", 7, "nonexistent-agg");
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    EXPECT_EQ(neocortex::PersonaContainer(*adapter).read(conn, "default", "self")
                  .dimensions.at("role"), "staff_engineer");
}

// The checkpoint must follow the outbox head. Advancing only to the last trigger
// event leaves every unrelated event after it counted as "lag" forever, so the
// Vitals page shows a permanent false backlog.
TEST(PersonaSubscriber, CheckpointAdvancesPastIrrelevantEvents) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S5", "self", "self", "trait_x", "y", "consolidated", "review_requested");
    seed_event(conn, "E5", "statement.derived", "S5", 1);
    seed_event(conn, "E5b", "vector.embedded", "S5", 2);
    seed_event(conn, "E5c", "pipeline.run_started", "S5", 3);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    EXPECT_EQ(persona_checkpoint(conn), 3);
}

// With no trigger event at all the checkpoint still has to reach the head.
TEST(PersonaSubscriber, CheckpointAdvancesWhenNoTriggerEventExists) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_event(conn, "E6", "vector.embedded", "none", 4);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 0);
    EXPECT_EQ(persona_checkpoint(conn), 4);
}

// A full batch must not jump to the head: pending trigger events would be skipped.
TEST(PersonaSubscriber, FullBatchDoesNotSkipPendingTriggerEvents) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S7a", "self", "self", "trait_a", "a", "consolidated", "review_requested");
    seed_statement(conn, "S7b", "self", "self", "trait_b", "b", "consolidated", "review_requested");
    seed_event(conn, "E7a", "statement.derived", "S7a", 1);
    seed_event(conn, "E7b", "statement.derived", "S7b", 2);
    seed_event(conn, "E7c", "vector.embedded", "S7b", 3);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z", 1), 1);
    EXPECT_EQ(persona_checkpoint(conn), 1);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:01:00Z", 1), 1);
    EXPECT_EQ(persona_checkpoint(conn), 2);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:02:00Z", 1), 0);
    EXPECT_EQ(persona_checkpoint(conn), 3);
}
