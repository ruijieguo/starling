-- Starling P2.a 09_tom schema (per spec §5.3).
-- 3 tables: BeliefTracker checkpoint, depth estimator cache, common_ground (P2.b writer).

-- BeliefTracker outbox checkpoint (singleton)
CREATE TABLE tom_belief_tracker_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO tom_belief_tracker_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-05-26T00:00:00Z');

-- ToMDepthEstimator 7d nesting_depth=1 count cache, TTL 1h
CREATE TABLE tom_depth_estimator_cache (
    tenant_id TEXT NOT NULL,
    partner_id TEXT NOT NULL,
    nesting_depth_1_count_7d INTEGER NOT NULL DEFAULT 0,
    last_recomputed_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, partner_id)
);

-- CommonGround pool: P2.a 加表，writer 留 P2.b (spec §7.2 + §13.2)
CREATE TABLE common_ground (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    statement_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN
        ('asserted_unack','grounded','suspected_diverge','expired','recanted')),
    parties_json TEXT NOT NULL DEFAULT '[]',
    grounded_at TEXT,
    last_confirmed_at TEXT,
    superseded_by TEXT,
    expired_at TEXT,
    audit_actor TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_common_ground_status
    ON common_ground(tenant_id, status);
CREATE INDEX idx_common_ground_statement
    ON common_ground(tenant_id, statement_id);
