-- M0.5 ConflictProbe indices on statements table.
-- idx_conflict_lookup: candidate prefilter for canonical_conflict_key matching.
-- idx_temporal_overlap: temporal overlap detection.

CREATE INDEX IF NOT EXISTS idx_conflict_lookup
    ON statements(
        tenant_id,
        holder_id,
        modality,
        subject_kind,
        subject_id,
        predicate,
        canonical_object_hash_version,
        canonical_object_hash
    );

CREATE INDEX IF NOT EXISTS idx_temporal_overlap
    ON statements(tenant_id, holder_id, valid_from, valid_to);
