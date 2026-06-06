-- P2.j 社会域接线：scope_parties（独立于 perceived_by 的 grounding 群体）+
-- CommonGroundSubscriber checkpoint + common_ground 轮次计数（#2 共同在场推定）。

-- 1. statements.scope_parties_json：grounding 参与方（sorted{self,interlocutor}），
--    可空；仅对话语境填。与 perceived_by_json（信息可见性）语义分离。
ALTER TABLE statements ADD COLUMN scope_parties_json TEXT;

-- 2. 不可变 trigger（沿用 0007 NULL-safe 模式）。
CREATE TRIGGER trg_statements_immutable_scope_parties_json
BEFORE UPDATE OF scope_parties_json ON statements
FOR EACH ROW
WHEN NEW.scope_parties_json IS NOT OLD.scope_parties_json
BEGIN
    SELECT RAISE(ABORT, 'immutable field: scope_parties_json may not be updated in-place; use statement.corrected + supersedes');
END;

-- 3. common_ground 轮次计数（#2 共同在场推定 N=3）。
ALTER TABLE common_ground ADD COLUMN rounds_since_assert INTEGER NOT NULL DEFAULT 0;

-- 4. CommonGroundSubscriber outbox checkpoint（singleton，仿 tom_belief_tracker_checkpoint）。
CREATE TABLE common_ground_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO common_ground_subscriber_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-06-06T00:00:00Z');
