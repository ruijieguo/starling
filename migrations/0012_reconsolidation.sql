-- M0.8 Reconsolidation Engine 状态 (per spec §5.2).

CREATE TABLE reconsolidation_windows (
    stmt_id TEXT PRIMARY KEY,            -- 窗口锁: 一个 stmt 同时只一个活跃窗口
    tenant_id TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    close_deadline TEXT NOT NULL,        -- opened_at + adaptive_timeout
    trigger_event_ids_json TEXT NOT NULL DEFAULT '[]',
    force_close_trigger_count INTEGER NOT NULL DEFAULT 0,
    evicted_count INTEGER NOT NULL DEFAULT 0,
    evicted_summary_hashes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed'))
);
CREATE INDEX idx_recon_windows_deadline
    ON reconsolidation_windows(status, close_deadline);

CREATE TABLE reconsolidation_pending_evidence (
    id TEXT PRIMARY KEY,
    window_stmt_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_stmt_id TEXT,
    payload_hash TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    arrived_at TEXT NOT NULL
);
CREATE INDEX idx_recon_evidence_window
    ON reconsolidation_pending_evidence(window_stmt_id, arrived_at);

CREATE TABLE reconsolidation_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO reconsolidation_checkpoint (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');
