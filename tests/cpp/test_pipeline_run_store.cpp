// Task 3a.3: PipelineRunStore — enqueue / find_active_run / get tests.
// Tests the first three implemented methods: enqueue, find_active_run, get.
// The remaining methods (claim/reclaim/confirm/etc.) are declared but unimplemented;
// they are NOT called here.
#include <gtest/gtest.h>

#include "starling/governance/pipeline_run_store.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

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
