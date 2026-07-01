// Task 3a.3–3a.6: PipelineRunStore — full method coverage.
// Covers enqueue/find_active_run/get (3a.3), claim/reclaim/confirm/record_checkpoint
// (3a.4–3a.5), and dead_letter/cancel/record_stage_timing/partial_terminal_rollup (3a.6).
#include <gtest/gtest.h>

#include "starling/governance/pipeline_run_store.hpp"
#include "starling/governance/stage_timer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <array>
#include <span>
#include <sqlite3.h>
#include <stdexcept>
#include <string>

using starling::governance::NewRun;
using starling::governance::PipelineKind;
using starling::governance::PipelineRun;
using starling::governance::PipelineRunStatus;
using starling::governance::PipelineRunStore;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::TransactionGuard;

namespace {

// Open an in-memory DB with all migrations applied — mirrors sibling tests.
Connection fresh_db() {
    auto conn = Connection::open(":memory:");
    MigrationRunner(conn.raw()).migrate_to_latest();
    return conn;
}

// Minimal NewRun builder — replay pipeline with sensible defaults.
NewRun make_spec(
        PipelineKind kind = PipelineKind::Replay,
        std::string tenant_id = "tenant-1",
        std::string aggregate_id = "agg-abc",
        std::string input_hash = "hash-001") {
    NewRun spec;
    spec.kind             = kind;
    spec.tenant_id        = std::move(tenant_id);
    spec.aggregate_id     = std::move(aggregate_id);
    spec.input_hash       = std::move(input_hash);
    spec.profile_name     = "default";
    spec.idempotency_key  = "idem-001";
    spec.pipeline_name    = "replay";
    spec.pipeline_version = "1";
    spec.step_contracts   = "[]";
    return spec;
}

}  // namespace

// ── 1. enqueue → QUEUED + get round-trip + JSON defaults ─────────────────────

TEST(PipelineRunStore, EnqueueReturnsQueuedRun) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun run = store.enqueue(make_spec());

    EXPECT_FALSE(run.id.empty());
    EXPECT_EQ(run.kind,         PipelineKind::Replay);
    EXPECT_EQ(run.aggregate_id, "agg-abc");
    EXPECT_EQ(run.tenant_id,    "tenant-1");
    EXPECT_EQ(run.status,       PipelineRunStatus::Queued);
    EXPECT_EQ(run.retry_count,  0LL);
}

TEST(PipelineRunStore, EnqueueGetRoundTrip) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun run = store.enqueue(make_spec());
    const auto fetched    = store.get(run.id);

    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->id,           run.id);
    EXPECT_EQ(fetched->kind,         PipelineKind::Replay);
    EXPECT_EQ(fetched->aggregate_id, "agg-abc");
    EXPECT_EQ(fetched->tenant_id,    "tenant-1");
    EXPECT_EQ(fetched->status,       PipelineRunStatus::Queued);
}

TEST(PipelineRunStore, EnqueueJsonDefaults) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun run = store.enqueue(make_spec());

    // JSON columns must have their table DEFAULT values on a fresh QUEUED row.
    EXPECT_EQ(run.item_run_ids,     "[]");
    EXPECT_EQ(run.watermark,        "{}");
    EXPECT_EQ(run.progress,         "{}");
    EXPECT_EQ(run.counters,         "{}");
    EXPECT_EQ(run.warnings,         "[]");
    EXPECT_EQ(run.stage_timings_ms, "[]");
}

// ── 2. Dedup (invariant 1): same (kind,tenant,agg,hash) → same run id ────────

TEST(PipelineRunStore, DeduplicateSameKey) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun first  = store.enqueue(make_spec());
    const PipelineRun second = store.enqueue(make_spec());

    // Must return the SAME row — no second INSERT.
    EXPECT_EQ(second.id, first.id);
}

// ── 3. Tenant isolation: different tenant_id → new run ───────────────────────

TEST(PipelineRunStore, DifferentTenantCreatesNewRun) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun run1 = store.enqueue(make_spec(PipelineKind::Replay, "tenant-A"));
    const PipelineRun run2 = store.enqueue(make_spec(PipelineKind::Replay, "tenant-B"));

    EXPECT_NE(run2.id, run1.id);
    EXPECT_EQ(run1.tenant_id, "tenant-A");
    EXPECT_EQ(run2.tenant_id, "tenant-B");
}

// ── 4. Different input_hash → new run ────────────────────────────────────────

