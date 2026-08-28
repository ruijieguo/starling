-- Move extraction lifecycle ownership to governance_pipeline_run. The legacy
-- name remains a compatibility view, not a second mutable status table.
ALTER TABLE governance_pipeline_run
    ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'
    CHECK(json_valid(metadata_json));

INSERT OR IGNORE INTO governance_pipeline_run(
    id, kind, aggregate_id, tenant_id, profile_name, input_hash,
    idempotency_key, pipeline_name, pipeline_version, metadata_json, status,
    started_at, updated_at
)
SELECT id, 'extraction', COALESCE(input_ref, id), tenant_id, 'default', id,
       'legacy:' || id, 'extractor', 'legacy',
       CASE WHEN json_valid(metadata_json) THEN metadata_json ELSE '{}' END,
       CASE status
           WHEN 'started' THEN 'RUNNING'
           WHEN 'failed' THEN 'DEAD_LETTERED'
           ELSE 'COMPLETED'
       END,
       started_at, COALESCE(finished_at, started_at)
FROM pipeline_run;

CREATE TABLE extraction_attempt_new (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES governance_pipeline_run(id),
    extraction_span_key TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    raw_output TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0
);
INSERT INTO extraction_attempt_new
SELECT id, pipeline_run_id, extraction_span_key, attempt_number, status,
       raw_output, error, created_at, prompt_tokens, completion_tokens,
       total_tokens, latency_ms
FROM extraction_attempt;
DROP TABLE extraction_attempt;
ALTER TABLE extraction_attempt_new RENAME TO extraction_attempt;
CREATE INDEX idx_extraction_attempt_span
    ON extraction_attempt(extraction_span_key, attempt_number);
CREATE UNIQUE INDEX idx_extraction_attempt_unique
    ON extraction_attempt(pipeline_run_id, extraction_span_key, attempt_number);

DROP TABLE pipeline_run;
CREATE VIEW pipeline_run AS
SELECT id, tenant_id, started_at,
       CASE WHEN status IN ('QUEUED','RUNNING','PAUSED') THEN NULL ELSE updated_at END AS finished_at,
       CASE
           WHEN status IN ('QUEUED','RUNNING','PAUSED') THEN 'started'
           WHEN status IN ('DEAD_LETTERED','FAILED','CANCELLED') THEN 'failed'
           ELSE 'finished'
       END AS status,
       aggregate_id AS input_ref,
       metadata_json
FROM governance_pipeline_run
WHERE kind='extraction';

-- Compatibility for tests and older local tooling that seed the former table.
-- The trigger writes directly into the sole authoritative governance ledger.
CREATE TRIGGER pipeline_run_compat_insert
INSTEAD OF INSERT ON pipeline_run
BEGIN
    INSERT INTO governance_pipeline_run(
        id, kind, aggregate_id, tenant_id, profile_name, input_hash,
        idempotency_key, pipeline_name, pipeline_version, metadata_json, status,
        started_at, updated_at
    ) VALUES(
        NEW.id, 'extraction', COALESCE(NEW.input_ref, NEW.id), NEW.tenant_id,
        'compat', NEW.id, 'compat:' || NEW.id, 'extractor', 'compat',
        COALESCE(NEW.metadata_json, '{}'),
        CASE lower(NEW.status)
            WHEN 'started' THEN 'RUNNING'
            WHEN 'failed' THEN 'DEAD_LETTERED'
            ELSE 'COMPLETED'
        END,
        NEW.started_at, COALESCE(NEW.finished_at, NEW.started_at)
    );
END;
