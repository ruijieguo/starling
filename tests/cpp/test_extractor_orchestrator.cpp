#include "starling/extractor/extractor.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <stdexcept>

namespace starling::extractor {

namespace {

constexpr const char* kSuccessJson =
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
        .raw_xml = kSuccessJson, .ok = true});

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
    llm.set_default_response(LLMResponse{.raw_xml = kSuccessJson, .ok = true});

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

// Regression: one chunk yielding two statements that share predicate+object but
// differ in subject/polarity. extraction_span_key omits subject/polarity, so
// both map to the SAME span_key. Both are HEARSAY -> validator forces
// INFERRED_UNREVIEWED (not approved), so the StatementWriter cannot dedupe them
// to ChunkDuplicate and both reach the Accepted branch. Before the per-span
// record_attempt guard, the second statement re-inserted
// (pipeline_run_id, extraction_span_key, attempt_number) and threw
// "UNIQUE constraint failed: ... extraction_attempt ...", which 500'd the
// dashboard remember. Mirrors the live input "Carol told me she has taken over
// billing from Bob ... Carol is now responsible for billing, not Bob."
TEST(ExtractorOrchestrator, DualStatementSharedSpanKeyDoesNotDuplicateAttempt) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);
    // Same predicate ("responsible_for") + same object ("billing") -> identical
    // canonical_object_hash -> identical extraction_span_key. Different subject
    // (Carol/Bob) and polarity (POS/NEG).
    llm.set_default_response(LLMResponse{
        .raw_xml =
            R"JSON([{"holder":"self","holder_perspective":"HEARSAY","subject":"Carol","predicate":"responsible_for","object":"billing","modality":"BELIEVES","polarity":"POS","nesting_depth":0},)JSON"
            R"JSON({"holder":"self","holder_perspective":"HEARSAY","subject":"Bob","predicate":"responsible_for","object":"billing","modality":"BELIEVES","polarity":"NEG","nesting_depth":0}])JSON",
        .ok = true});

    // Before the fix this line threw the UNIQUE-constraint RuntimeError.
    auto r = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});

    EXPECT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(r.accepted_statement_ids.size(), 2u);   // both statements kept
    EXPECT_EQ(row_count(conn, "statements"), 2);
    // Exactly one Success attempt row for the shared span_key (the second is
    // intentionally not re-recorded), so no UNIQUE clash. The first statement's
    // row still covers the span for cross-run idempotency.
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='success'"), 1);
    EXPECT_EQ(row_count(conn, "pipeline_run", "status='finished'"), 1);
}

// 0027 cost attribution: ONE extract() call per attempt, but the success path
// writes one ledger row PER statement-span. take_cost() must charge the call's
// cost to exactly ONE row (the first written this iteration) so SUM(total_tokens)
// over the run equals the per-call cost — not N×. Two HEARSAY statements with
// DIFFERENT objects (billing/auth) → two distinct span_keys → two success rows
// from a single extract() call.
TEST(ExtractorOrchestrator, CostAttributedOncePerExtractCallNotPerSpanRow) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);
    llm.set_default_response(LLMResponse{
        .raw_xml =
            R"JSON([{"holder":"self","holder_perspective":"HEARSAY","subject":"Carol","predicate":"responsible_for","object":"billing","modality":"BELIEVES","polarity":"POS","nesting_depth":0},)JSON"
            R"JSON({"holder":"self","holder_perspective":"HEARSAY","subject":"Dana","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON",
        .ok = true,
        .prompt_tokens = 120, .completion_tokens = 34,
        .total_tokens = 154, .latency_ms = 512});

    auto r = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    ASSERT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    ASSERT_EQ(r.accepted_statement_ids.size(), 2u);   // two distinct spans written
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='success'"), 2);
    // The call's cost lands on exactly ONE success row (no double-count)...
    EXPECT_EQ(row_count(conn, "extraction_attempt",
        "prompt_tokens=120 AND completion_tokens=34 AND total_tokens=154 "
        "AND latency_ms=512"), 1);
    // ...and the other success row of the same call carries zero.
    EXPECT_EQ(row_count(conn, "extraction_attempt",
        "status='success' AND total_tokens=0"), 1);
    // So the run's total token cost equals the single call's cost, not 2×.
    EXPECT_EQ(row_count(conn, "extraction_attempt", "total_tokens=154"), 1);
}

