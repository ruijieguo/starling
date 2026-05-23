-- M0.3 EngramStore column extensions and source-identity uniqueness.
-- The MigrationRunner records each migration's checksum and skips already-applied
-- versions on re-run, so the raw ALTER TABLE statements below are safe — they
-- only execute the first time this version is seen.

ALTER TABLE engrams ADD COLUMN adapter_name TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN adapter_version TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN source_item_id TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN source_version TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN chunk_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE engrams ADD COLUMN declared_transformations_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE engrams ADD COLUMN byte_preserving INTEGER NOT NULL DEFAULT 0;
ALTER TABLE engrams ADD COLUMN redacted_content TEXT;
ALTER TABLE engrams ADD COLUMN key_ref TEXT;
ALTER TABLE engrams ADD COLUMN audit_trail_json TEXT NOT NULL DEFAULT '[]';

-- Source idempotency: a producer that re-ingests the same
-- (adapter, item, version, chunk) tuple gets the existing EngramRef back from
-- EvidenceValidator. The UNIQUE index is the storage-layer guarantee even if
-- two concurrent producers race past the validator's pre-INSERT SELECT.
CREATE UNIQUE INDEX IF NOT EXISTS idx_engrams_source_identity
    ON engrams(tenant_id, adapter_name, source_item_id, source_version, chunk_index);
