-- Starling M0.6 retrieval index. Per docs/design/subsystems_design/13_retrieval.md
-- §"P1 basic_retrieve 闭环": basic_retrieve filters by (holder, consolidation_state,
-- valid_from, valid_to) on the statements main table. The composite covers tenant
-- isolation (leading column) + holder scoping + state filter + predicate equality
-- + time-anchor range.

CREATE INDEX IF NOT EXISTS idx_statements_basic_retrieve
    ON statements(tenant_id, holder_id, consolidation_state, predicate, valid_from, valid_to);
