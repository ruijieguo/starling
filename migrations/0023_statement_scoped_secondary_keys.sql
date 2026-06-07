-- Statement-scoped secondary tables must key by (tenant_id, stmt_id).
-- The authoritative statements primary key is (id, tenant_id); keeping these
-- tables keyed only by stmt_id leaks state across tenants when IDs collide.

-- ── statement_vectors: stmt_id PK -> (tenant_id, stmt_id) PK ──
CREATE TABLE statement_vectors_new (
    stmt_id         TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    index_vector    BLOB,
    raw_embedding   BLOB,
    dim             INTEGER NOT NULL,
    model           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'embedded'
                    CHECK (status IN ('embedded','failed')),
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    embedded_at     TEXT,
    PRIMARY KEY (tenant_id, stmt_id)
);
INSERT OR IGNORE INTO statement_vectors_new (
    stmt_id, tenant_id, index_vector, raw_embedding, dim, model, status,
    retry_count, last_attempt_at, embedded_at
)
SELECT stmt_id, tenant_id, index_vector, raw_embedding, dim, model, status,
       retry_count, last_attempt_at, embedded_at
FROM statement_vectors;
DROP TABLE statement_vectors;
ALTER TABLE statement_vectors_new RENAME TO statement_vectors;
CREATE INDEX idx_statement_vectors_scope ON statement_vectors(tenant_id, status);

-- ── proj_vector_payload: stmt_id PK -> (tenant_id, stmt_id) PK ──
CREATE TABLE proj_vector_payload_new (
    tenant_id           TEXT NOT NULL,
    holder_id           TEXT NOT NULL,
    consolidation_state TEXT NOT NULL,
    modality            TEXT,
    review_status       TEXT NOT NULL,
    stmt_id             TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
INSERT OR IGNORE INTO proj_vector_payload_new (
    tenant_id, holder_id, consolidation_state, modality, review_status, stmt_id
)
SELECT tenant_id, holder_id, consolidation_state, modality, review_status, stmt_id
FROM proj_vector_payload;
DROP TABLE proj_vector_payload;
ALTER TABLE proj_vector_payload_new RENAME TO proj_vector_payload;
CREATE INDEX idx_proj_vector_payload_scope
    ON proj_vector_payload(tenant_id, holder_id, consolidation_state);

-- ── reconsolidation_windows: stmt_id PK -> (tenant_id, stmt_id) PK ──
CREATE TABLE reconsolidation_windows_new (
    stmt_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    close_deadline TEXT NOT NULL,
    trigger_event_ids_json TEXT NOT NULL DEFAULT '[]',
    force_close_trigger_count INTEGER NOT NULL DEFAULT 0,
    evicted_count INTEGER NOT NULL DEFAULT 0,
    evicted_summary_hashes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    PRIMARY KEY (tenant_id, stmt_id)
);
INSERT OR IGNORE INTO reconsolidation_windows_new (
    stmt_id, tenant_id, opened_at, close_deadline, trigger_event_ids_json,
    force_close_trigger_count, evicted_count, evicted_summary_hashes_json, status
)
SELECT stmt_id, tenant_id, opened_at, close_deadline, trigger_event_ids_json,
       force_close_trigger_count, evicted_count, evicted_summary_hashes_json, status
FROM reconsolidation_windows;
DROP TABLE reconsolidation_windows;
ALTER TABLE reconsolidation_windows_new RENAME TO reconsolidation_windows;
CREATE INDEX idx_recon_windows_deadline
    ON reconsolidation_windows(status, close_deadline);

-- ── reconsolidation_pending_evidence: carry window_tenant_id ──
CREATE TABLE reconsolidation_pending_evidence_new (
    id TEXT PRIMARY KEY,
    window_stmt_id TEXT NOT NULL,
    window_tenant_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_stmt_id TEXT,
    payload_hash TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    arrived_at TEXT NOT NULL
);
INSERT OR IGNORE INTO reconsolidation_pending_evidence_new (
    id, window_stmt_id, window_tenant_id, event_id, event_type, source_stmt_id,
    payload_hash, weight, arrived_at
)
SELECT e.id, e.window_stmt_id, COALESCE(w.tenant_id, 'default'),
       e.event_id, e.event_type, e.source_stmt_id, e.payload_hash, e.weight,
       e.arrived_at
FROM reconsolidation_pending_evidence e
LEFT JOIN reconsolidation_windows w ON w.stmt_id = e.window_stmt_id;
DROP TABLE reconsolidation_pending_evidence;
ALTER TABLE reconsolidation_pending_evidence_new RENAME TO reconsolidation_pending_evidence;
CREATE INDEX idx_recon_evidence_window
    ON reconsolidation_pending_evidence(window_tenant_id, window_stmt_id, arrived_at);
