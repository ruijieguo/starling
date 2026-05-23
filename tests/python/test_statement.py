from datetime import datetime, timezone
import uuid
import pytest
from starling.schema.statement import Statement, EvidenceRef, TimeRange
from starling.schema.refs import CognizerRef, EntityRef, EngramRef
from starling.schema.affect import AffectVector
from starling.schema.enums import (
    Perspective, Modality, Polarity, EvidenceStatus,
    StatementProvenance, ConsolidationState, ReviewStatus,
)


def _now() -> datetime:
    return datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)


def _affect_zero() -> AffectVector:
    return AffectVector(valence=0.0, arousal=0.0, dominance=0.0, novelty=0.0, stakes=0.0)


def _minimal_statement(**overrides) -> Statement:
    holder = CognizerRef(uuid.uuid4())
    subject = EntityRef(uuid.uuid4())
    base = dict(
        id=uuid.uuid4(),
        tenant_id="default",
        holder=holder,
        holder_perspective=Perspective.FIRST_PERSON,
        subject=subject,
        predicate="status",
        object="active",
        modality=Modality.BELIEVES,
        polarity=Polarity.POS,
        confidence=0.9,
        observed_at=_now(),
        evidence=(EvidenceRef(
            engram_ref=EngramRef(uuid.uuid4()),
            content_hash="a"*64,
        ),),
        salience=0.5,
        affect=_affect_zero(),
        activation=0.0,
        last_accessed=_now(),
        provenance=StatementProvenance.USER_INPUT,
        canonical_object_hash="b"*64,
    )
    base.update(overrides)
    return Statement(**base)


def test_statement_constructs():
    s = _minimal_statement()
    assert s.consolidation_state == ConsolidationState.VOLATILE
    assert s.review_status == ReviewStatus.APPROVED
    assert s.derived_depth == 0
    assert s.nesting_depth == 0


def test_statement_frozen():
    s = _minimal_statement()
    with pytest.raises(Exception):
        s.confidence = 0.1  # type: ignore[misc]


def test_statement_field_count_at_least_30():
    """§3.3 documents 30+ fields. Lock the lower bound so removals are intentional."""
    fields = list(Statement.__dataclass_fields__)
    assert len(fields) >= 30


def test_statement_default_state_volatile():
    s = _minimal_statement()
    assert s.consolidation_state == ConsolidationState.VOLATILE


def test_evidence_ref_default_active():
    ref = EvidenceRef(
        engram_ref=EngramRef(uuid.uuid4()),
        content_hash="c"*64,
    )
    assert ref.status == EvidenceStatus.ACTIVE
    assert ref.erased_at is None


def test_time_range_optional_bounds():
    r = TimeRange()
    assert r.start is None
    assert r.end is None
    r2 = TimeRange(start=_now())
    assert r2.start is not None and r2.end is None
