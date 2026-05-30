-- M0.9 Projection Index 第 7 类: idx_vector_payload (per spec §8)。
-- 已嵌入向量的 statement 元数据 scoping 索引,供 vector_recall 圈定可见集。
-- repair guard 复用 projection_rebuild_state (0015),无需新表。

CREATE TABLE proj_vector_payload (
    tenant_id           TEXT NOT NULL,
    holder_id           TEXT NOT NULL,
    consolidation_state TEXT NOT NULL,
    modality            TEXT,
    review_status       TEXT NOT NULL,
    stmt_id             TEXT NOT NULL,
    PRIMARY KEY (stmt_id)
);
CREATE INDEX idx_proj_vector_payload_scope
    ON proj_vector_payload(tenant_id, holder_id, consolidation_state);