TEST(PipelineRunStore, DifferentInputHashCreatesNewRun) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    auto spec_a = make_spec();
    spec_a.input_hash = "hash-aaa";
    auto spec_b = make_spec();
    spec_b.input_hash = "hash-bbb";

    const PipelineRun run_a = store.enqueue(spec_a);
    const PipelineRun run_b = store.enqueue(spec_b);

    EXPECT_NE(run_b.id, run_a.id);
}

// ── 5. find_active_run: none → some ──────────────────────────────────────────

TEST(PipelineRunStore, FindActiveRunNoneWhenEmpty) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const auto res = store.find_active_run(
        PipelineKind::Replay, "tenant-1", "agg-xyz", "hash-xyz");
    EXPECT_FALSE(res.has_value());
}

TEST(PipelineRunStore, FindActiveRunReturnsSomeAfterEnqueue) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun run = store.enqueue(make_spec());

    const auto found = store.find_active_run(
        PipelineKind::Replay, "tenant-1", "agg-abc", "hash-001");
    ASSERT_TRUE(found.has_value());
    EXPECT_EQ(found->id,     run.id);
    EXPECT_EQ(found->status, PipelineRunStatus::Queued);
}

// ── 6. CX-10: ComplianceErase → throws ───────────────────────────────────────

TEST(PipelineRunStore, EnqueueComplianceEraseThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    NewRun spec = make_spec(PipelineKind::ComplianceErase);
    EXPECT_THROW(store.enqueue(spec), std::runtime_error);
}

// ── 7. get missing id → nullopt ──────────────────────────────────────────────

TEST(PipelineRunStore, GetMissingIdReturnsNullopt) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const auto res = store.get("does-not-exist-id");
    EXPECT_FALSE(res.has_value());
}

// ── 8. claim: QUEUED → RUNNING ────────────────────────────────────────────────

TEST(PipelineRunStore, ClaimTransitionsQueuedToRunning) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    const PipelineRun claimed = store.claim(queued.id, "worker-A", "2026-06-29T12:00:00Z");

    EXPECT_EQ(claimed.status, PipelineRunStatus::Running);
    ASSERT_TRUE(claimed.worker_id.has_value());
    EXPECT_EQ(*claimed.worker_id, "worker-A");
    ASSERT_TRUE(claimed.lease_until.has_value());
    EXPECT_EQ(*claimed.lease_until, "2026-06-29T12:00:00Z");
}

// ── 9. claim: RUNNING is still active via find_active_run ────────────────────

TEST(PipelineRunStore, ClaimedRunIsStillActive) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    store.claim(queued.id, "worker-A", "2026-06-29T12:00:00Z");

    const auto found = store.find_active_run(
        PipelineKind::Replay, "tenant-1", "agg-abc", "hash-001");
    ASSERT_TRUE(found.has_value());
    EXPECT_EQ(found->id,     queued.id);
    EXPECT_EQ(found->status, PipelineRunStatus::Running);
}

// ── 10. claim: 2nd claim on RUNNING → throws ─────────────────────────────────

TEST(PipelineRunStore, ClaimOnRunningThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    store.claim(queued.id, "worker-A", "2026-06-29T12:00:00Z");

    EXPECT_THROW(
        store.claim(queued.id, "worker-B", "2026-06-29T13:00:00Z"),
        std::runtime_error);
}

// ── 11. claim: non-existent run_id → throws ──────────────────────────────────

TEST(PipelineRunStore, ClaimNonExistentRunThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    EXPECT_THROW(
        store.claim("no-such-run-id", "worker-A", "2026-06-29T12:00:00Z"),
        std::runtime_error);
}

// ── Helper: enqueue + claim → RUNNING run ────────────────────────────────────

namespace {

PipelineRun enqueue_and_claim(
        PipelineRunStore& store,
        std::string_view worker_id = "worker-A",
        std::string_view lease_until = "2099-01-01T00:00:00Z") {
    const PipelineRun queued = store.enqueue(make_spec());
    return store.claim(queued.id, worker_id, lease_until);
}

}  // namespace

// ── 12. confirm: RUNNING → Completed + watermark; no longer active ────────────

TEST(PipelineRunStore, ConfirmCompletedSetsStatusAndWatermark) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    const std::string wm = R"({"last_sqlite_id":42})";
    const PipelineRun done = store.confirm(running.id, wm, PipelineRunStatus::Completed);

    EXPECT_EQ(done.status,   PipelineRunStatus::Completed);
    EXPECT_EQ(done.watermark, wm);

    // Terminal run is no longer active.
    const auto found = store.find_active_run(
        PipelineKind::Replay, "tenant-1", "agg-abc", "hash-001");
    EXPECT_FALSE(found.has_value());
}

