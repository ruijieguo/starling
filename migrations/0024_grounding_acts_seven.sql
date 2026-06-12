-- 0024: grounding_acts 七幕(P3.a2)。
-- spec 09_tom §Grounding Acts:Assert/Acknowledge/Repair/Withdraw/
-- SupersedeGround/ExpireGround/Unground——0014 的 CHECK 只放行前五幕,
-- expire/unground 写入撞约束。SQLite 不能改 CHECK,按标准重建表模式迁移。

CREATE TABLE grounding_acts_new (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    common_ground_id TEXT NOT NULL,
    act TEXT NOT NULL CHECK (act IN
        ('assert','acknowledge','repair','withdraw','supersede',
         'expire','unground')),
    actor_cognizer_id TEXT,
    statement_id TEXT,
    occurred_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

INSERT INTO grounding_acts_new
    SELECT id, tenant_id, common_ground_id, act, actor_cognizer_id,
           statement_id, occurred_at, metadata_json
    FROM grounding_acts;

DROP TABLE grounding_acts;
ALTER TABLE grounding_acts_new RENAME TO grounding_acts;

CREATE INDEX idx_grounding_acts_cg
    ON grounding_acts(tenant_id, common_ground_id, occurred_at);
