from datetime import datetime, timezone
import uuid
import pytest
from starling.schema.container import (
    Container, Persona, CommonGround, KnowledgeFrontier,
    PERSONA_DIMENSIONS, COMMON_GROUND_DIMENSIONS, KNOWLEDGE_FRONTIER_DIMENSIONS,
    VALID_DIMENSIONS,
)
from starling.schema.refs import CognizerRef
from starling.schema.enums import ContainerKind, BuildPolicy


def _now():
    return datetime(2026, 5, 23, tzinfo=timezone.utc)


def test_persona_dimension_keys():
    assert "traits" in PERSONA_DIMENSIONS
    assert "preferences" in PERSONA_DIMENSIONS
    assert len(PERSONA_DIMENSIONS) == 7


def test_common_ground_dimension_keys():
    assert len(COMMON_GROUND_DIMENSIONS) == 4
    assert "grounded" in COMMON_GROUND_DIMENSIONS


def test_knowledge_frontier_dimension_keys():
    assert len(KNOWLEDGE_FRONTIER_DIMENSIONS) == 5


def test_valid_dimensions_keyed_by_kind():
    assert VALID_DIMENSIONS[ContainerKind.PERSONA] == PERSONA_DIMENSIONS
    assert VALID_DIMENSIONS[ContainerKind.COMMON_GROUND] == COMMON_GROUND_DIMENSIONS
    assert VALID_DIMENSIONS[ContainerKind.KNOWLEDGE_FRONTIER] == KNOWLEDGE_FRONTIER_DIMENSIONS


def test_persona_constructs():
    p = Persona(
        id=uuid.uuid4(),
        kind=ContainerKind.PERSONA,
        cognizer=CognizerRef(uuid.uuid4()),
        last_rebuilt_at=_now(),
    )
    assert p.version == 0
    assert p.build_policy == BuildPolicy.ON_EVENT


def test_common_ground_n_ary_parties():
    parties = tuple(CognizerRef(uuid.uuid4()) for _ in range(3))
    cg = CommonGround(
        id=uuid.uuid4(),
        kind=ContainerKind.COMMON_GROUND,
        parties=parties,
        last_rebuilt_at=_now(),
    )
    assert len(cg.parties) == 3


def test_knowledge_frontier_constructs():
    kf = KnowledgeFrontier(
        id=uuid.uuid4(),
        kind=ContainerKind.KNOWLEDGE_FRONTIER,
        cognizer=CognizerRef(uuid.uuid4()),
        last_rebuilt_at=_now(),
    )
    assert kf.kind == ContainerKind.KNOWLEDGE_FRONTIER


def test_container_frozen():
    p = Persona(
        id=uuid.uuid4(),
        kind=ContainerKind.PERSONA,
        cognizer=CognizerRef(uuid.uuid4()),
        last_rebuilt_at=_now(),
    )
    with pytest.raises(Exception):
        p.version = 1  # type: ignore[misc]