// Failed responses still carry latency/tokens (see LLMResponse). Each retry is a
// distinct extract() call → its own attempt row → charged once. 3 retries → 3
// failed rows each bearing the call cost (SUM = 3×, correct: three real calls).
TEST(ExtractorOrchestrator, FailedAttemptsPersistPerCallCost) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);
    llm.set_default_response(LLMResponse{
        .ok = false, .error = "boom",
        .prompt_tokens = 10, .completion_tokens = 0,
        .total_tokens = 10, .latency_ms = 99});

    auto r = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    ASSERT_EQ(r.status, ExtractionRunResult::Status::FAILED);
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='failed'"), 3);
    EXPECT_EQ(row_count(conn, "extraction_attempt",
        "status='failed' AND total_tokens=10 AND latency_ms=99"), 3);
}

// Regression(noop 分支的同型洞): the Accepted-branch guard alone is not
// enough — on a RE-REMEMBER of an already-extracted text, BOTH same-span
// statements hit the cross-run noop branch, and the second noop record
// collided on (run_id, span_key, attempt_number) → whole rerun 500'd.
TEST(ExtractorOrchestrator, DualStatementSharedSpanKeyRerunNoopsOnce) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);
    llm.set_default_response(LLMResponse{
        .raw_xml =
            R"JSON([{"holder":"self","holder_perspective":"HEARSAY","subject":"Dana","predicate":"responsible_for","object":"rate limiter","modality":"BELIEVES","polarity":"POS","nesting_depth":0},)JSON"
            R"JSON({"holder":"self","holder_perspective":"HEARSAY","subject":"Bob","predicate":"responsible_for","object":"rate limiter","modality":"BELIEVES","polarity":"NEG","nesting_depth":0}])JSON",
        .ok = true});

    auto r1 = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    ASSERT_EQ(r1.status, ExtractionRunResult::Status::SUCCESS);
    ASSERT_EQ(r1.accepted_statement_ids.size(), 2u);

    // Rerun (same engram, same canned parse). Before the fix this threw the
    // UNIQUE-constraint RuntimeError out of the second noop record.
    auto r2 = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});
    EXPECT_EQ(r2.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(row_count(conn, "statements"), 2);                              // unchanged
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='noop'"), 1);     // recorded once
    EXPECT_EQ(row_count(conn, "bus_events", "event_type='extraction.noop'"), 1);
}

// Regression: a second-order (nesting_depth=2) emission — the prompt's own
// HEARSAY/nested examples teach the model to produce these — must complete the
// run. The old parser mapped depth>=2 to object_kind="statement", whose writer
// contract requires an existing parent UUID; free-text objects then aborted the
// whole run ("nesting_depth_writer: parent statement not found" → dashboard
// /api/remember 500).
TEST(ExtractorOrchestrator, SecondOrderNestedEmissionDoesNotAbortRun) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm);
    llm.set_default_response(LLMResponse{
        .raw_xml =
            R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Frank","predicate":"believes","object":"the database migration risk is manageable","modality":"BELIEVES","polarity":"POS","nesting_depth":2}])JSON",
        .ok = true});

    // Before the fix this threw RuntimeError out of the run.
    auto r = ex.run("engram-1", {1,2,3}, "cog-self", "default", {});

    EXPECT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(r.accepted_statement_ids.size(), 1u);
    EXPECT_EQ(row_count(conn, "statements", "object_kind='str'"), 1);
    EXPECT_EQ(row_count(conn, "statements", "nesting_depth=0"), 1);  // flat-text in P2
}

