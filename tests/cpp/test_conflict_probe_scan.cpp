#include "starling/bus/conflict_probe.hpp"
#include "starling/bus/normalized_interval.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <optional>
#include <string>
#include <utility>

namespace starling::bus {
namespace {

using starling::extractor::ExtractedStatement;
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
    s.valid_from            = std::move(vf);
    s.valid_to              = std::move(vt);
    return s;
}

// Insert a single row into `statements`, mirroring StatementWriter columns.
// Empty vf/vt -> NULL.  state default 'consolidated'.
void insert_row(starling::persistence::Connection& conn,
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

NormalizedInterval iv(std::optional<std::string> vf, std::optional<std::string> vt) {
    return normalize_interval(std::move(vf), std::move(vt), std::nullopt);
}

TEST(ConflictProbeScan, NoCandidatesReturnsNullopt) {
    auto a = open_fresh();
    ConflictProbe p(a->connection());
    auto m = p.scan(make_stmt("neg", 0.85), iv(std::nullopt, std::nullopt));
    EXPECT_FALSE(m.has_value());
}

TEST(ConflictProbeScan, DirectContradictionAboveTheta) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("neg", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        iv(std::string("2026-06-01T00:00:00Z"), std::string("2026-12-31T00:00:00Z")));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::DirectContradiction, m->kind);
    EXPECT_EQ("s_old", m->matched_statement_id);
    EXPECT_EQ(64u, m->conflict_key_hex.size());
}

TEST(ConflictProbeScan, BelowThetaDowngradesToPartial) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.50,    // below theta
               "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("neg", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        iv(std::string("2026-06-01T00:00:00Z"), std::string("2026-12-31T00:00:00Z")));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
}

TEST(ConflictProbeScan, UnknownPolarityDoesNotTriggerDirectContradiction) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "unknown", 0.85,
               "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("pos", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        iv(std::string("2026-06-01T00:00:00Z"), std::string("2026-12-31T00:00:00Z")));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
}

TEST(ConflictProbeScan, UnknownIntervalClampsToPartial) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85);   // no interval
    ConflictProbe p(a->connection());
    auto m = p.scan(make_stmt("neg", 0.85), iv(std::nullopt, std::nullopt));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
}

TEST(ConflictProbeScan, CrossVersionDowngradesToPartial) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
               /*version=*/"v2");                         // synthetic v2
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("neg", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        iv(std::string("2026-06-01T00:00:00Z"), std::string("2026-12-31T00:00:00Z")));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
}

TEST(ConflictProbeScan, VolatileSOldClampsSevereToPartial) {
    // §3.5 T7-P1 only authorizes the SUPERSEDES atomic path against a
    // CONSOLIDATED S_old. A VOLATILE S_old that would otherwise classify as
    // DirectContradiction (opposite polarity, both above theta, intervals
    // overlap) must clamp to PartialOverlap so Bus::write does not invoke
    // apply_supersedes_atomic against a row whose state forbids the bypass.
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
               "v1", "volatile");
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("neg", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        iv(std::string("2026-06-01T00:00:00Z"), std::string("2026-12-31T00:00:00Z")));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
}

TEST(ConflictProbeScan, SupersedingWhenNewCoversOldSamePolarity) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z");
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("pos", 0.85, std::string("2026-05-01T00:00:00Z"), std::nullopt),
        iv(std::string("2026-05-01T00:00:00Z"), std::nullopt));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::Superseding, m->kind);
}

TEST(ConflictProbeScan, AdjacentWhenIntervalsTouch) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_old", "pos", 0.85,
               "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z");
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("pos", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-07-01T00:00:00Z")),
        iv(std::string("2026-06-01T00:00:00Z"), std::string("2026-07-01T00:00:00Z")));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::Adjacent, m->kind);
}

TEST(ConflictProbeScan, StrongestMatchWinsAcrossMultipleCandidates) {
    auto a = open_fresh();
    insert_row(a->connection(), "s_adj", "pos", 0.85,
               "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z");
    insert_row(a->connection(), "s_direct", "pos", 0.85,
               "2026-06-15T00:00:00Z", "2027-01-01T00:00:00Z");
    ConflictProbe p(a->connection());
    auto m = p.scan(
        make_stmt("neg", 0.85, std::string("2026-06-01T00:00:00Z"),
                  std::string("2026-12-31T00:00:00Z")),
        iv(std::string("2026-06-01T00:00:00Z"), std::string("2026-12-31T00:00:00Z")));
    ASSERT_TRUE(m.has_value());
    EXPECT_EQ(ConflictKind::DirectContradiction, m->kind);
    EXPECT_EQ("s_direct", m->matched_statement_id);
}

}  // namespace
}  // namespace starling::bus
