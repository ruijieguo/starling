#pragma once
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::governance {

// 7 kinds. String forms are the spec literals (stored in the `kind` column).
// : std::uint8_t for performance-enum-size (clang-tidy).
enum class PipelineKind : std::uint8_t {
    Extraction, Replay, ProjectionRebuild, ContainerRebuild,
    ComplianceErase, RetrievalEval, Migration
};

// 9-state lifecycle. String forms are the spec UPPERCASE names — FROZEN CONTRACT
// (a later migration's partial active index + CHECK reference 'QUEUED'/'RUNNING'/...).
// NOTE (P3.c1 scope): FAILED and PAUSED are enum-only in c1 — no mutator produces
// them yet (FAILED = a future transient retry-state; PAUSED = future DRAINING
// coordination). The c1 store reaches QUEUED/RUNNING/COMPLETED/PARTIAL_SUCCESS/
// DEGRADED_COMPLETED/CANCELLED/DEAD_LETTERED.
enum class PipelineRunStatus : std::uint8_t {
    Queued, Running, Paused, Completed, PartialSuccess,
    DegradedCompleted, Failed, Cancelled, DeadLettered
};

[[nodiscard]] inline std::string_view kind_to_string(PipelineKind kind) {
    switch (kind) {
        case PipelineKind::Extraction:        return "extraction";
        case PipelineKind::Replay:            return "replay";
        case PipelineKind::ProjectionRebuild: return "projection_rebuild";
        case PipelineKind::ContainerRebuild:  return "container_rebuild";
        case PipelineKind::ComplianceErase:   return "compliance_erase";
        case PipelineKind::RetrievalEval:     return "retrieval_eval";
        case PipelineKind::Migration:         return "migration";
    }
    throw std::invalid_argument("kind_to_string: unknown PipelineKind");
}

[[nodiscard]] inline PipelineKind kind_from_string(std::string_view str) {
    if (str == "extraction")         { return PipelineKind::Extraction; }
    if (str == "replay")             { return PipelineKind::Replay; }
    if (str == "projection_rebuild") { return PipelineKind::ProjectionRebuild; }
    if (str == "container_rebuild")  { return PipelineKind::ContainerRebuild; }
    if (str == "compliance_erase")   { return PipelineKind::ComplianceErase; }
    if (str == "retrieval_eval")     { return PipelineKind::RetrievalEval; }
    if (str == "migration")          { return PipelineKind::Migration; }
    throw std::invalid_argument("kind_from_string: unknown kind '" + std::string(str) + "'");
}

[[nodiscard]] inline std::string_view status_to_string(PipelineRunStatus status) {
    switch (status) {
        case PipelineRunStatus::Queued:            return "QUEUED";
        case PipelineRunStatus::Running:           return "RUNNING";
        case PipelineRunStatus::Paused:            return "PAUSED";
        case PipelineRunStatus::Completed:         return "COMPLETED";
        case PipelineRunStatus::PartialSuccess:    return "PARTIAL_SUCCESS";
        case PipelineRunStatus::DegradedCompleted: return "DEGRADED_COMPLETED";
        case PipelineRunStatus::Failed:            return "FAILED";
        case PipelineRunStatus::Cancelled:         return "CANCELLED";
        case PipelineRunStatus::DeadLettered:      return "DEAD_LETTERED";
    }
    throw std::invalid_argument("status_to_string: unknown PipelineRunStatus");
}

[[nodiscard]] inline PipelineRunStatus status_from_string(std::string_view str) {
    if (str == "QUEUED")             { return PipelineRunStatus::Queued; }
    if (str == "RUNNING")            { return PipelineRunStatus::Running; }
    if (str == "PAUSED")             { return PipelineRunStatus::Paused; }
    if (str == "COMPLETED")          { return PipelineRunStatus::Completed; }
    if (str == "PARTIAL_SUCCESS")    { return PipelineRunStatus::PartialSuccess; }
    if (str == "DEGRADED_COMPLETED") { return PipelineRunStatus::DegradedCompleted; }
    if (str == "FAILED")             { return PipelineRunStatus::Failed; }
    if (str == "CANCELLED")          { return PipelineRunStatus::Cancelled; }
    if (str == "DEAD_LETTERED")      { return PipelineRunStatus::DeadLettered; }
    throw std::invalid_argument("status_from_string: unknown status '" + std::string(str) + "'");
}

// Invariant-1 "active" predicate: a run blocks a duplicate iff QUEUED or RUNNING
// (PAUSED does NOT block). Matches the migration's partial-index WHERE clause.
[[nodiscard]] constexpr bool is_active(PipelineRunStatus status) {
    return status == PipelineRunStatus::Queued || status == PipelineRunStatus::Running;
}

// Read-back row. Scalars typed; structured sub-fields are opaque JSON text.
struct PipelineRun {
    std::string id;
    PipelineKind kind{};
    std::string aggregate_id;
    std::string tenant_id;                       // REQUIRED — part of the active-dedup key
    std::optional<std::string> business_task_id;
    std::optional<std::string> parent_run_id;
    std::string profile_name;
    std::string input_hash;
    std::string idempotency_key;
    std::string pipeline_name;
    std::string pipeline_version;
    PipelineRunStatus status{};
    std::optional<long long> checkpoint_sequence;
    std::optional<std::string> error_kind;
    long long retry_count = 0;
    std::optional<std::string> worker_id;
    std::optional<std::string> lease_until;      // canonical ISO-8601 UTC (YYYY-MM-DDTHH:MM:SSZ)
    std::string item_run_ids    = "[]";          // JSON
    std::string step_contracts  = "[]";          // JSON (opaque in c1)
    std::string watermark       = "{}";          // JSON
    std::string progress        = "{}";          // JSON
    std::string counters        = "{}";          // JSON
    std::string warnings        = "[]";          // JSON
    std::string stage_timings_ms = "[]";         // JSON array of {stage, ms}
    std::string started_at;                       // ISO-8601 UTC
    std::string updated_at;                       // ISO-8601 UTC
};

// enqueue() input — the caller-supplied identity of a new run.
struct NewRun {
    PipelineKind kind{};
    std::string aggregate_id;
    std::string tenant_id;                       // REQUIRED — part of the active-dedup key
    std::string profile_name;
    std::string input_hash;
    std::string idempotency_key;
    std::string pipeline_name;
    std::string pipeline_version;
    std::optional<std::string> business_task_id;
    std::optional<std::string> parent_run_id;
    std::string step_contracts = "[]";           // opaque JSON
};

}  // namespace starling::governance
