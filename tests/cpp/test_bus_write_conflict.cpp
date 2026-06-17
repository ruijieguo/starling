#include "starling/bus/bus.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/conflict_probe.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <chrono>
#include <memory>
#include <optional>
#include <string>
#include <utility>

namespace starling::bus {
namespace {

using starling::extractor::ExtractedStatement;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::persistence::MigrationRunner;
using starling::persistence::StmtHandle;

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

// Same as test_conflict_probe_scan.cpp's insert_row — direct INSERT bypassing StatementWriter.
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

// sub-project A phase 4: an OCCURRED event (episodic fact). Two such events that
// share subject+predicate+object (same theme) are a temporal SEQUENCE, not a
// contradiction. Same column shape as the belief make_stmt above but with
// modality=occurred and the episodic-event subject/predicate/object convention
// (entity:agent / moved / theme) so two of them collide on the conflict-probe
// prefilter just like the test_episodic_event_store rows.
ExtractedStatement make_occurred(
    double confidence,
    std::optional<std::string> vf = std::nullopt,
    std::optional<std::string> vt = std::nullopt) {
    ExtractedStatement s;
    s.holder_id             = "cog-self";
    s.holder_tenant_id      = "default";
    s.holder_perspective    = schema::Perspective::FIRST_PERSON;
    s.subject_kind          = "entity";
    s.subject_id            = "agent";
    s.predicate             = "moved";
    s.object_kind           = "str";
    s.object_value          = "ball";
    s.canonical_object_hash =
        "beadfeed01234567beadfeed01234567beadfeed01234567beadfeed01234567";
    s.modality              = schema::Modality::OCCURRED;
    s.polarity              = schema::Polarity::POS;
    s.confidence            = confidence;
    s.observed_at           = "2026-05-24T10:00:00Z";
    s.source_hash           = "eee";
    s.valid_from            = std::move(vf);
    s.valid_to              = std::move(vt);
    return s;
}

// Direct INSERT of an OCCURRED event row matching make_occurred's prefilter keys
// (so a later make_occurred write sees it as a same-key candidate). state default
// 'volatile' clamps any classification to PartialOverlap (the conflict-edge floor)
// in the no-skip baseline — proving the skip is what suppresses the edge.
void insert_occurred_row(Connection& conn, const std::string& id,
                         const std::string& vf, const std::string& vt,
                         const std::string& state = "volatile") {
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
    sqlite3_bind_text(h.get(), i++, "entity",                     -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "agent",                      -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "moved",                      -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "str",                        -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "ball",                       -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++,
        "beadfeed01234567beadfeed01234567beadfeed01234567beadfeed01234567",
        -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "v1",                         -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "occurred",                   -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), i++, "pos",                        -1, SQLITE_STATIC);
    sqlite3_bind_double(h.get(), i++, 0.9);
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

TEST(BusWriteConflict, NoConflictNoEdgeNoBeliefEvent) {
    auto a = open_fresh();
    Bus bus(*a);
    auto out = bus.write(make_stmt("pos", 0.85), "engram-1", "span-1", std::nullopt);
    (void)out;
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
}

TEST(BusWriteConflict, PartialOverlapWritesConflictsWithEdgeAndBeliefEvent) {
    auto a = open_fresh();
    // S_old below θ_severe (0.6) → forces partial_overlap classification.
    insert_row(a->connection(), "s_old", "pos", 0.50,
               "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
    Bus bus(*a);
    auto out = bus.write(
        make_stmt("neg", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        "engram-1", "span-1", std::nullopt);
    (void)out;
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
}

TEST(BusWriteConflict, BeliefConflictDebouncedWithinWindow) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.50,
               "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
    Bus bus(*a);
    // S_new conf=0.50 (also below θ_severe). Each S_new still classifies as
    // partial_overlap against s_old (both below theta clamps to partial); the
    // second S_new also classifies as partial_overlap against the first S_new
    // (same polarity, but both-below-theta clamps the Superseding path to
    // partial_overlap as well). All pairs share the same canonical_conflict_key
    // (same 7-tuple), so:
    //   - First write: insert_statement_edge succeeds → 1 conflicts_with edge.
    //   - Second write: insert_statement_edge deduped by partial UNIQUE index →
    //     noop (WARN to stderr), no second edge row.
    // belief.conflict events also debounce: only ONE survives the 10s window.
    bus.write(
        make_stmt("neg", 0.50, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        "engram-1", "span-1", std::nullopt);
    bus.write(
        make_stmt("neg", 0.50, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        "engram-2", "span-2", std::nullopt);
    // Only ONE conflicts_with edge (second write is deduped by UNIQUE index).
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
}

TEST(BusWriteConflict, AdjacentWritesAdjacentEdgeOnly) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z");
    Bus bus(*a);
    bus.write(
        make_stmt("pos", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-07-01T00:00:00Z")),
        "engram-1", "span-1", std::nullopt);
    EXPECT_EQ(1, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='adjacent'"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
}

// sub-project A phase 4: two OCCURRED events sharing subject+predicate+object
// (same theme "ball") but different intervals/locations are a temporal sequence
// — "agent moved ball" at T1 then again at T2 — NOT a contradiction. They share
// every conflict-probe prefilter key, so absent the OCCURRED skip the second
// write would emit a conflicts_with edge + belief.conflict event. With the skip,
// ConflictProbe::scan returns no match for OCCURRED, so neither is created.
TEST(BusWriteConflict, OccurredEventsAreNotConflicts) {
    auto a = open_fresh();
    // First event already on record (volatile → would clamp to PartialOverlap).
    insert_occurred_row(a->connection(), "ev_old",
                        "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
    Bus bus(*a);
    // Second event: same agent/action/theme, overlapping interval, different time.
    auto out = bus.write(
        make_occurred(0.9, std::string("2026-06-01T00:00:00Z"),
                      std::string("2026-12-31T00:00:00Z")),
        "engram-ev", "span-ev", std::nullopt);
    (void)out;
    // No conflict edge of any kind (conflicts_with / adjacent) over the events.
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='adjacent'"));
    // No belief.conflict event fired.
    EXPECT_EQ(0, count_rows(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
    // Both events still persisted as facts (sequence, not contradiction): the
    // pre-seeded ev_old plus the just-written OCCURRED row.
    EXPECT_EQ(2, count_rows(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE modality='occurred'"));
}

TEST(BusEventWindowBucket, BeliefConflictIs10sBucket) {
    using namespace std::chrono;
    // 2026-05-24T10:00:05Z = 1779976805 sec; 1779976805 / 10 = 177997680
    const auto t = system_clock::time_point{seconds{1779976805}};
    EXPECT_EQ("177997680", compute_window_bucket("belief.conflict", t));
    // Same 10s window
    const auto t_same = system_clock::time_point{seconds{1779976809}};
    EXPECT_EQ("177997680", compute_window_bucket("belief.conflict", t_same));
    // Next 10s window
    const auto t_next = system_clock::time_point{seconds{1779976810}};
    EXPECT_EQ("177997681", compute_window_bucket("belief.conflict", t_next));
}

TEST(BusEventWindowBucket, StatementLifecycleHasEmptyBucket) {
    using namespace std::chrono;
    const auto t = system_clock::time_point{seconds{1779976805}};
    EXPECT_EQ("", compute_window_bucket("statement.archived", t));
    EXPECT_EQ("", compute_window_bucket("statement.superseded", t));
}

}  // namespace
}  // namespace starling::bus