// ── 13. confirm: PartialSuccess and DegradedCompleted also succeed ────────────

TEST(PipelineRunStore, ConfirmPartialSuccessSucceeds) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    const PipelineRun done = store.confirm(running.id, "{}", PipelineRunStatus::PartialSuccess);
    EXPECT_EQ(done.status, PipelineRunStatus::PartialSuccess);
}

TEST(PipelineRunStore, ConfirmDegradedCompletedSucceeds) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    const PipelineRun done = store.confirm(running.id, "{}", PipelineRunStatus::DegradedCompleted);
    EXPECT_EQ(done.status, PipelineRunStatus::DegradedCompleted);
}

// ── 14. confirm: illegal terminal → throws (before DB) ───────────────────────

TEST(PipelineRunStore, ConfirmIllegalTerminalThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    EXPECT_THROW(
        store.confirm(running.id, "{}", PipelineRunStatus::Queued),
        std::invalid_argument);
}

// ── 15. confirm: non-RUNNING (QUEUED) run → throws ───────────────────────────

TEST(PipelineRunStore, ConfirmOnQueuedThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    EXPECT_THROW(
        store.confirm(queued.id, "{}", PipelineRunStatus::Completed),
        std::runtime_error);
}

// ── 16. reclaim: expired lease → reclaimed, retry_count == 1 ─────────────────

TEST(PipelineRunStore, ReclaimExpiredLeaseSucceeds) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    // claim with an already-expired lease (year 2000 is safely in the past).
    const PipelineRun queued = store.enqueue(make_spec());
    store.claim(queued.id, "worker-A", "2000-01-01T00:00:00Z");

    const PipelineRun reclaimed = store.reclaim(queued.id, "worker-B", "2030-01-01T00:00:00Z");

    EXPECT_EQ(reclaimed.status,      PipelineRunStatus::Running);
    ASSERT_TRUE(reclaimed.worker_id.has_value());
    EXPECT_EQ(*reclaimed.worker_id,  "worker-B");
    EXPECT_EQ(reclaimed.retry_count, 1LL);
}

// ── 17. reclaim: valid lease → throws ────────────────────────────────────────

TEST(PipelineRunStore, ReclaimValidLeaseThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    // claim with a lease far in the future (year 2099).
    const PipelineRun queued = store.enqueue(make_spec());
    store.claim(queued.id, "worker-A", "2099-01-01T00:00:00Z");

    EXPECT_THROW(
        store.reclaim(queued.id, "worker-B", "2099-06-01T00:00:00Z"),
        std::runtime_error);
}

// ── 18. reclaim: non-RUNNING (QUEUED) run → throws ───────────────────────────

TEST(PipelineRunStore, ReclaimOnQueuedThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    EXPECT_THROW(
        store.reclaim(queued.id, "worker-B", "2030-01-01T00:00:00Z"),
        std::runtime_error);
}

// ── 19. record_checkpoint: sets seq + watermark, status still Running ─────────

TEST(PipelineRunStore, RecordCheckpointSetsSeqAndWatermark) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    const std::string wm = R"({"last_sqlite_id":7})";
    const PipelineRun after = store.record_checkpoint(running.id, 7LL, wm);

    ASSERT_TRUE(after.checkpoint_sequence.has_value());
    EXPECT_EQ(*after.checkpoint_sequence, 7LL);
    EXPECT_EQ(after.watermark, wm);
    EXPECT_EQ(after.status,    PipelineRunStatus::Running);
}

// ── 20. record_checkpoint: non-RUNNING (QUEUED) run → throws ─────────────────

TEST(PipelineRunStore, RecordCheckpointOnQueuedThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    EXPECT_THROW(
        store.record_checkpoint(queued.id, 1LL, "{}"),
        std::runtime_error);
}

// ── Helper: run a scalar SQL expression over a text parameter, return int ─────

namespace {

// Evaluates a SQLite expression of the form "SELECT <expr>(?)" where the
// single bind parameter is the given text. Returns the integer result.
// Used to assert JSON structure without a JSON library in tests.
int eval_json_int(sqlite3* dbh, const char* expr, const std::string& json_text) {
    const std::string sql = std::string("SELECT ") + expr + "(?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error("eval_json_int: prepare failed");
    }
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    sqlite3_bind_text(raw, 1, json_text.c_str(), -1, SQLITE_TRANSIENT);
    const int rcode = sqlite3_step(raw);
    const int result = (rcode == SQLITE_ROW) ? sqlite3_column_int(raw, 0) : -1;
    sqlite3_finalize(raw);
    return result;
}

