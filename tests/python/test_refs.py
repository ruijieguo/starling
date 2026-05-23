import uuid
import pytest
from starling.schema.refs import (
    CognizerRef, EntityRef, StatementRef, EngramRef,
    PersonaRef, KnowledgeFrontierRef,
)


def test_ref_frozen():
    r = CognizerRef(uuid.uuid4())
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError under slots
        r.id = uuid.uuid4()  # type: ignore[misc]


def test_ref_equality_by_id():
    u = uuid.uuid4()
    assert CognizerRef(u) == CognizerRef(u)
    # Cross-type equality is NOT defined: CognizerRef with the same UUID is
    # not equal to EntityRef. This protects against silent ref-class confusion
    # in dict keys and JSON round-trips.
    assert CognizerRef(u) != EntityRef(u)


def test_ref_hashable():
    u = uuid.uuid4()
    s = {CognizerRef(u), CognizerRef(u)}
    assert len(s) == 1


def test_ref_str_round_trip():
    u = uuid.uuid4()
    r = CognizerRef(u)
    assert str(r) == str(u)
    assert CognizerRef.from_str(str(u)) == r


def test_statement_ref_distinct_from_engram_ref():
    u = uuid.uuid4()
    assert StatementRef(u) != EngramRef(u)


def test_persona_and_knowledge_frontier_distinct():
    u = uuid.uuid4()
    assert PersonaRef(u) != KnowledgeFrontierRef(u)
