-- #38-C Phase 3: natural-language summary of a NORM gist, produced by the
-- consolidation LLM (the "NORM-gist" judgment's prose form). NULL for every
-- non-gist statement. Additive + nullable → no table rewrite, no impact on the
-- explicit-column INSERT/SELECT paths. The structured gist identity
-- (holder/subject/predicate/object) stays the source of truth + the
-- clustering/idempotency key; this column is the human-readable rendering only.
ALTER TABLE statements ADD COLUMN consolidation_summary TEXT;