// Evaluates "SELECT json_extract(?, <path>)" and returns the text result.
std::string eval_json_extract_str(sqlite3* dbh,
                                   const std::string& json_text,
                                   const char* path) {
    const std::string sql = std::string("SELECT json_extract(?, ?)");
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error("eval_json_extract_str: prepare failed");
    }
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    sqlite3_bind_text(raw, 1, json_text.c_str(), -1, SQLITE_TRANSIENT);
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    sqlite3_bind_text(raw, 2, path, -1, SQLITE_STATIC);
    const int rcode = sqlite3_step(raw);
    std::string result;
    if (rcode == SQLITE_ROW && sqlite3_column_type(raw, 0) != SQLITE_NULL) {
        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        const auto* txt = reinterpret_cast<const char*>(sqlite3_column_text(raw, 0));
        if (txt != nullptr) {
            result = txt;
        }
    }
    sqlite3_finalize(raw);
    return result;
}

// Evaluates "SELECT json_extract(?, <path>)" and returns the int64 result.
long long eval_json_extract_int(sqlite3* dbh,
                                 const std::string& json_text,
                                 const char* path) {
    const std::string sql = std::string("SELECT json_extract(?, ?)");
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error("eval_json_extract_int: prepare failed");
    }
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    sqlite3_bind_text(raw, 1, json_text.c_str(), -1, SQLITE_TRANSIENT);
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    sqlite3_bind_text(raw, 2, path, -1, SQLITE_STATIC);
    const int rcode = sqlite3_step(raw);
    const long long result = (rcode == SQLITE_ROW) ? sqlite3_column_int64(raw, 0) : -1LL;
    sqlite3_finalize(raw);
    return result;
}

}  // namespace

// ── 21. dead_letter: RUNNING → DEAD_LETTERED; error_kind set; retry_count unchanged

TEST(PipelineRunStore, DeadLetterSetsStatusAndErrorKind) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    store.dead_letter(running.id, "max_retries_exceeded");

    const auto after = store.get(running.id);
    ASSERT_TRUE(after.has_value());
    EXPECT_EQ(after->status, PipelineRunStatus::DeadLettered);
    ASSERT_TRUE(after->error_kind.has_value());
    EXPECT_EQ(*after->error_kind, "max_retries_exceeded");
    // CX-9: retry_count must not be touched by dead_letter.
    EXPECT_EQ(after->retry_count, 0LL);

    // No longer active.
    const auto active = store.find_active_run(
        PipelineKind::Replay, "tenant-1", "agg-abc", "hash-001");
    EXPECT_FALSE(active.has_value());
}

// ── 22. dead_letter: QUEUED (not RUNNING) → throws ──────────────────────────

TEST(PipelineRunStore, DeadLetterOnQueuedThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    EXPECT_THROW(
        store.dead_letter(queued.id, "some_error"),
        std::runtime_error);
}

// ── 23. dead_letter: missing run_id → throws ─────────────────────────────────

TEST(PipelineRunStore, DeadLetterMissingRunThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    EXPECT_THROW(
        store.dead_letter("no-such-run-id", "some_error"),
        std::runtime_error);
}

// ── 24. cancel: QUEUED → CANCELLED; no longer active ────────────────────────

TEST(PipelineRunStore, CancelFromQueuedSucceeds) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun queued = store.enqueue(make_spec());
    const PipelineRun cancelled = store.cancel(queued.id);

    EXPECT_EQ(cancelled.status, PipelineRunStatus::Cancelled);

    const auto active = store.find_active_run(
        PipelineKind::Replay, "tenant-1", "agg-abc", "hash-001");
    EXPECT_FALSE(active.has_value());
}

// ── 25. cancel: RUNNING → CANCELLED ─────────────────────────────────────────

TEST(PipelineRunStore, CancelFromRunningSucceeds) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    const PipelineRun cancelled = store.cancel(running.id);

    EXPECT_EQ(cancelled.status, PipelineRunStatus::Cancelled);
}

// ── 26. cancel: already-terminal run → throws ───────────────────────────────

TEST(PipelineRunStore, CancelOnTerminalThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    store.confirm(running.id, "{}", PipelineRunStatus::Completed);

    EXPECT_THROW(store.cancel(running.id), std::runtime_error);
}

