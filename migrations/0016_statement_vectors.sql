-- M0.9 向量存储 (per spec §4)。独立表,保持 statements 精简,向量可选/异步。
-- "缺 statement_vectors 行" = 待嵌入队列;status='failed' 行带 retry_count 退避重试。

CREATE TABLE statement_vectors (
    stmt_id         TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    index_vector    BLOB,                 -- 模式分离后的索引向量 (float32 紧凑 little-endian)
    raw_embedding   BLOB,                 -- 原始 embedding (留待将来重分离)
    dim             INTEGER NOT NULL,
    model           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'embedded'
                    CHECK (status IN ('embedded','failed')),
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    embedded_at     TEXT
);
CREATE INDEX idx_statement_vectors_scope ON statement_vectors(tenant_id, status);
