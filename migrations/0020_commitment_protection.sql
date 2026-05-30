-- P2.c active_holding 反向保护映射 (per spec §7)。decay EXISTS-join commitments.state='ACTIVE'。
CREATE TABLE commitment_protection (
    commitment_stmt_id TEXT NOT NULL,
    protected_stmt_id  TEXT NOT NULL,
    PRIMARY KEY (protected_stmt_id, commitment_stmt_id)
);
