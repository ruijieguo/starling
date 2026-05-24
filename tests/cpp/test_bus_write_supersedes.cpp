#include "starling/bus/bus.hpp"
#include "starling/bus/conflict_probe.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>

namespace starling::bus {
namespace {

using starling::extractor::ExtractedStatement;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::MigrationRunner;
using starling::persistence::StmtHandle;

// GTest helpers don't share across translation units, so these are copied
// from tests/cpp/test_bus_write_conflict.cpp verbatim (D7 in the Task 8
// brief). Tests use ":memory:" databases to keep the suite hermetic.

std::unique_ptr<SqliteAdapter> open_fresh() {
    auto a = SqliteAdapter::open(":memory:");
    MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

ExtractedStatement make_stmt(
    const std::string& polarity, double confidence,
    std::optional<std::string> vf = std::nullopt,
    std::optional<std::string> vt = std::nullopt) {
    ExtractedStatement s;
    s.holder_id             = "cog-self";
    s.holder_tenant_id      = "default";
    s.holder_perspective    = schema::Perspective::FIRST_PERSON;
    s.subject_kind          = "cognizer";
    s.subject_id            = "cog-bob";
    s.predicate             = "responsible_for";
    s.object_kind           = "str";
    s.object_value          = "auth";
    s.canonical_object_hash =
        "deadbeef01234567deadbeef01234567deadbeef01234567deadbeef01234567";
    s.modality              = schema::Modality::BELIEVES;
    s.polarity              = (polarity == "pos") ? schema::Polarity::POS
                                                  : schema::Polarity::NEG;
    s.confidence            = confidence;
    s.observed_at           = "2026-05-24T10:00:00Z";
    s.source_hash           = "fff";
    s.valid_from            = std::move(vf);
    s.valid_to              = std::move(vt);
    return s;
}

void insert_row(Connection& conn,
                const std::string& id, const std::string& polarity,
                double confidence,
                const std::string& vf = "", const std::string& vt = "",
                const std::string& version = "v1",
                const std::string& state = "consolidated") {
    const char* sql =
        "INSERT INTO statements("
        "id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,"
        "polarity,confidence,observed_at,salience,affect_json,activation,"
        "last_accessed,provenance,consolidation_state,review_status,"
        "valid_from,valid_to,created_at,updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr));
    StmtHandle h(raw);
    int i = 1;
    sqlite3_bind_text(h.get(), i++, id.c_str(),                   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "default",                    -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "cog-self",                   -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "first_person",               -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "cognizer",                   -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "cog-bob",                    -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "responsible_for",            -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "str",                        -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "auth",                       -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++,
        "deadbeef01234567deadbeef01234567deadbeef01234567deadbeef01234567",
        -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, version.c_str(),              -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "believes",                   -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, polarity.c_str(),             -1, SQLITE_TRANSIENT);
    sqlite3_bind_double(h.get(), i++, confidence);
    sqlite3_bind_text(h.get(), i++, "2026-05-24T09:00:00Z",       -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 0.5);
    sqlite3_bind_text(h.get(), i++, "{}",                         -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 1.0);
    sqlite3_bind_text(h.get(), i++, "2026-05-24T09:00:00Z",       -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "user_input",                 -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, state.c_str(),                -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "approved",                   -1, SQLITE_STATIC);
    if (vf.empty()) sqlite3_bind_null(h.get(), i++);
    else            sqlite3_bind_text(h.get(), i++, vf.c_str(),   -1, SQLITE_TRANSIENT);
    if (vt.empty()) sqlite3_bind_null(h.get(), i++);
    else            sqlite3_bind_text(h.get(), i++, vt.c_str(),   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), i++, "2026-05-24T09:00:00Z",       -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "2026-05-24T09:00:00Z",       -1, SQLITE_STATIC);
    ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.get()));
}

int count_rows(Connection& conn, const std::string& sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr));
    StmtHandle h(raw);
    EXPECT_EQ(SQLITE_ROW, sqlite3_step(h.get()));
    return sqlite3_column_int(h.get(), 0);
}

std::string read_string(Connection& conn, const std::string& sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(SQLITE_OK, sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr));
    StmtHandle h(raw);
    EXPECT_EQ(SQLITE_ROW, sqlite3_step(h.get()));
    const unsigned char* txt = sqlite3_column_text(h.get(), 0);
    return txt ? std::string(reinterpret_cast<const char*>(txt)) : std::string{};
}

