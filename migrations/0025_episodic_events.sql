-- 0025: episodic_events — extension table for OCCURRED episodic-event statements (sub-project A).
-- One row per episodic event (statements.modality='occurred'); carries event-specific fields.
CREATE TABLE IF NOT EXISTS episodic_events (
    statement_id       TEXT NOT NULL,
    tenant_id          TEXT NOT NULL,
    seq                INTEGER NOT NULL,           -- monotonic event order within an ingestion
    event_time         TEXT,                       -- ISO8601, nullable
    location           TEXT,                       -- theme's resulting location, nullable
    participants_json  TEXT NOT NULL DEFAULT '[]', -- cognizers NAMED in this event
    action_raw         TEXT,                       -- surface verb
    PRIMARY KEY (statement_id, tenant_id),
    -- statements' PK is composite (id, tenant_id); SQLite FK targets must match a
    -- PRIMARY KEY / UNIQUE column set exactly, so reference both columns.
    FOREIGN KEY (statement_id, tenant_id) REFERENCES statements(id, tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_episodic_events_seq ON episodic_events(tenant_id, seq);
