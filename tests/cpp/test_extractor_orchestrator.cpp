#include "starling/extractor/extractor.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <stdexcept>

namespace starling::extractor {

namespace {

constexpr const char* kSuccessXml =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void seed_engram(persistence::Connection& conn, std::string_view /*id*/) {
    sqlite3* db = conn.raw();
    sqlite3_exec(db,
        "INSERT INTO engrams("
        "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
        "  privacy_class,retention_mode,refcount,payload_inline,created_at"
        ") VALUES("
        "  'engram-1','default','hash-1','user_input','store','whole_record',"
        "  'internal','audit_retain',0,X'','2026-05-23T10:00:00Z')",
        nullptr, nullptr, nullptr);
}

int row_count(persistence::Connection& conn, const std::string& table,
              const std::string& where = "1=1") {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            ("SELECT COUNT(*) FROM " + table + " WHERE " + where).c_str(),
            -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(std::string("row_count prepare failed: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    return sqlite3_column_int(h.get(), 0);
}

}  // namespace

TEST(ExtractorOrchestrator, AcceptedPathWritesStatementAndPipelineRun) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);

    llm.set_default_response(LLMResponse{
        .raw_xml = kSuccessXml, .ok = true});

    ExtractionRunResult r = ex.run(
        /*engram_ref_id=*/"engram-1",
        /*payload_bytes=*/std::vector<std::uint8_t>{1,2,3},
        /*holder_id=*/"cog-self",
        /*holder_tenant_id=*/"default",
        /*existing_ref_map=*/{});

    EXPECT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(r.accepted_statement_ids.size(), 1u);
    EXPECT_EQ(row_count(conn, "statements"), 1);
    EXPECT_EQ(row_count(conn, "pipeline_run", "status='finished'"), 1);
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='success'"), 1);
    EXPECT_EQ(row_count(conn, "bus_events", "event_type='statement.written'"), 1);
    EXPECT_EQ(row_count(conn, "bus_events", "event_type='pipeline.run_started'"), 1);
    EXPECT_EQ(row_count(conn, "bus_events", "event_type='pipeline.run_completed'"), 1);
}

TEST(ExtractorOrchestrator, AdapterFailureRetriesAndDeadletters) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;  // no response set; all calls return ok=false
    Extractor ex(conn, llm);

    auto r = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    EXPECT_EQ(r.status, ExtractionRunResult::Status::FAILED);
    EXPECT_EQ(r.accepted_statement_ids.size(), 0u);
    // 3 retries -> 3 attempt rows with status=failed
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='failed'"), 3);
    EXPECT_EQ(row_count(conn, "pipeline_run", "status='failed'"), 1);
    EXPECT_EQ(row_count(conn, "bus_events", "event_type='extraction.failed'"), 3);
    EXPECT_EQ(row_count(conn, "bus_events", "event_type='pipeline.run_failed'"), 1);
    EXPECT_EQ(row_count(conn, "statements"), 0);
}

TEST(ExtractorOrchestrator, ParseErrorIsRetriedThenFails) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);

    // Non-array top level -> ParseError -> orchestrator retries then fails.
    llm.set_default_response(LLMResponse{
        .raw_xml = "not a json array", .ok = true});

    auto r = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    EXPECT_EQ(r.status, ExtractionRunResult::Status::FAILED);
    // 3 attempts x 1 chunk = 3 attempt rows; all status=failed.
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='failed'"), 3);
}

TEST(ExtractorOrchestrator, IdempotencyOnRerun) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);
    llm.set_default_response(LLMResponse{.raw_xml = kSuccessXml, .ok = true});

    // First run: writes 1 Statement.
    auto r1 = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    EXPECT_EQ(r1.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(row_count(conn, "statements"), 1);

    // Second run: same Engram, same prompt -> same prompt_input_hash -> same
    // adapter response -> but extractor detects extraction_span_key already
    // wrote a Statement and emits NOOP. Ledger gets a NOOP attempt; no new
    // Statement.
    auto r2 = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    EXPECT_EQ(r2.status, ExtractionRunResult::Status::SUCCESS);  // noop is still a successful run
    EXPECT_EQ(row_count(conn, "statements"), 1);  // unchanged
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='noop'"), 1);
    EXPECT_EQ(row_count(conn, "bus_events", "event_type='extraction.noop'"), 1);
}

}  // namespace starling::extractor