// ── 27. cancel: missing run_id → throws ─────────────────────────────────────

TEST(PipelineRunStore, CancelMissingRunThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    EXPECT_THROW(store.cancel("no-such-run-id"), std::runtime_error);
}

// ── 28. record_stage_timing: two entries; parsed array length + ordered values

TEST(PipelineRunStore, RecordStageTimingAppendsEntries) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    const PipelineRun running = enqueue_and_claim(store);
    store.record_stage_timing(running.id, "embed",  12LL);
    store.record_stage_timing(running.id, "replay", 30LL);

    const auto after = store.get(running.id);
    ASSERT_TRUE(after.has_value());
    const std::string& timings = after->stage_timings_ms;

    // Assert structure via SQLite JSON1 functions — not substring matching.
    EXPECT_EQ(eval_json_int(conn.raw(), "json_array_length", timings), 2);
    EXPECT_EQ(eval_json_extract_str(conn.raw(), timings, "$[0].stage"), "embed");
    EXPECT_EQ(eval_json_extract_int(conn.raw(), timings, "$[0].ms"),    12LL);
    EXPECT_EQ(eval_json_extract_str(conn.raw(), timings, "$[1].stage"), "replay");
    EXPECT_EQ(eval_json_extract_int(conn.raw(), timings, "$[1].ms"),    30LL);
}

// ── 29. record_stage_timing: missing run_id → throws ────────────────────────

TEST(PipelineRunStore, RecordStageTimingMissingRunThrows) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);

    EXPECT_THROW(
        store.record_stage_timing("no-such-run-id", "embed", 5LL),
        std::runtime_error);
}

// ── 30. partial_terminal_rollup: four cases ──────────────────────────────────

TEST(PipelineRunStore, PartialTerminalRollupMixed) {
    using starling::governance::PipelineRunStatus;
    const std::array<PipelineRunStatus, 2> items = {
        PipelineRunStatus::Completed, PipelineRunStatus::Failed
    };
    EXPECT_EQ(
        PipelineRunStore::partial_terminal_rollup(items),
        PipelineRunStatus::PartialSuccess);
}

TEST(PipelineRunStore, PartialTerminalRollupAllSuccess) {
    using starling::governance::PipelineRunStatus;
    const std::array<PipelineRunStatus, 2> items = {
        PipelineRunStatus::Completed, PipelineRunStatus::DegradedCompleted
    };
    EXPECT_EQ(
        PipelineRunStore::partial_terminal_rollup(items),
        PipelineRunStatus::Completed);
}

TEST(PipelineRunStore, PartialTerminalRollupAllFailure) {
    using starling::governance::PipelineRunStatus;
    const std::array<PipelineRunStatus, 2> items = {
        PipelineRunStatus::Failed, PipelineRunStatus::DeadLettered
    };
    EXPECT_EQ(
        PipelineRunStore::partial_terminal_rollup(items),
        PipelineRunStatus::Failed);
}

TEST(PipelineRunStore, PartialTerminalRollupEmptyIsCompleted) {
    using starling::governance::PipelineRunStatus;
    const std::span<const PipelineRunStatus> empty{};
    EXPECT_EQ(
        PipelineRunStore::partial_terminal_rollup(empty),
        PipelineRunStatus::Completed);
}

// ── 31. StageTimer sink wires to record_stage_timing — Phase-4 seam proof ────

TEST(PipelineRunStore, StageTimerSinkPersistsViaRecordStageTiming) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);
    const PipelineRun running = enqueue_and_claim(store);  // RUNNING run to attach to

    {
        // The SAME StageTimer as the tick path — here its sink writes to the store
        // instead of accumulating, proving the Phase-4 run-owner seam is wired.
        starling::governance::StageTimer timer(
            "embed", [&](std::string_view stage, long long ms) {
                store.record_stage_timing(running.id, stage, ms);
            });
    }  // scope exit -> record_stage_timing(running.id, "embed", <elapsed>)

    const auto after = store.get(running.id);
    ASSERT_TRUE(after.has_value());
    EXPECT_EQ(eval_json_int(conn.raw(), "json_array_length", after->stage_timings_ms), 1);
    EXPECT_EQ(eval_json_extract_str(conn.raw(), after->stage_timings_ms, "$[0].stage"), "embed");
    EXPECT_GE(eval_json_extract_int(conn.raw(), after->stage_timings_ms, "$[0].ms"), 0LL);
}
