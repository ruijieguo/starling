-- P3.c1 Phase 3a: governance PipelineRun ledger — the long-task lifecycle account
-- (enqueue/claim/confirm/reclaim/find_active_run/dead_letter + per-stage timing),
-- DISTINCT from the M0.4 extraction-cost ledger (pipeline_run + extraction_attempt).
-- Sole writer: src/governance/pipeline_run_store.cpp (lands in Task 3a.3). Scalars are
-- first-class columns; structured sub-fields are JSON text (SQLite JSON1). See
-- docs/design/subsystems_design/05_governance.md §数据模型.
CREATE TABLE governance_pipeline_run (
    id                  TEXT PRIMARY KEY,
    kind                TEXT NOT NULL CHECK(kind IN ('extraction','replay','projection_rebuild','container_rebuild','compliance_erase','retrieval_eval','migration')),
    aggregate_id        TEXT NOT NULL,
    tenant_id           TEXT NOT NULL,
    business_task_id    TEXT,
    parent_run_id       TEXT,
    profile_name        TEXT NOT NULL,
    input_hash          TEXT NOT NULL,
    idempotency_key     TEXT NOT NULL,
    pipeline_name       TEXT NOT NULL,
    pipeline_version    TEXT NOT NULL,
    status              TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','PAUSED','COMPLETED','PARTIAL_SUCCESS','DEGRADED_COMPLETED','FAILED','CANCELLED','DEAD_LETTERED')),
    checkpoint_sequence INTEGER,
    error_kind          TEXT,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    worker_id           TEXT,
    lease_until         TEXT,
    item_run_ids        TEXT NOT NULL DEFAULT '[]',
    step_contracts      TEXT NOT NULL DEFAULT '[]',
    watermark           TEXT NOT NULL DEFAULT '{}',
    progress            TEXT NOT NULL DEFAULT '{}',
    counters            TEXT NOT NULL DEFAULT '{}',
    warnings            TEXT NOT NULL DEFAULT '[]',
    stage_timings_ms    TEXT NOT NULL DEFAULT '[]',
    started_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Invariant 1 (05_governance.md:185): at most one ACTIVE run (QUEUED|RUNNING) per
-- (kind, tenant_id, aggregate_id, input_hash). tenant_id is in the key to prevent
-- cross-tenant run suppression (aggregate_id is NOT tenant-qualified in this repo).
-- The partial UNIQUE index lets the writer INSERT-then-detect (CX-3) instead of a
-- caller-side set. The status literals here MUST match status_to_string's output.
CREATE UNIQUE INDEX idx_governance_pipeline_run_active
    ON governance_pipeline_run(kind, tenant_id, aggregate_id, input_hash)
    WHERE status IN ('QUEUED', 'RUNNING');

-- Lease-sweep + status scans (reclaim of expired leases; find_active_run).
CREATE INDEX idx_governance_pipeline_run_lease
    ON governance_pipeline_run(status, lease_until);
