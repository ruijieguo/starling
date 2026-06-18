-- 0026: perception_state — per-cognizer last-known state of a theme (sub-project B).
-- Append-only: one row per (cognizer, perceived state-event). The PerceptionReconstructor
-- is the single writer; what_does_X_think reads the highest-position row with
-- observed_at <= as_of per (cognizer, theme, state_dim). observed_at (ingest time, the
-- as_of/order key) is used because A's episodic_events.event_time is nullable.
CREATE TABLE IF NOT EXISTS perception_state (
    tenant_id        TEXT NOT NULL,
    cognizer_id      TEXT NOT NULL,
    theme_id         TEXT NOT NULL,        -- statements.object_value (theme)
    state_dim        TEXT NOT NULL,        -- 'location' | 'content'
    state_value      TEXT NOT NULL,        -- e.g. 'basket'
    observed_at      TEXT NOT NULL,        -- ingest time; the as_of/order key
    position         INTEGER NOT NULL,     -- global event order index (tie-break within observed_at)
    source_event_id  TEXT NOT NULL,        -- the OCCURRED statement id this perception came from
    PRIMARY KEY (tenant_id, cognizer_id, source_event_id)
);
CREATE INDEX IF NOT EXISTS idx_perception_state_query
    ON perception_state(tenant_id, cognizer_id, theme_id, state_dim, position);
