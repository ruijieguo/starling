#include "starling/bus/bus.hpp"
#include "starling/bus/statement_writer.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>

namespace starling::bus {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

extractor::ExtractedStatement minimal_stmt() {
    extractor::ExtractedStatement s;
    s.holder_id            = "cog-self";
    s.holder_tenant_id     = "default";
    s.holder_perspective   = schema::Perspective::FIRST_PERSON;
    s.subject_kind         = "cognizer";
    s.subject_id           = "cog-self";
    s.predicate            = "responsible_for";
    s.object_kind          = "str";
    s.object_value         = "auth";
    s.canonical_object_hash = "hash-auth";
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

TEST(BusStatementWrite, OpensAndCommitsItsOwnTransaction) {
    auto a = make_adapter();
    Bus bus(*a);
    auto outcome = bus.write(minimal_stmt(),
                             /*evidence_engram_id=*/"engram-1",
                             /*extraction_span_key=*/"span-1",
                             /*causation_parent=*/std::nullopt);
    EXPECT_TRUE(std::holds_alternative<StatementWriteAccepted>(outcome));
    auto& conn = a->connection();
    EXPECT_EQ(row_count(conn, "statements"), 1);
    EXPECT_EQ(row_count(conn, "bus_events"), 1);
}

}  // namespace starling::bus
