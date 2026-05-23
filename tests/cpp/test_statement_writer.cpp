#include "starling/bus/statement_writer.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <memory>

namespace starling::bus {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

extractor::ExtractedStatement minimal_stmt(const std::string& object_value,
                                           const std::string& object_hash) {
    extractor::ExtractedStatement s;
    s.holder_id            = "cog-self";
    s.holder_tenant_id     = "default";
    s.holder_perspective   = schema::Perspective::FIRST_PERSON;
    s.subject_kind         = "cognizer";
    s.subject_id           = "cog-self";
    s.predicate            = "responsible_for";
    s.object_kind          = "str";
    s.object_value         = object_value;
    s.canonical_object_hash = object_hash;
    s.modality             = schema::Modality::BELIEVES;
    s.polarity             = schema::Polarity::POS;
    s.confidence           = 0.85;
    s.observed_at          = "2026-05-23T10:00:00Z";
    s.chunk_index          = 0;
    s.source_hash          = "fff";
    s.perceived_by         = {"cog-self"};
    s.provenance           = schema::StatementProvenance::USER_INPUT;
    s.review_status        = schema::ReviewStatus::APPROVED;
    return s;
}

int row_count(persistence::Connection& conn, const std::string& table) {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(db, ("SELECT COUNT(*) FROM " + table).c_str(), -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    return sqlite3_column_int(h.get(), 0);
}

}  // namespace

TEST(StatementWriter, WritesStatementAndOutboxAtomically) {
    auto a = make_adapter();
    auto& conn = a->connection();

    sqlite3* db = conn.raw();
    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);
    StatementWriter w(conn);
    auto outcome = w.write(minimal_stmt("auth", "hash-auth"),
                           /*evidence_engram_id=*/"engram-1",
                           /*extraction_span_key=*/"span-1",
                           /*causation_parent=*/std::nullopt);
    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);

    EXPECT_TRUE(std::holds_alternative<StatementWriteAccepted>(outcome));
    EXPECT_EQ(row_count(conn, "statements"), 1);
    EXPECT_EQ(row_count(conn, "bus_events"), 1);
}

TEST(StatementWriter, ChunkDuplicateForcesReviewRequested) {
    auto a = make_adapter();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();

    // first write — APPROVED
    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);
    StatementWriter w(conn);
    w.write(minimal_stmt("auth", "hash-auth"),
            "engram-1", "span-1", std::nullopt);
    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);

    // second write, same (predicate, canonical_object) within the same
    // engram — must force REVIEW_REQUESTED on the new row, NOT overwrite.
    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);
    auto outcome2 = w.write(minimal_stmt("auth", "hash-auth"),
                            "engram-1", "span-1", std::nullopt);
    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);

    EXPECT_TRUE(std::holds_alternative<StatementWriteChunkDuplicate>(outcome2));

    // both rows should exist (two statements; second is REVIEW_REQUESTED).
    EXPECT_EQ(row_count(conn, "statements"), 2);

    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(db,
        "SELECT review_status FROM statements ORDER BY created_at ASC", -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)), "approved");
    sqlite3_step(h.get());
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)), "review_requested");
}

TEST(StatementWriter, BusEventCarriesExtractionSpanKey) {
    auto a = make_adapter();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();
    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);
    StatementWriter w(conn);
    w.write(minimal_stmt("auth", "hash-auth"),
            "engram-1", "span-key-aaa", std::nullopt);
    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);

    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(db,
        "SELECT payload_json FROM bus_events WHERE event_type='statement.written'",
        -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    ASSERT_EQ(sqlite3_step(h.get()), SQLITE_ROW);
    const std::string payload = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
    EXPECT_NE(payload.find("\"extraction_span_key\":\"span-key-aaa\""), std::string::npos);
}

TEST(StatementWriter, RollbackLeavesNothingBehind) {
    auto a = make_adapter();
    auto& conn = a->connection();
    sqlite3* db = conn.raw();

    sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);
    StatementWriter w(conn);
    w.write(minimal_stmt("auth", "hash-auth"),
            "engram-1", "span-1", std::nullopt);
    sqlite3_exec(db, "ROLLBACK", nullptr, nullptr, nullptr);

    EXPECT_EQ(row_count(conn, "statements"), 0);
    EXPECT_EQ(row_count(conn, "bus_events"), 0);
}

}  // namespace starling::bus
