-- M0.8 Replay Scheduler 状态 (per spec §5.1).

CREATE TABLE replay_scheduler_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    online_trigger_counter INTEGER NOT NULL DEFAULT 0,
    last_online_run_at TEXT,
    last_idle_run_at TEXT,
    last_sleep_run_at TEXT,
    last_updated_at TEXT NOT NULL
);
INSERT INTO replay_scheduler_state (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');

CREATE TABLE replay_ledger (
    replay_batch_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('online','idle','sleep')),
    sampled_count INTEGER NOT NULL DEFAULT 0,
    ops_applied_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    finished_at TEXT
);

ALTER TABLE statements ADD COLUMN last_replay_batch_id TEXT;
