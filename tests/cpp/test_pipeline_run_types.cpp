#include <gtest/gtest.h>

#include "starling/governance/pipeline_run.hpp"

#include <stdexcept>
#include <string>

using starling::governance::PipelineKind;
using starling::governance::PipelineRun;
using starling::governance::PipelineRunStatus;
using starling::governance::NewRun;
using starling::governance::is_active;
using starling::governance::kind_to_string;
using starling::governance::kind_from_string;
using starling::governance::status_to_string;
using starling::governance::status_from_string;

// ── 1. Frozen string forms ─────────────────────────────────────────────────

TEST(PipelineRunTypes, StatusFrozenForms) {
    EXPECT_EQ(status_to_string(PipelineRunStatus::Queued),            "QUEUED");
    EXPECT_EQ(status_to_string(PipelineRunStatus::Running),           "RUNNING");
    EXPECT_EQ(status_to_string(PipelineRunStatus::Paused),            "PAUSED");
    EXPECT_EQ(status_to_string(PipelineRunStatus::Completed),         "COMPLETED");
    EXPECT_EQ(status_to_string(PipelineRunStatus::PartialSuccess),    "PARTIAL_SUCCESS");
    EXPECT_EQ(status_to_string(PipelineRunStatus::DegradedCompleted), "DEGRADED_COMPLETED");
    EXPECT_EQ(status_to_string(PipelineRunStatus::Failed),            "FAILED");
    EXPECT_EQ(status_to_string(PipelineRunStatus::Cancelled),         "CANCELLED");
    EXPECT_EQ(status_to_string(PipelineRunStatus::DeadLettered),      "DEAD_LETTERED");
}

TEST(PipelineRunTypes, KindFrozenForms) {
    EXPECT_EQ(kind_to_string(PipelineKind::Extraction),        "extraction");
    EXPECT_EQ(kind_to_string(PipelineKind::Replay),            "replay");
    EXPECT_EQ(kind_to_string(PipelineKind::ProjectionRebuild), "projection_rebuild");
    EXPECT_EQ(kind_to_string(PipelineKind::ContainerRebuild),  "container_rebuild");
    EXPECT_EQ(kind_to_string(PipelineKind::ComplianceErase),   "compliance_erase");
    EXPECT_EQ(kind_to_string(PipelineKind::RetrievalEval),     "retrieval_eval");
    EXPECT_EQ(kind_to_string(PipelineKind::Migration),         "migration");
}

// ── 2. Round-trip: every status and every kind ────────────────────────────

TEST(PipelineRunTypes, StatusRoundTrip) {
    const PipelineRunStatus all_statuses[] = {
        PipelineRunStatus::Queued,
        PipelineRunStatus::Running,
        PipelineRunStatus::Paused,
        PipelineRunStatus::Completed,
        PipelineRunStatus::PartialSuccess,
        PipelineRunStatus::DegradedCompleted,
        PipelineRunStatus::Failed,
        PipelineRunStatus::Cancelled,
        PipelineRunStatus::DeadLettered,
    };
    for (const auto s : all_statuses) {
        EXPECT_EQ(status_from_string(status_to_string(s)), s);
    }
}

TEST(PipelineRunTypes, KindRoundTrip) {
    const PipelineKind all_kinds[] = {
        PipelineKind::Extraction,
        PipelineKind::Replay,
        PipelineKind::ProjectionRebuild,
        PipelineKind::ContainerRebuild,
        PipelineKind::ComplianceErase,
        PipelineKind::RetrievalEval,
        PipelineKind::Migration,
    };
    for (const auto k : all_kinds) {
        EXPECT_EQ(kind_from_string(kind_to_string(k)), k);
    }
}

// ── 3. from_string throws on unknown ─────────────────────────────────────

TEST(PipelineRunTypes, StatusFromStringThrows) {
    EXPECT_THROW(status_from_string("queued"),    std::invalid_argument);  // lowercase
    EXPECT_THROW(status_from_string("UNKNOWN"),   std::invalid_argument);
    EXPECT_THROW(status_from_string(""),          std::invalid_argument);
}

TEST(PipelineRunTypes, KindFromStringThrows) {
    EXPECT_THROW(kind_from_string("Extraction"),  std::invalid_argument);  // capitalised
    EXPECT_THROW(kind_from_string("unknown"),     std::invalid_argument);
    EXPECT_THROW(kind_from_string(""),            std::invalid_argument);
}

// ── 4. is_active predicate ────────────────────────────────────────────────

TEST(PipelineRunTypes, IsActive) {
    EXPECT_TRUE(is_active(PipelineRunStatus::Queued));
    EXPECT_TRUE(is_active(PipelineRunStatus::Running));

    EXPECT_FALSE(is_active(PipelineRunStatus::Paused));
    EXPECT_FALSE(is_active(PipelineRunStatus::Completed));
    EXPECT_FALSE(is_active(PipelineRunStatus::PartialSuccess));
    EXPECT_FALSE(is_active(PipelineRunStatus::DegradedCompleted));
    EXPECT_FALSE(is_active(PipelineRunStatus::Failed));
    EXPECT_FALSE(is_active(PipelineRunStatus::Cancelled));
    EXPECT_FALSE(is_active(PipelineRunStatus::DeadLettered));
}

// ── 5. Struct fields exist (compile-level + readback guard for tenant_id) ─

TEST(PipelineRunTypes, PipelineRunTenantIdField) {
    PipelineRun run;
    run.tenant_id = "tenant-abc";
    EXPECT_EQ(run.tenant_id, "tenant-abc");
}

TEST(PipelineRunTypes, NewRunTenantIdField) {
    NewRun req;
    req.tenant_id = "tenant-xyz";
    EXPECT_EQ(req.tenant_id, "tenant-xyz");
}