// Helper: read the single statements row's holder_id.
namespace {
std::string single_holder_id(persistence::Connection& conn) {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, "SELECT holder_id FROM statements LIMIT 1",
                           -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(std::string("single_holder_id prepare: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);
    if (sqlite3_step(h.get()) != SQLITE_ROW) return "";
    const unsigned char* t = sqlite3_column_text(h.get(), 0);
    return t ? reinterpret_cast<const char*>(t) : "";
}

// subject="Xiao Hong" is the desirer (character); holder is the narrator.
// With the flag ON, holder_id is attributed to the cognizer-resolved subject,
// not to the llm_holder field (which is always the narrator in practice).
constexpr const char* kNarratedDesireJson =
    R"JSON([{"holder":"narrator","holder_perspective":"INFERRED","subject":"Xiao Hong","predicate":"desires","object":"amusement park","modality":"DESIRES","polarity":"POS","nesting_depth":0}])JSON";
}  // namespace

// Flag DEFAULT-OFF: a narrated first-order desire ("Xiao Ming wants a computer")
// is still attributed to the agent (holder_id == the run arg), exactly as before.
TEST(ExtractorOrchestrator, NarratedMentalStateKeepsAgentHolderWhenFlagOff) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    Extractor ex(conn, llm, *a);  // store-adapter ctor; default policy (flag OFF)
    llm.set_default_response(LLMResponse{.raw_xml = kNarratedDesireJson, .ok = true});

    auto r = ex.run("engram-1", {1,2,3}, "narrator", "default", {});
    ASSERT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(row_count(conn, "statements"), 1);
    EXPECT_EQ(single_holder_id(conn), "narrator");  // unchanged: agent holds it
}

// Flag ON: the narrated first-order desire is re-attributed to its subject
// (the desirer, cognizer-resolved). holder=subject_id="Xiao Hong".
// The LLM's `holder` field carries "narrator" (as observed in production);
// we now use `subject` instead because it is reliably the attitude bearer
// for the desire family.
TEST(ExtractorOrchestrator, NarratedDesireReattributedToSubjectWhenFlagOn) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    ValidationPolicy pol;
    pol.attribute_first_order_mental_to_holder = true;
    Extractor ex(conn, llm, *a, /*prompt_template=*/"", pol);
    llm.set_default_response(LLMResponse{.raw_xml = kNarratedDesireJson, .ok = true});

    auto r = ex.run("engram-1", {1,2,3}, "narrator", "default", {});
    ASSERT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(row_count(conn, "statements"), 1);
    // Re-attributed to the subject (cognizer-resolved desirer), not llm_holder.
    EXPECT_EQ(single_holder_id(conn), "Xiao Hong");
    EXPECT_EQ(row_count(conn, "statements", "holder_id='narrator'"), 0);
}

// Flag ON but the LLM marked the statement second-order (nesting_depth=2):
// re-attribution is gated to first-order only, so holder stays the agent.
// Also doubles as a non-desire modality guard: BELIEVES at nesting_depth=0
// would also stay with the agent (subject=topic, not bearer).
TEST(ExtractorOrchestrator, SecondOrderNotReattributedEvenWhenFlagOn) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    ValidationPolicy pol;
    pol.attribute_first_order_mental_to_holder = true;
    Extractor ex(conn, llm, *a, "", pol);
    llm.set_default_response(LLMResponse{
        .raw_xml =
            R"JSON([{"holder":"narrator","holder_perspective":"INFERRED","subject":"Alice","predicate":"desires","object":"Bob to get a raise","modality":"DESIRES","polarity":"POS","nesting_depth":2}])JSON",
        .ok = true});

    auto r = ex.run("engram-1", {1,2,3}, "narrator", "default", {});
    ASSERT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(single_holder_id(conn), "narrator");  // second-order stays with agent
}

// Flag ON, non-desire modality (norm): re-attribution does not fire
// (gated to desire-family modalities), holder stays the agent.
TEST(ExtractorOrchestrator, NonDesireModalityNotReattributedWhenFlagOn) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn, "engram-1");

    FakeLLMAdapter llm;
    ValidationPolicy pol;
    pol.attribute_first_order_mental_to_holder = true;
    Extractor ex(conn, llm, *a, "", pol);
    // modality NORM_OUGHT (via the prompt alias "ENFORCES" → norm_ought) is not desire.
    llm.set_default_response(LLMResponse{
        .raw_xml =
            R"JSON([{"holder":"公司政策","holder_perspective":"QUOTED","subject":"production","predicate":"requires","object":"two approvals","modality":"ENFORCES","polarity":"POS","nesting_depth":0}])JSON",
        .ok = true});

    auto r = ex.run("engram-1", {1,2,3}, "narrator", "default", {});
    ASSERT_EQ(r.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(single_holder_id(conn), "narrator");
}

}  // namespace starling::extractor