TEST(BusWriteSupersedes, DirectContradictionAtomicCommit) {
    auto a = open_fresh();
    // S_old: pos, conf 0.85, CONSOLIDATED. S_new: neg, conf 0.85, fully covers
    // S_old's interval -> direct_contradiction.
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z",
               "v1", "consolidated");
    Bus bus(*a);
    auto out = bus.write(
        make_stmt("neg", 0.85, std::string("2026-05-01T00:00:00Z"),
                  std::string("2027-01-01T00:00:00Z")),
        "engram-1", "span-1", std::nullopt);
    (void)out;

    // Invariant 1: S_new (volatile) + S_old (archived). No row in
    // replaying_reconsolidating — bypassed per §3.5 T7-P1.
    EXPECT_EQ(2, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='archived'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='volatile'"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='replaying_reconsolidating'"));

    // Invariant 2: 1 SUPERSEDES edge S_new -> S_old.
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"));

    // Invariant 3: 3 outbox events: statement.written, statement.archived,
    // statement.superseded.
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.written'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.superseded'"));

    // Invariant 4: no may_overlap_with / conflicts_with edges leaked.
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges "
        "WHERE edge_kind IN ('may_overlap_with','conflicts_with')"));

    // Invariant 5: archive event payload encodes reason="direct_contradiction".
    const std::string payload = read_string(a->connection(),
        "SELECT payload_json FROM bus_events WHERE event_type='statement.archived'");
    EXPECT_NE(std::string::npos, payload.find("direct_contradiction"));

    // Invariant 6: superseded event payload carries S_old as old_statement_id —
    // traceability anchor for downstream consumers.
    const std::string sup_payload = read_string(a->connection(),
        "SELECT payload_json FROM bus_events WHERE event_type='statement.superseded'");
    EXPECT_NE(std::string::npos, sup_payload.find("\"old_statement_id\""));
    EXPECT_NE(std::string::npos, sup_payload.find("s_old"));
}

TEST(BusWriteSupersedes, SupersedingAtomicCommit) {
    auto a = open_fresh();
    // S_old: pos, conf 0.85, narrower window. S_new: pos, conf 0.85, wider
    // window that covers S_old -> superseding (same polarity).
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z",
               "v1", "consolidated");
    Bus bus(*a);
    auto out = bus.write(
        make_stmt("pos", 0.85, std::string("2026-05-01T00:00:00Z"),
                  std::string("2027-01-01T00:00:00Z")),
        "engram-1", "span-1", std::nullopt);
    (void)out;

    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='archived'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.superseded'"));

    // Reason discriminator: "superseding" not "direct_contradiction".
    const std::string payload = read_string(a->connection(),
        "SELECT payload_json FROM bus_events WHERE event_type='statement.archived'");
    EXPECT_NE(std::string::npos, payload.find("superseding"));
    EXPECT_EQ(std::string::npos, payload.find("direct_contradiction"));
}

// Rollback path: the helper's archive UPDATE has a defensive
// `WHERE consolidation_state='consolidated'` guard. If S_old's state changed
// between probe and apply (a real-world race), sqlite3_changes() returns 0
// and the helper throws std::runtime_error. The TransactionGuard destructor
// then rolls back the entire write — no S_new, no edge, no events.
//
// We can't reproduce a true probe/apply race in a single-threaded test, so
// we simulate one with a SQLite BEFORE UPDATE trigger that flips S_old's
// state to 'replaying_reconsolidating' before the helper's UPDATE matches.
// The result is identical to the race: WHERE state='consolidated' affects
// zero rows, the guard throws, and the tx rolls back.
TEST(BusWriteSupersedes, RollbackOnSOldUpdateFailure) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z",
               "v1", "consolidated");

    // Race simulator: a BEFORE UPDATE trigger that fires RAISE(IGNORE)
    // aborts the triggering UPDATE statement before any row is touched.
    // sqlite3_step() still returns SQLITE_DONE and sqlite3_changes() is 0
    // — the same observable outcome as the helper's
    // `WHERE consolidation_state='consolidated'` guard matching zero rows
    // when S_old's state changed between probe and apply. The simulation
    // is not byte-identical to the race (the WHERE never evaluates), but
    // the helper's defensive `sqlite3_changes() != 1` check sees the same
    // signal and throws std::runtime_error.
    char* err = nullptr;
    ASSERT_EQ(SQLITE_OK, sqlite3_exec(a->connection().raw(),
        "CREATE TRIGGER race_simulator BEFORE UPDATE OF consolidation_state "
        "ON statements WHEN NEW.consolidation_state='archived' AND OLD.id='s_old' "
        "BEGIN "
        "  SELECT RAISE(IGNORE); "
        "END;",
        nullptr, nullptr, &err));

    Bus bus(*a);
    EXPECT_THROW(
        bus.write(
            make_stmt("neg", 0.85, std::string("2026-05-01T00:00:00Z"),
                      std::string("2027-01-01T00:00:00Z")),
            "engram-1", "span-1", std::nullopt),
        std::runtime_error);

    // Tx fully rolled back: only the original s_old row remains (still
    // 'consolidated' — the trigger's intermediate write is also rolled back),
    // no new statements, no edges, no bus_events.
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='consolidated'"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events"));
}

// Disjoint intervals + opposite polarity -> classifies as adjacent (or
// nothing severe), NOT direct_contradiction. The SUPERSEDES path must not
// fire.
TEST(BusWriteSupersedes, NotTriggeredWhenIntervalsDoNotOverlap) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z",
               "v1", "consolidated");
    Bus bus(*a);
    bus.write(
        make_stmt("neg", 0.85, std::string("2027-01-01T00:00:00Z"),
                  std::string("2027-12-31T00:00:00Z")),
        "engram-1", "span-1", std::nullopt);

    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='archived'"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived'"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.superseded'"));
}

}  // namespace
}  // namespace starling::bus
