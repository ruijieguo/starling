-- 0038_memory_events.sql:按调用方给的稳定 key 记一次写入的收据(rise 设计二 §8)。
CREATE TABLE IF NOT EXISTS events (
    tenant_id          TEXT NOT NULL,
    key                TEXT NOT NULL,
    text               TEXT NOT NULL,
    interlocutor       TEXT NOT NULL,
    text_sha256        TEXT NOT NULL,
    engram_ref         TEXT,
    statement_ids_json TEXT NOT NULL DEFAULT '[]',
    seq                INTEGER NOT NULL,
    state              TEXT NOT NULL CHECK (state IN ('pending','committed','abandoned')),
    failure_category   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, key),
    UNIQUE (tenant_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_events_state ON events(tenant_id, state);
