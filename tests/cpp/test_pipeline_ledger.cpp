#include <gtest/gtest.h>

#include "starling/bus/pipeline_ledger.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

using starling::bus::ExtractionStatus;
using starling::bus::PipelineLedger;
using starling::bus::PipelineStatus;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::SqliteError;

namespace {

Connection fresh_db() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

int count(Connection& c, const char* sql) {
    sqlite3_stmt* s = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(c.raw(), sql, -1, &s, nullptr), SQLITE_OK);
    EXPECT_EQ(sqlite3_step(s), SQLITE_ROW);
    const int n = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return n;
}

}  // namespace

TEST(PipelineLedger, StartFinishRoundTrip) {
    auto c = fresh_db();
    PipelineLedger l(c);
    const auto run_id = l.start_run("t1", "msg-uri-1", "{\"k\":\"v\"}");
    EXPECT_FALSE(run_id.empty());
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM pipeline_run WHERE status='started'"), 1);
    l.finish_run(run_id, PipelineStatus::Finished);
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM pipeline_run WHERE status='finished'"), 1);
}

TEST(PipelineLedger, AttemptUniquePerSpanAndAttemptNumber) {
    auto c = fresh_db();
    PipelineLedger l(c);
    const auto run_id = l.start_run("t1", "msg-uri-1");
    l.record_attempt(run_id, "span-1", 1, ExtractionStatus::Success, "<xml/>");
    EXPECT_THROW(
        l.record_attempt(run_id, "span-1", 1, ExtractionStatus::Success, "<xml/>"),
        SqliteError);
    l.record_attempt(run_id, "span-1", 2, ExtractionStatus::PartialSuccess);
    l.record_attempt(run_id, "span-2", 1, ExtractionStatus::Success);
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM extraction_attempt"), 3);
}

TEST(PipelineLedger, AttemptStatusEnumStrings) {
    auto c = fresh_db();
    PipelineLedger l(c);
    const auto run_id = l.start_run("t1", "ref");
    l.record_attempt(run_id, "s1", 1, ExtractionStatus::Failed, {}, "boom");
    EXPECT_EQ(count(c,
        "SELECT COUNT(*) FROM extraction_attempt "
        "WHERE status='failed' AND error='boom'"), 1);
}
