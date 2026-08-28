-- Enforce the composite statement identity for all future CommonGround writes.
-- Triggers avoid rebuilding the table and preserve any historical orphan rows
-- for explicit audit/remediation instead of silently deleting them.
CREATE TRIGGER common_ground_statement_ref_insert
BEFORE INSERT ON common_ground
WHEN NOT EXISTS (
    SELECT 1 FROM statements s
    WHERE s.id = NEW.statement_id AND s.tenant_id = NEW.tenant_id
)
BEGIN
    SELECT RAISE(ABORT, 'common_ground statement not found in tenant');
END;

CREATE TRIGGER common_ground_statement_ref_update
BEFORE UPDATE OF statement_id, tenant_id ON common_ground
WHEN NOT EXISTS (
    SELECT 1 FROM statements s
    WHERE s.id = NEW.statement_id AND s.tenant_id = NEW.tenant_id
)
BEGIN
    SELECT RAISE(ABORT, 'common_ground statement not found in tenant');
END;

CREATE TRIGGER common_ground_superseded_ref_insert
BEFORE INSERT ON common_ground
WHEN NEW.superseded_by IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM statements s
    WHERE s.id = NEW.superseded_by AND s.tenant_id = NEW.tenant_id
)
BEGIN
    SELECT RAISE(ABORT, 'common_ground superseding statement not found in tenant');
END;

CREATE TRIGGER common_ground_superseded_ref_update
BEFORE UPDATE OF superseded_by ON common_ground
WHEN NEW.superseded_by IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM statements s
    WHERE s.id = NEW.superseded_by AND s.tenant_id = NEW.tenant_id
)
BEGIN
    SELECT RAISE(ABORT, 'common_ground superseding statement not found in tenant');
END;
