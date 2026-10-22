-- 形态 S（左脑原文召回 lane）：权威元数据、派生向量索引、带历史的组成员关系。
--
-- 设计：docs/superpowers/specs/2026-10-19-form-s-source-lane-design.md（v4.3）
--   §5.3  source_unit_meta（权威）/ source_unit_vectors（派生，可整表重建）
--   §3.2b cognizer_group_membership（带 joined_at/left_at 的历史）
--
-- 为什么权威元数据单独成表：audience/session_id/observed_at/provenance 是重建与审计
-- 依赖的事实，不能只存在于可重建的向量表里（三轮 Codex #9、五轮 #5/#6）。

-- 外键目标 engrams(id, tenant_id) 的唯一索引由 0035 建立（idx_engrams_id_tenant），此处复用。

-- ── 权威元数据：写入即固定，只追加 ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS source_unit_meta (
    tenant_id     TEXT NOT NULL,
    engram_ref    TEXT NOT NULL,
    clause_id     TEXT NOT NULL,      -- unit 在 payload 内的稳定编号（c0, c1, ...）
    speaker       TEXT NOT NULL,      -- 渲染归属用的说话人
    session_id    TEXT NOT NULL,      -- 场景（对话 session 在多智能体下的推广）
    audience_json TEXT NOT NULL,      -- 写入时展开后的听众数组（组已展开）
    turn_index    INTEGER,            -- 场景内句序；旧数据可为 NULL
    observed_at   TEXT,               -- NULL = 无可信时间，不参与召回
    provenance    TEXT NOT NULL DEFAULT 'source_time'
                  CHECK (provenance IN ('source_time','ingest_clock')),
    PRIMARY KEY (tenant_id, engram_ref, clause_id),
    FOREIGN KEY (engram_ref, tenant_id) REFERENCES engrams(id, tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_sum_session ON source_unit_meta(tenant_id, session_id);
CREATE INDEX IF NOT EXISTS idx_sum_engram  ON source_unit_meta(tenant_id, engram_ref);

-- ── 派生向量索引：可整表重建，删了不丢信息 ─────────────────────────────────
CREATE TABLE IF NOT EXISTS source_unit_vectors (
    tenant_id       TEXT NOT NULL,
    engram_ref      TEXT NOT NULL,
    clause_id       TEXT NOT NULL,
    dim             INTEGER CHECK (dim > 0),      -- pending 时未知，嵌入后必填
    model           TEXT,                         -- pending 时未知，嵌入后必填
    index_vector    BLOB,
    raw_embedding   BLOB,
    status          TEXT NOT NULL CHECK (status IN ('pending','embedded','failed')),
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    embedded_at     TEXT,
    PRIMARY KEY (tenant_id, engram_ref, clause_id),
    -- 嵌入完成后必须有维度与模型；pending 阶段允许为空。
    CHECK (status = 'pending' OR (dim IS NOT NULL AND model IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_suv_scan ON source_unit_vectors(tenant_id, status);

-- ── 组成员关系（带历史）────────────────────────────────────────────────────
-- 主键含 joined_at：同一 (组, 成员) 在不同生效时刻可并存，历史不被覆盖；
-- 同一 (组, 成员, 生效时刻) 重复写入由 INSERT OR IGNORE 吸收（幂等）。
CREATE TABLE IF NOT EXISTS cognizer_group_membership (
    tenant_id   TEXT NOT NULL,
    group_id    TEXT NOT NULL,
    cognizer_id TEXT NOT NULL,
    joined_at   TEXT NOT NULL,        -- 生效时刻（世界时刻/事件时间），不是写入时刻
    left_at     TEXT,                 -- NULL = 仍在组内
    recorded_at TEXT NOT NULL,        -- 写入时刻，供审计
    PRIMARY KEY (tenant_id, group_id, cognizer_id, joined_at)
);
CREATE INDEX IF NOT EXISTS idx_cgm_asof
    ON cognizer_group_membership(tenant_id, group_id, joined_at);
