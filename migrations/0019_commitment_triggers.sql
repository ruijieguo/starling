-- P2.c PolicyEngine Trigger 注册 (per spec §6)。
CREATE TABLE commitment_triggers (
    id                 TEXT PRIMARY KEY,
    commitment_stmt_id TEXT NOT NULL,
    tenant_id          TEXT NOT NULL,
    kind               TEXT NOT NULL CHECK (kind IN ('time','event','state','compound')),
    spec_json          TEXT NOT NULL DEFAULT '{}',
    status             TEXT NOT NULL DEFAULT 'armed' CHECK (status IN ('armed','fired','cleared')),
    created_at         TEXT NOT NULL
);
CREATE INDEX idx_commitment_triggers_kind ON commitment_triggers(tenant_id, kind, status);

-- PolicyEngine.run_post_write 的 outbox 消费游标 (Task 8 依赖)。
CREATE TABLE policy_engine_checkpoint (
    id  INTEGER PRIMARY KEY CHECK (id = 1),
    seq INTEGER NOT NULL DEFAULT 0
);
INSERT INTO policy_engine_checkpoint(id, seq) VALUES (1, 0);
