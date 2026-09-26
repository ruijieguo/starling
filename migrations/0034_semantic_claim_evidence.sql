-- Optional direct-source semantic evidence; existing statements remain NULL.
ALTER TABLE statements ADD COLUMN semantic_claim_json TEXT;
