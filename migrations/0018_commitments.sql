-- P2.c Commitment 五态机 (per spec §5)。绑定 modality=COMMITS statement。
CREATE TABLE commitments (
    stmt_id      TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'ACTIVE'
                 CHECK (state IN ('created','ACTIVE','FULFILLED','BROKEN','RENEGOTIATED','WITHDRAWN')),
    broken_count INTEGER NOT NULL DEFAULT 0,
    deadline     TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX idx_commitments_state ON commitments(tenant_id, state);
CREATE INDEX idx_commitments_deadline ON commitments(state, deadline);
