-- P2.c hardening: tenant-scope commitment tables (statements PK is (id,tenant_id)).
DROP TABLE IF EXISTS commitments;
CREATE TABLE commitments (
    tenant_id    TEXT NOT NULL,
    stmt_id      TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'ACTIVE'
                 CHECK (state IN ('created','ACTIVE','FULFILLED','BROKEN','RENEGOTIATED','WITHDRAWN')),
    broken_count INTEGER NOT NULL DEFAULT 0,
    deadline     TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
CREATE INDEX idx_commitments_state ON commitments(tenant_id, state);
CREATE INDEX idx_commitments_deadline ON commitments(state, deadline);

DROP TABLE IF EXISTS commitment_protection;
CREATE TABLE commitment_protection (
    tenant_id          TEXT NOT NULL,
    commitment_stmt_id TEXT NOT NULL,
    protected_stmt_id  TEXT NOT NULL,
    PRIMARY KEY (tenant_id, protected_stmt_id, commitment_stmt_id)
);
