-- M0.8 Neocortex Persona/CommonGround Container 物化载荷 (per spec §5.3).
ALTER TABLE containers ADD COLUMN content_json TEXT NOT NULL DEFAULT '{}';
