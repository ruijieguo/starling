-- M0.8 Projection Index 6 SQL 物化投影 + repair guard (per spec §5.5).
-- idx_vector_payload (第7个) 推迟 M0.9。

CREATE TABLE proj_holder_state_time (
    tenant_id TEXT NOT NULL, holder_id TEXT NOT NULL,
    consolidation_state TEXT NOT NULL, observed_at TEXT NOT NULL,
    stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, holder_id, stmt_id)
);
CREATE TABLE proj_holder_subgraph (
    tenant_id TEXT NOT NULL, holder_id TEXT NOT NULL,
    subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, holder_id, stmt_id)
);
CREATE TABLE proj_entity_statement (
    tenant_id TEXT NOT NULL, subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, subject_kind, subject_id, stmt_id)
);
CREATE TABLE proj_salience_hot (
    tenant_id TEXT NOT NULL, salience REAL NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
CREATE INDEX idx_proj_salience ON proj_salience_hot(tenant_id, salience DESC);
CREATE TABLE proj_commitment_due (
    tenant_id TEXT NOT NULL, due_at TEXT, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
CREATE INDEX idx_proj_commitment ON proj_commitment_due(tenant_id, due_at);
CREATE TABLE proj_common_ground (
    tenant_id TEXT NOT NULL, common_ground_id TEXT NOT NULL,
    status TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, common_ground_id, stmt_id)
);

CREATE TABLE projection_rebuild_state (
    projection_name TEXT PRIMARY KEY,
    ground_truth_count INTEGER NOT NULL DEFAULT 0,
    index_count INTEGER NOT NULL DEFAULT 0,
    last_rebuilt_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','truncation_suspected'))
);

CREATE TABLE projection_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO projection_subscriber_checkpoint (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');
