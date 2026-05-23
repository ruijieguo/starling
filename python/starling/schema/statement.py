"""Statement core dataclass + EvidenceRef + TimeRange (M0.1, §3.3 / §3.11).

Statement is the centerpiece of the schema layer: 36 fields covering subject /
content / time / evidence / brain-like dynamics dimensions. It is
``frozen=True, slots=True, kw_only=True`` so that field ordering mirrors §3.3
documentation order regardless of which fields carry defaults.

Subclasses (`EpisodicEvent / Commitment / Norm / Skill`, §3.6) are intentionally
NOT implemented in M0.1 — they require `Trigger / NormScope / ProcedureSpec`
types that don't land until P2/P3. Cross-field validators live in T8.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from starling.schema.affect import AffectVector
from starling.schema.enums import (
    Perspective, Modality, Polarity, EvidenceStatus,
    StatementProvenance, ConsolidationState, ReviewStatus,
)
from starling.schema.refs import (
    CognizerRef, EntityRef, StatementRef, EngramRef,
)
from starling.schema.source import SourceSpanRef
from starling.schema.temporal import TemporalAnchor, ConfidenceEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceRef:
    engram_ref: EngramRef
    content_hash: str
    status: EvidenceStatus = EvidenceStatus.ACTIVE
    erased_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeRange:
    start: datetime | None = None
    end: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Statement:
    # ── 主体维度 ─────────────────────────────────────────────────────
    id: uuid.UUID
    tenant_id: str
    holder: CognizerRef
    holder_perspective: Perspective
    # ── 内容维度 ─────────────────────────────────────────────────────
    subject: CognizerRef | EntityRef
    predicate: str
    object: bool | int | float | str | datetime | CognizerRef | EntityRef | StatementRef
    modality: Modality
    polarity: Polarity
    confidence: float
    # ── 时间维度 ─────────────────────────────────────────────────────
    observed_at: datetime
    # ── 证据归因 ─────────────────────────────────────────────────────
    # ── 类脑动力学 ───────────────────────────────────────────────────
    salience: float
    affect: AffectVector
    activation: float
    last_accessed: datetime
    provenance: StatementProvenance
    canonical_object_hash: str
    # ── defaulted fields ─────────────────────────────────────────────
    confidence_history: tuple[ConfidenceEvent, ...] = ()
    event_time: TimeRange | None = None
    inferred_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    source_spans: tuple[SourceSpanRef, ...] = ()
    temporal_anchor: TemporalAnchor | None = None
    derived_from: tuple[StatementRef, ...] = ()
    derived_depth: int = 0
    perceived_by: tuple[CognizerRef, ...] = ()
    supersedes: StatementRef | None = None
    access_count: int = 0
    last_replayed: datetime | None = None
    replay_count: int = 0
    consolidation_state: ConsolidationState = ConsolidationState.VOLATILE
    review_status: ReviewStatus = ReviewStatus.APPROVED
    nesting_depth: int = 0
    visibility: tuple[CognizerRef, ...] = ()
    retention_policy: str | None = None
    canonical_object_hash_version: str = "v1"
