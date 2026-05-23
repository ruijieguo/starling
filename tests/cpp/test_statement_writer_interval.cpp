#include "starling/bus/statement_writer.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/schema/statement_enums.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

namespace starling::bus {

namespace {

// Helper: open an in-memory DB and run migrations.
std::unique_ptr<persistence::SqliteAdapter> make_test_db() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

extractor::ExtractedStatement make_base_stmt() {
    extractor::ExtractedStatement s;
    s.holder_id            = "holder-uuid-001";
    s.holder_tenant_id     = "tenant-001";
    s.holder_perspective   = schema::Perspective::FIRST_PERSON;
    s.subject_kind         = "entity";
    s.subject_id           = "entity-uuid-001";
    s.predicate            = "responsible_for";
    s.object_kind          = "str";
    s.object_value         = "auth";
    s.canonical_object_hash =
        "deadbeef01234567deadbeef01234567deadbeef01234567deadbeef01234567";
    s.modality             = schema::Modality::BELIEVES;
    s.polarity             = schema::Polarity::POS;
    s.confidence           = 0.9;
    s.observed_at          = "2026-01-01T00:00:00Z";
    s.chunk_index          = 0;
    s.source_hash          = "src-hash-001";
    s.perceived_by         = {"holder-uuid-001"};
    s.provenance           = schema::StatementProvenance::USER_INPUT;
    s.review_status        = schema::ReviewStatus::APPROVED;
    return s;
}

// Run the writer inside an explicit transaction, matching the contract that
// callers (Bus::write or tests) open BEGIN IMMEDIATE before invoking.
StatementWriteOutcome run_write(persistence::Connection& conn,
                                const extractor::ExtractedStatement& s) {
    sqlite3* db = conn.raw();
    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);
    StatementWriter w(conn);
    auto outcome = w.write(s,
                           /*evidence_engram_id=*/"engram-001",
                           /*extraction_span_key=*/"span-001",
                           /*causation_parent=*/std::nullopt);
    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
    return outcome;
}

}  // namespace

TEST(StatementWriterInterval, NullIntervalRoundTrip) {
    auto a = make_test_db();
    auto& conn = a->connection();

    auto outcome = run_write(conn, make_base_stmt());
    ASSERT_TRUE(std::holds_alternative<StatementWriteAccepted>(outcome));
    auto& accepted = std::get<StatementWriteAccepted>(outcome);

    sqlite3_stmt* raw = nullptr;
    int rc = sqlite3_prepare_v2(
        conn.raw(),
        "SELECT valid_from, valid_to, event_time_start FROM statements WHERE id = ?",
        -1, &raw, nullptr);
    ASSERT_EQ(rc, SQLITE_OK);
    sqlite3_bind_text(raw, 1, accepted.stmt_id.c_str(), -1, SQLITE_STATIC);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_type(raw, 0), SQLITE_NULL);
    EXPECT_EQ(sqlite3_column_type(raw, 1), SQLITE_NULL);
    EXPECT_EQ(sqlite3_column_type(raw, 2), SQLITE_NULL);
    sqlite3_finalize(raw);
}

TEST(StatementWriterInterval, FullIntervalRoundTrip) {
    auto a = make_test_db();
    auto& conn = a->connection();

    auto stmt = make_base_stmt();
    stmt.valid_from       = "2026-01-01T00:00:00Z";
    stmt.valid_to         = "2026-06-01T00:00:00Z";
    stmt.event_time_start = "2026-01-15T12:00:00Z";

    auto outcome = run_write(conn, stmt);
    ASSERT_TRUE(std::holds_alternative<StatementWriteAccepted>(outcome));
    auto& accepted = std::get<StatementWriteAccepted>(outcome);

    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(
        conn.raw(),
        "SELECT valid_from, valid_to, event_time_start FROM statements WHERE id = ?",
        -1, &raw, nullptr);
    sqlite3_bind_text(raw, 1, accepted.stmt_id.c_str(), -1, SQLITE_STATIC);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_ROW);
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 0)),
                 "2026-01-01T00:00:00Z");
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 1)),
                 "2026-06-01T00:00:00Z");
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 2)),
                 "2026-01-15T12:00:00Z");
    sqlite3_finalize(raw);
}

TEST(StatementWriterInterval, ValidFromOnlyRoundTrip) {
    auto a = make_test_db();
    auto& conn = a->connection();

    auto stmt = make_base_stmt();
    stmt.valid_from = "2026-03-01T00:00:00Z";

    auto outcome = run_write(conn, stmt);
    ASSERT_TRUE(std::holds_alternative<StatementWriteAccepted>(outcome));
    auto& accepted = std::get<StatementWriteAccepted>(outcome);

    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(
        conn.raw(),
        "SELECT valid_from, valid_to, event_time_start FROM statements WHERE id = ?",
        -1, &raw, nullptr);
    sqlite3_bind_text(raw, 1, accepted.stmt_id.c_str(), -1, SQLITE_STATIC);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_ROW);
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 0)),
                 "2026-03-01T00:00:00Z");
    EXPECT_EQ(sqlite3_column_type(raw, 1), SQLITE_NULL);
    EXPECT_EQ(sqlite3_column_type(raw, 2), SQLITE_NULL);
    sqlite3_finalize(raw);
}

}  // namespace starling::bus
