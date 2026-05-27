-- P2.a 0009: ALTER statement_edges to add canonical_conflict_key column
-- + create partial UNIQUE index for conflicts_with edges only
-- + create singleton state table for backfill progress tracking.
-- Per spec §5.2.

ALTER TABLE statement_edges ADD COLUMN canonical_conflict_key TEXT;

-- partial UNIQUE: only conflicts_with edges with non-NULL key are constrained
-- (existing supersedes edges have NULL canonical_conflict_key permanently)
CREATE UNIQUE INDEX idx_conflict_edges_key_unique
    ON statement_edges(tenant_id, canonical_conflict_key)
    WHERE edge_kind = 'conflicts_with' AND canonical_conflict_key IS NOT NULL;

-- backfill progress (singleton; the row is seeded with started_at = epoch
-- so the application code can detect "never started" vs "in progress")
CREATE TABLE conflict_key_backfill_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_edge_id TEXT,
    rows_backfilled INTEGER NOT NULL DEFAULT 0,
    rows_deduped INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    last_updated_at TEXT NOT NULL
);
INSERT INTO conflict_key_backfill_state (id, started_at, last_updated_at)
    VALUES (1, '2026-05-26T00:00:00Z', '2026-05-26T00:00:00Z');
