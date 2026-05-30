-- M0.8 CommonGround Grounding Acts 审计 (per spec §5.4).

CREATE TABLE grounding_acts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    common_ground_id TEXT NOT NULL,
    act TEXT NOT NULL CHECK (act IN
        ('assert','acknowledge','repair','withdraw','supersede')),
    actor_cognizer_id TEXT,
    statement_id TEXT,
    occurred_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_grounding_acts_cg
    ON grounding_acts(tenant_id, common_ground_id, occurred_at);

ALTER TABLE common_ground ADD COLUMN establishment_evidence_json TEXT NOT NULL DEFAULT '[]';
