"""Engram + SourceRef + KeyRef placeholders (M0.1)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from starling.schema.refs import CognizerRef
from starling.schema.enums import (
    SourceKind, IngestPolicy, IngestMode, PrivacyClass, EngramRetentionMode,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceRef:
    """P1 placeholder. M0.2 EngramStore will extend."""
    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KeyRef:
    """P1 placeholder. KMS integration lands in P2+."""
    key_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Engram:
    id: uuid.UUID
    source: SourceRef
    source_kind: SourceKind
    ingest_policy: IngestPolicy
    ingest_mode: IngestMode
    privacy_class: PrivacyClass
    byte_preserving: bool
    content_hash: str
    retention_mode: EngramRetentionMode
    chunk_index: int
    timestamp: datetime
    adapter_name: str | None = None
    adapter_version: str | None = None
    declared_transformations: tuple[str, ...] = ()
    content_ciphertext: bytes | None = None
    redacted_content: str | None = None
    key_ref: KeyRef | None = None
    speaker: CognizerRef | None = None
    source_time_range: tuple[datetime, datetime] | None = None
    segment_map: tuple = ()
    audit_trail: tuple = ()
