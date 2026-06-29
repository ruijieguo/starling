#pragma once
#include "starling/governance/pipeline_run.hpp"
#include "starling/persistence/connection.hpp"

#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace starling::governance {

// Sole sanctioned write path into governance_pipeline_run. The active-run dedup
// (invariant 1) lives HERE (INSERT-then-detect), not in callers. No internal mutex;
// statement-only (the caller owns the transaction). Mirrors bus::PipelineLedger.
class PipelineRunStore {
public:
    explicit PipelineRunStore(persistence::Connection& conn) : conn_(conn) {}

    // Create a QUEUED run. If an ACTIVE run (QUEUED|RUNNING) already exists for
    // (kind, tenant_id, aggregate_id, input_hash), returns it WITHOUT inserting
    // (invariant 1). THROWS std::runtime_error on kind==ComplianceErase — c1 cannot
    // honor invariant 4 for compliance runs yet, so it refuses to create them
    // (fail-closed; re-enable when the invariant-4 health coupling lands).
    PipelineRun enqueue(const NewRun& spec);

    [[nodiscard]] std::optional<PipelineRun> find_active_run(
        PipelineKind kind, std::string_view tenant_id,
        std::string_view aggregate_id, std::string_view input_hash);
    [[nodiscard]] std::optional<PipelineRun> get(std::string_view run_id);

    // QUEUED -> RUNNING + worker_id + lease_until. Throws if the run is not QUEUED. (Task 3a.4)
    PipelineRun claim(std::string_view run_id, std::string_view worker_id,
                      std::string_view lease_until);
    // expired-lease RUNNING -> re-claim by a new worker, retry_count++. (Task 3a.5)
    PipelineRun reclaim(std::string_view run_id, std::string_view worker_id,
                        std::string_view lease_until);
    // RUNNING -> terminal (Completed|PartialSuccess|DegradedCompleted) + watermark. (Task 3a.5)
    PipelineRun confirm(std::string_view run_id, std::string_view checkpoint_json,
                        PipelineRunStatus terminal);
    // mid-run durable checkpoint (RUNNING only) — makes reclaim-resume real. (Task 3a.5)
    PipelineRun record_checkpoint(std::string_view run_id, long long checkpoint_sequence,
                                  std::string_view watermark_json);
    // QUEUED|RUNNING -> CANCELLED (cooperative cancel). (Task 3a.6)
    PipelineRun cancel(std::string_view run_id);
    // RUNNING -> DEAD_LETTERED + error_kind (does NOT touch retry_count). (Task 3a.6)
    void dead_letter(std::string_view run_id, std::string_view error_kind);
    // append {stage, ms} to stage_timings_ms (JSON1). (Task 3a.6)
    void record_stage_timing(std::string_view run_id, std::string_view stage, long long ms);

    // PARTIAL terminal rollup (NOT full invariant 7 — the 9-state enum has no NOOP,
    // so the all-NOOP rule is unrepresentable; deferred to c2). >=1 success & >=1 fail
    // -> PartialSuccess; all-success -> Completed; all-fail -> Failed. (Task 3a.6)
    [[nodiscard]] static PipelineRunStatus partial_terminal_rollup(
        std::span<const PipelineRunStatus> item_statuses);

private:
    [[nodiscard]] PipelineRun read_row_(std::string_view run_id);  // throws std::runtime_error if absent
    persistence::Connection& conn_;
};

}  // namespace starling::governance
