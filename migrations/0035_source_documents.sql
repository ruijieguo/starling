CREATE UNIQUE INDEX IF NOT EXISTS idx_engrams_id_tenant ON engrams(id, tenant_id);
CREATE TABLE IF NOT EXISTS source_documents (
    tenant_id TEXT NOT NULL,
    holder_id TEXT NOT NULL,
    engram_ref TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, holder_id, engram_ref),
    FOREIGN KEY (engram_ref, tenant_id) REFERENCES engrams(id, tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_source_documents_scope ON source_documents(tenant_id, holder_id);
