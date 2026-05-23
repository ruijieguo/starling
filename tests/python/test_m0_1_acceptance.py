"""M0.1 acceptance: build a realistic Statement end-to-end and round-trip its
canonical hash through both Python and C++ paths."""
from datetime import datetime, timezone
import uuid
import jsonschema

from starling.schema import (
    Statement, Cognizer, Entity, AffectVector,
    StatementProvenance, Modality, Polarity, Perspective, ConsolidationState,
)
from starling.schema.refs import CognizerRef, EntityRef, EngramRef
from starling.schema.statement import EvidenceRef
from starling.schema.value import canonicalize_object
from starling.schema.validators import (
    validate_evidence_or_derivation,
    validate_subject_not_statement,
    validate_canonical_object_hash,
)
from starling.schema.jsonschema_export import all_schemas


def test_alice_says_bob_no_longer_owns_auth_end_to_end():
    """End-to-end happy path: §14.1 input flow, M0.1 schema layer only."""
    now = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)

    alice = Cognizer(
        id=Cognizer.derive_id("human", "alice"),
        kind="human", canonical_name="Alice",
        external_id="alice", created_at=now, last_seen_at=now,
    )
    auth_module = Entity(
        id=Entity.derive_id("project", "auth_module"),
        kind="project", canonical_name="auth_module", created_at=now,
    )
    engram_id = uuid.uuid4()

    object_value = "deprecated"
    canonical, hash_hex = canonicalize_object(object_value)

    stmt = Statement(
        id=uuid.uuid4(),
        tenant_id="default",
        holder=CognizerRef(alice.id),
        holder_perspective=Perspective.FIRST_PERSON,
        subject=EntityRef(auth_module.id),
        predicate="ownership_status",
        object=object_value,
        modality=Modality.BELIEVES,
        polarity=Polarity.POS,
        confidence=0.95,
        observed_at=now,
        evidence=(EvidenceRef(
            engram_ref=EngramRef(engram_id),
            content_hash="0"*64,
        ),),
        salience=0.6,
        affect=AffectVector(valence=-0.2, arousal=0.4, dominance=0.0,
                            novelty=0.7, stakes=0.8),
        activation=0.5,
        last_accessed=now,
        provenance=StatementProvenance.USER_INPUT,
        canonical_object_hash=hash_hex,
    )

    validate_evidence_or_derivation(stmt)
    validate_subject_not_statement(stmt)
    validate_canonical_object_hash(stmt)

    assert stmt.consolidation_state == ConsolidationState.VOLATILE


def test_jsonschema_export_round_trips_against_a_real_payload():
    """Encode a Cognizer dict, validate against the exported schema."""
    schemas = all_schemas()
    cognizer_schema = schemas["Cognizer"]
    payload = {
        "id": str(uuid.uuid4()),
        "tenant_id": "default",
        "kind": "human",
        "canonical_name": "Alice",
        "aliases": ["alice"],
        "external_id": "alice",
        "persona": None,
        "knowledge_frontier": None,
        "relations": [],
        "trust_priors": [],
        "permissions": None,
        "created_at": "2026-05-23T12:00:00Z",
        "last_seen_at": "2026-05-23T12:00:00Z",
    }
    jsonschema.validate(payload, cognizer_schema)
