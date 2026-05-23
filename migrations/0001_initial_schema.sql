-- Starling M0.2 initial schema. Targets SQLite 3.46+.

-- ── containers (persona / common_ground / knowledge_frontier; §3.4) ──
CREATE TABLE IF NOT EXISTS containers (
    id TEXT PRIMARY KEY,                    -- UUID
    tenant_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('persona','common_ground','knowledge_frontier')),
    holder_id TEXT NOT NULL,                -- CognizerRef
    scope_descriptor TEXT NOT NULL,         -- canonical JSON
    created_at TEXT NOT NULL,               -- ISO-8601 UTC
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_containers_tenant_holder
    ON containers(tenant_id, holder_id, kind);

-- ── statements (38-field core; §3.3) ──
CREATE TABLE IF NOT EXISTS statements (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    holder_id TEXT NOT NULL,
    holder_perspective TEXT NOT NULL,
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ('cognizer','entity')),
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_kind TEXT NOT NULL,              -- bool|int|float|str|datetime|cognizer|entity|statement
    object_value TEXT NOT NULL,             -- canonical string form (see canonicalize_object, M0.5)
    canonical_object_hash TEXT NOT NULL,
    canonical_object_hash_version TEXT NOT NULL DEFAULT 'v1',
    modality TEXT NOT NULL,
    polarity TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    observed_at TEXT NOT NULL,
    inferred_at TEXT,
    valid_from TEXT,
    valid_to TEXT,
    event_time_start TEXT,
    event_time_end TEXT,
    salience REAL NOT NULL CHECK (salience >= 0.0 AND salience <= 1.0),
    affect_json TEXT NOT NULL,              -- canonical JSON of AffectVector
    activation REAL NOT NULL,
    last_accessed TEXT NOT NULL,
    provenance TEXT NOT NULL,
    confidence_history_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    source_spans_json TEXT NOT NULL DEFAULT '[]',
    temporal_anchor_json TEXT,
    derived_from_json TEXT NOT NULL DEFAULT '[]',
    derived_depth INTEGER NOT NULL DEFAULT 0,
    perceived_by_json TEXT NOT NULL DEFAULT '[]',
    supersedes_id TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_replayed TEXT,
    replay_count INTEGER NOT NULL DEFAULT 0,
    consolidation_state TEXT NOT NULL DEFAULT 'volatile',
    review_status TEXT NOT NULL DEFAULT 'approved',
    nesting_depth INTEGER NOT NULL DEFAULT 0,
    visibility_json TEXT NOT NULL DEFAULT '[]',
    retention_policy TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (id, tenant_id)
);
-- P1-mandatory composite index (preflight checks for this exact name)
CREATE UNIQUE INDEX IF NOT EXISTS idx_statement_id_tenant
    ON statements(id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_statements_holder_predicate
    ON statements(tenant_id, holder_id, predicate);
CREATE INDEX IF NOT EXISTS idx_statements_subject
    ON statements(tenant_id, subject_kind, subject_id);

-- ── statement_edges (typed edges between statements; §3.4) ──
CREATE TABLE IF NOT EXISTS statement_edges (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    src_id TEXT NOT NULL,
    dst_id TEXT NOT NULL,
    edge_kind TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_edges_src
    ON statement_edges(tenant_id, src_id, edge_kind);
CREATE INDEX IF NOT EXISTS idx_edges_dst
    ON statement_edges(tenant_id, dst_id, edge_kind);

-- ── engrams (raw evidence anchors; §3.7) ──
CREATE TABLE IF NOT EXISTS engrams (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    ingest_policy TEXT NOT NULL,
    ingest_mode TEXT NOT NULL,
    privacy_class TEXT NOT NULL,
    retention_mode TEXT NOT NULL,
    refcount INTEGER NOT NULL DEFAULT 0,
    payload_uri TEXT,                       -- KMS-encrypted blob URI; M0.3 wires real adapter
    payload_inline BLOB,                    -- M0.2 inline only for tests
    created_at TEXT NOT NULL,
    erased_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_engrams_content_hash
    ON engrams(tenant_id, content_hash);

-- ── bus_events (transactional outbox; §3.10) ──
CREATE TABLE IF NOT EXISTS bus_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    primary_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    outbox_sequence INTEGER NOT NULL,       -- monotonic, claimed from outbox_sequence_counter
    causation_chain_json TEXT NOT NULL DEFAULT '[]',
    idempotency_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    dispatch_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (dispatch_status IN ('pending','in_flight','delivered','dead_letter')),
    dispatch_attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    last_error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_events_sequence
    ON bus_events(outbox_sequence);
CREATE INDEX IF NOT EXISTS idx_bus_events_dispatch
    ON bus_events(dispatch_status, outbox_sequence)
    WHERE dispatch_status IN ('pending','in_flight');
CREATE INDEX IF NOT EXISTS idx_bus_events_aggregate
    ON bus_events(aggregate_id, outbox_sequence);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_events_idempotency
    ON bus_events(idempotency_key);

-- ── outbox_sequence_counter (single-row monotonic claim) ──
CREATE TABLE IF NOT EXISTS outbox_sequence_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    next_value INTEGER NOT NULL
);
INSERT OR IGNORE INTO outbox_sequence_counter(id, next_value) VALUES (1, 1);

-- ── consumer_checkpoint (per-consumer last delivered sequence) ──
CREATE TABLE IF NOT EXISTS consumer_checkpoint (
    consumer_id TEXT PRIMARY KEY,
    last_delivered_sequence INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- ── idempotency_inbox (consumer-side dedup; 7-day expiry) ──
CREATE TABLE IF NOT EXISTS idempotency_inbox (
    consumer_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    received_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (consumer_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires
    ON idempotency_inbox(expires_at);

-- ── pipeline_run + extraction_attempt (M0.4 ledger; columns reserved here so M0.4 needs no migration) ──
CREATE TABLE IF NOT EXISTS pipeline_run (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    input_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS extraction_attempt (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_run(id),
    extraction_span_key TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL,                   -- success|partial_success|failed
    raw_output TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_extraction_attempt_span
    ON extraction_attempt(extraction_span_key, attempt_number);

-- ── schema_migrations (drift detection) ──
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    checksum TEXT NOT NULL                  -- sha256 hex of the migration file
);
