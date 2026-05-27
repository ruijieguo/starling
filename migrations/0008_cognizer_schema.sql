-- Starling P2.a cognizer schema (per spec §5.1).
-- 4 tables + statements.holder_id backfill.

-- ── cognizers (主表) ──
CREATE TABLE cognizers (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    kind TEXT NOT NULL CHECK (kind IN
        ('self','human','agent','group','role','external')),
    canonical_name TEXT NOT NULL,
    canonical_name_normalized TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    aliases_normalized_json TEXT NOT NULL DEFAULT '[]',
    external_id TEXT NOT NULL,
    trust_priors_json TEXT NOT NULL DEFAULT '{}',
    permissions_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (id, tenant_id)
);
CREATE INDEX idx_cognizers_canonical_normalized
    ON cognizers(tenant_id, canonical_name_normalized);
CREATE INDEX idx_cognizers_external_id
    ON cognizers(tenant_id, kind, external_id);

-- ── cognizer_relations (Fiske 4-mode) ──
CREATE TABLE cognizer_relations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    a_id TEXT NOT NULL,
    b_id TEXT NOT NULL,
    fiske_weights_json TEXT NOT NULL DEFAULT '{}',
    affinity REAL NOT NULL DEFAULT 0.5 CHECK (affinity >= 0.0 AND affinity <= 1.0),
    trust_json TEXT NOT NULL DEFAULT '{}',
    power_asymmetry REAL NOT NULL DEFAULT 0.0,
    interaction_history_ref TEXT,
    valid_from TEXT,
    valid_to TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_relations_a
    ON cognizer_relations(tenant_id, a_id);
CREATE INDEX idx_relations_pair
    ON cognizer_relations(tenant_id, a_id, b_id);

-- ── cognizer_presence_log (KnowledgeFrontier 1/5: presence_log) ──
CREATE TABLE cognizer_presence_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cognizer_id TEXT NOT NULL,
    engram_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'default'
);
CREATE INDEX idx_presence_log_cognizer_time
    ON cognizer_presence_log(tenant_id, cognizer_id, observed_at);

-- ── cognizer_frontier_facts (KnowledgeFrontier 2-5/5: explicit_told / not_told / accessible_source / membership) ──
CREATE TABLE cognizer_frontier_facts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cognizer_id TEXT NOT NULL,
    statement_id TEXT,
    source_engram_id TEXT,
    fact_kind TEXT NOT NULL CHECK (fact_kind IN
        ('explicit_told','explicit_not_told','accessible_source','membership')),
    asserted_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_frontier_facts_cognizer
    ON cognizer_frontier_facts(tenant_id, cognizer_id, fact_kind);
CREATE INDEX idx_frontier_facts_statement
    ON cognizer_frontier_facts(tenant_id, statement_id);

-- ── Backfill: each distinct (tenant_id, holder_id) in statements → cognizers row ──
INSERT OR IGNORE INTO cognizers (
    id, tenant_id, kind, canonical_name, canonical_name_normalized,
    aliases_json, aliases_normalized_json, external_id,
    created_at, last_seen_at
)
SELECT
    lower(hex(randomblob(16))),
    s.tenant_id,
    'human',
    s.holder_id,
    lower(trim(s.holder_id)),
    json_array(s.holder_id),
    json_array(lower(trim(s.holder_id))),
    s.holder_id,
    COALESCE(MIN(s.created_at), '2026-05-26T00:00:00Z'),
    COALESCE(MAX(s.updated_at), '2026-05-26T00:00:00Z')
FROM statements s
GROUP BY s.tenant_id, s.holder_id;

-- ── Backfill: subject_kind='cognizer' subjects also get cognizers rows ──
INSERT OR IGNORE INTO cognizers (
    id, tenant_id, kind, canonical_name, canonical_name_normalized,
    aliases_json, aliases_normalized_json, external_id,
    created_at, last_seen_at
)
SELECT
    lower(hex(randomblob(16))),
    s.tenant_id,
    'human',
    s.subject_id,
    lower(trim(s.subject_id)),
    json_array(s.subject_id),
    json_array(lower(trim(s.subject_id))),
    s.subject_id,
    COALESCE(MIN(s.created_at), '2026-05-26T00:00:00Z'),
    COALESCE(MAX(s.updated_at), '2026-05-26T00:00:00Z')
FROM statements s
WHERE s.subject_kind = 'cognizer'
GROUP BY s.tenant_id, s.subject_id;
