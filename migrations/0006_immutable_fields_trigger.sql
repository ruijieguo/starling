-- Starling M0.7 immutable-field enforcement. Spec §15.3.1 (TC-NEG-IMMUTABLE):
-- "post-write in-place UPDATE on holder / source_speaker / perceived_by /
--  tenant_id / provenance must be rejected; correct path is
--  statement.corrected + supersedes."
--
-- DB column mapping:
--   holder          → holder_id
--   source_speaker  → holder_perspective  (QUOTED perspective encodes source-speaker
--                     identity; source_speaker is merged into perceived_by_json at
--                     ingest time and this column tracks the attribution mode)
--   perceived_by    → perceived_by_json
--   tenant_id       → tenant_id
--   provenance      → provenance
--
-- Each BEFORE UPDATE trigger fires only when the relevant column changes.
-- RAISE(ABORT, ...) rolls back the triggering statement and surfaces a
-- sqlite3.DatabaseError in Python with the message text below.

CREATE TRIGGER IF NOT EXISTS trg_statements_immutable_holder_id
BEFORE UPDATE OF holder_id ON statements
FOR EACH ROW
WHEN NEW.holder_id != OLD.holder_id
BEGIN
    SELECT RAISE(ABORT, 'immutable field: holder_id may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER IF NOT EXISTS trg_statements_immutable_holder_perspective
BEFORE UPDATE OF holder_perspective ON statements
FOR EACH ROW
WHEN NEW.holder_perspective != OLD.holder_perspective
BEGIN
    SELECT RAISE(ABORT, 'immutable field: holder_perspective (source_speaker) may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER IF NOT EXISTS trg_statements_immutable_perceived_by_json
BEFORE UPDATE OF perceived_by_json ON statements
FOR EACH ROW
WHEN NEW.perceived_by_json != OLD.perceived_by_json
BEGIN
    SELECT RAISE(ABORT, 'immutable field: perceived_by_json may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER IF NOT EXISTS trg_statements_immutable_tenant_id
BEFORE UPDATE OF tenant_id ON statements
FOR EACH ROW
WHEN NEW.tenant_id != OLD.tenant_id
BEGIN
    SELECT RAISE(ABORT, 'immutable field: tenant_id may not be updated in-place; use statement.corrected + supersedes');
END;

CREATE TRIGGER IF NOT EXISTS trg_statements_immutable_provenance
BEFORE UPDATE OF provenance ON statements
FOR EACH ROW
WHEN NEW.provenance != OLD.provenance
BEGIN
    SELECT RAISE(ABORT, 'immutable field: provenance may not be updated in-place; use statement.corrected + supersedes');
END;
