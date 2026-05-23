from datetime import datetime, timezone
import uuid
import pytest

from starling.schema.statement import Statement, EvidenceRef, TimeRange
from starling.schema.refs import (
    CognizerRef, EntityRef, StatementRef, EngramRef,
)
from starling.schema.affect import AffectVector
from starling.schema.cognizer import Cognizer
from starling.schema.enums import (
    Perspective, Modality, Polarity, EvidenceStatus,
    StatementProvenance, ContainerKind,
)
from starling.schema.value import canonicalize_object
from starling.schema.validators import (
    SchemaInvalid,
    validate_evidence_or_derivation,
    validate_subject_not_statement,
    validate_derived_depth,
    validate_tenant_derived,
    validate_perspective_provenance,
    validate_canonical_object_hash,
    validate_evidence_status,
    validate_container_dimension,
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


def test_evidence_or_derivation_user_input_needs_evidence():
    s = _minimal_statement(evidence=(), derived_from=(),
                           provenance=StatementProvenance.USER_INPUT)
    with pytest.raises(SchemaInvalid):
        validate_evidence_or_derivation(s)


def test_evidence_or_derivation_replay_derived_needs_derived_from():
    s = _minimal_statement(
        evidence=(), derived_from=(),
        provenance=StatementProvenance.REPLAY_DERIVED,
    )
    with pytest.raises(SchemaInvalid):
        validate_evidence_or_derivation(s)


def test_evidence_or_derivation_replay_derived_with_parent_ok():
    parent = StatementRef(uuid.uuid4())
    s = _minimal_statement(
        evidence=(), derived_from=(parent,),
        provenance=StatementProvenance.REPLAY_DERIVED,
    )
    validate_evidence_or_derivation(s)


def test_evidence_or_derivation_user_input_with_evidence_ok():
    s = _minimal_statement(provenance=StatementProvenance.USER_INPUT)
    validate_evidence_or_derivation(s)


def test_subject_not_statement_ref():
    holder = CognizerRef(uuid.uuid4())
    bogus_subject = StatementRef(uuid.uuid4())
    bogus = Statement(
        id=uuid.uuid4(), tenant_id="default", holder=holder,
        holder_perspective=Perspective.FIRST_PERSON,
        subject=bogus_subject,
        predicate="x", object="y",
        modality=Modality.BELIEVES, polarity=Polarity.POS,
        confidence=0.9, observed_at=_now(),
        evidence=(EvidenceRef(
            engram_ref=EngramRef(uuid.uuid4()),
            content_hash="a"*64,
        ),),
        salience=0.5, affect=_affect_zero(),
        activation=0.0, last_accessed=_now(),
        provenance=StatementProvenance.USER_INPUT,
        canonical_object_hash="b"*64,
    )
    with pytest.raises(SchemaInvalid, match="subject"):
        validate_subject_not_statement(bogus)


def test_subject_entity_ref_ok():
    s = _minimal_statement()
    validate_subject_not_statement(s)


def test_canonical_object_hash_matches():
    canon, h = canonicalize_object("status_active")
    s = _minimal_statement(object="status_active", canonical_object_hash=h)
    validate_canonical_object_hash(s)


def test_canonical_object_hash_mismatch():
    s = _minimal_statement(object="status_active", canonical_object_hash="0"*64)
    with pytest.raises(SchemaInvalid, match="canonical_object_hash"):
        validate_canonical_object_hash(s)


def test_evidence_status_active_requires_no_erased_at():
    bad = EvidenceRef(
        engram_ref=EngramRef(uuid.uuid4()),
        status=EvidenceStatus.ACTIVE,
        content_hash="a"*64,
        erased_at=_now(),
    )
    s = _minimal_statement(evidence=(bad,))
    with pytest.raises(SchemaInvalid, match="evidence_status"):
        validate_evidence_status(s)


def test_evidence_status_erased_requires_erased_at():
    bad = EvidenceRef(
        engram_ref=EngramRef(uuid.uuid4()),
        status=EvidenceStatus.ERASED,
        content_hash="a"*64,
        erased_at=None,
    )
    s = _minimal_statement(evidence=(bad,))
    with pytest.raises(SchemaInvalid, match="evidence_status"):
        validate_evidence_status(s)


def test_container_dimension_persona_legal():
    validate_container_dimension(ContainerKind.PERSONA, "traits")


def test_container_dimension_persona_illegal():
    with pytest.raises(SchemaInvalid, match="dimension"):
        validate_container_dimension(ContainerKind.PERSONA, "bogus_key")


def test_container_dimension_cross_kind_illegal():
    with pytest.raises(SchemaInvalid, match="dimension"):
        validate_container_dimension(ContainerKind.PERSONA, "grounded")


def test_derived_depth_zero_when_no_parents():
    s = _minimal_statement(derived_from=(), derived_depth=0)
    validate_derived_depth(s, parent_depths={})


def test_derived_depth_max_parent_plus_one():
    parent = StatementRef(uuid.uuid4())
    s = _minimal_statement(
        derived_from=(parent,),
        derived_depth=3,
        provenance=StatementProvenance.REPLAY_DERIVED,
    )
    validate_derived_depth(s, parent_depths={parent: 2})


def test_derived_depth_mismatch_raises():
    parent = StatementRef(uuid.uuid4())
    s = _minimal_statement(
        derived_from=(parent,),
        derived_depth=99,
        provenance=StatementProvenance.REPLAY_DERIVED,
    )
    with pytest.raises(SchemaInvalid, match="derived_depth"):
        validate_derived_depth(s, parent_depths={parent: 2})


def test_tenant_derived_match():
    holder = Cognizer(
        id=uuid.uuid4(), kind="human", canonical_name="Alice",
        external_id="alice", created_at=_now(), last_seen_at=_now(),
        tenant_id="default",
    )
    s = _minimal_statement(holder=CognizerRef(holder.id), tenant_id="default")
    validate_tenant_derived(s, holder)


def test_tenant_derived_mismatch_raises():
    holder = Cognizer(
        id=uuid.uuid4(), kind="human", canonical_name="Alice",
        external_id="alice", created_at=_now(), last_seen_at=_now(),
        tenant_id="other_tenant",
    )
    s = _minimal_statement(holder=CognizerRef(holder.id), tenant_id="default")
    with pytest.raises(SchemaInvalid, match="tenant_id"):
        validate_tenant_derived(s, holder)


def test_perspective_provenance_tom_inferred_requires_inferred_perspective():
    parent = StatementRef(uuid.uuid4())
    bad = _minimal_statement(
        provenance=StatementProvenance.TOM_INFERRED,
        derived_from=(parent,),
        evidence=(),
        holder_perspective=Perspective.FIRST_PERSON,
    )
    with pytest.raises(SchemaInvalid, match="tom_inferred"):
        validate_perspective_provenance(bad)


def test_perspective_provenance_user_input_unrestricted():
    s = _minimal_statement(
        provenance=StatementProvenance.USER_INPUT,
        holder_perspective=Perspective.QUOTED,
    )
    validate_perspective_provenance(s)
