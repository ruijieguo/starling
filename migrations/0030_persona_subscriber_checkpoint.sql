-- E (persona 物化接线): PersonaSubscriber outbox checkpoint (singleton, 仿 0022).
-- Drives persona rebuild as a tick_all stage on statement.derived/consolidated/superseded.
CREATE TABLE persona_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO persona_subscriber_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-07-01T00:00:00Z');
