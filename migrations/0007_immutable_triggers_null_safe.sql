-- Starling post-M0.7 NIT-3: harden immutable-field triggers against NULL.
--
-- Migration 0006 used `NEW.col != OLD.col`. SQL three-valued logic returns
-- NULL when either operand is NULL, which evaluates as "not true" in a
-- WHEN clause and would silently skip the RAISE. All five columns
-- (holder_id / holder_perspective / perceived_by_json / tenant_id /
-- provenance) are NOT NULL today so this is moot in current production,
-- but a future migration that loosens any of those NOT NULL constraints
-- would create a silent immutability bypass.
--
-- Fix: replace `!=` with `IS NOT`, which is NULL-safe (treats NULL as a
-- distinct value, not a wildcard) and matches SQLite's own idiom for
-- column-equality comparisons that must work under tri-valued logic.
--
-- The triggers are dropped and recreated rather than altered in place,
-- because SQLite has no ALTER TRIGGER. CREATE TRIGGER IF NOT EXISTS
-- alone would skip the work on a DB that already ran migration 0006.

DROP TRIGGER IF EXISTS trg_statements_immutable_holder_id;
DROP TRIGGER IF EXISTS trg_statements_immutable_holder_perspective;
DROP TRIGGER IF EXISTS trg_statements_immutable_perceived_by_json;
DROP TRIGGER IF EXISTS trg_statements_immutable_tenant_id;
DROP TRIGGER IF EXISTS trg_statements_immutable_provenance;

CREATE TRIGGER trg_statements_immutable_holder_id
BEFORE UPDATE OF holder_id ON statements
FOR EACH ROW
WHEN NEW.holder_id IS NOT OLD.holder_id
BEGIN
    SELECT RAISE(ABORT, 'immutable field: holder_id may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER trg_statements_immutable_holder_perspective
BEFORE UPDATE OF holder_perspective ON statements
FOR EACH ROW
WHEN NEW.holder_perspective IS NOT OLD.holder_perspective
BEGIN
    SELECT RAISE(ABORT, 'immutable field: holder_perspective (source_speaker) may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER trg_statements_immutable_perceived_by_json
BEFORE UPDATE OF perceived_by_json ON statements
FOR EACH ROW
WHEN NEW.perceived_by_json IS NOT OLD.perceived_by_json
BEGIN
    SELECT RAISE(ABORT, 'immutable field: perceived_by_json may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER trg_statements_immutable_tenant_id
BEFORE UPDATE OF tenant_id ON statements
FOR EACH ROW
WHEN NEW.tenant_id IS NOT OLD.tenant_id
BEGIN
    SELECT RAISE(ABORT, 'immutable field: tenant_id may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER trg_statements_immutable_provenance
BEFORE UPDATE OF provenance ON statements
FOR EACH ROW
WHEN NEW.provenance IS NOT OLD.provenance
BEGIN
    SELECT RAISE(ABORT, 'immutable field: provenance may not be updated in-place; use statement.corrected + supersedes');
END;
