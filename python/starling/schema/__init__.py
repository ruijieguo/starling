"""Starling schema layer (M0.1)."""
from starling.schema.enums import (
    Perspective, Modality, Polarity, ConsolidationState,
    EngramRetentionMode, SourceKind, IngestPolicy, IngestMode,
    PrivacyClass, StatementProvenance, ReviewStatus, EvidenceStatus,
    ContainerKind, EdgeKind, AnchorKind, BuildPolicy,
    CONSOLIDATION_TRANSITIONS,
)

__all__ = [
    "Perspective", "Modality", "Polarity", "ConsolidationState",
    "EngramRetentionMode", "SourceKind", "IngestPolicy", "IngestMode",
    "PrivacyClass", "StatementProvenance", "ReviewStatus", "EvidenceStatus",
    "ContainerKind", "EdgeKind", "AnchorKind", "BuildPolicy",
    "CONSOLIDATION_TRANSITIONS",
]
