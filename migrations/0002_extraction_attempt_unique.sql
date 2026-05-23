-- M0.2 Task 8: enforce per-run uniqueness of (extraction_span_key, attempt_number).
-- The non-unique idx_extraction_attempt_span from 0001 supports lookup by span;
-- this index gives M0.4's LLM extractor a hard guarantee that the same
-- (run, span, attempt_number) cannot be inserted twice.
CREATE UNIQUE INDEX IF NOT EXISTS idx_extraction_attempt_unique
    ON extraction_attempt(pipeline_run_id, extraction_span_key, attempt_number);
