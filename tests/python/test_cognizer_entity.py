from datetime import datetime, timezone
import pytest
from starling.schema.cognizer import Cognizer, AccessPolicy
from starling.schema.entity import Entity


def test_cognizer_derive_id_is_stable():
    a = Cognizer.derive_id("human", "user_42")
    b = Cognizer.derive_id("human", "user_42")
    assert a == b


def test_cognizer_derive_id_diff_kind_diff_id():
    a = Cognizer.derive_id("human", "user_42")
    b = Cognizer.derive_id("agent", "user_42")
    assert a != b


def test_cognizer_default_tenant():
    now = datetime(2026, 5, 23, tzinfo=timezone.utc)
    c = Cognizer(
        id=Cognizer.derive_id("human", "u1"),
        kind="human",
        canonical_name="Alice",
        external_id="u1",
        created_at=now,
        last_seen_at=now,
    )
    assert c.tenant_id == "default"


def test_cognizer_frozen():
    now = datetime(2026, 5, 23, tzinfo=timezone.utc)
    c = Cognizer(
        id=Cognizer.derive_id("human", "u1"),
        kind="human",
        canonical_name="Alice",
        external_id="u1",
        created_at=now,
        last_seen_at=now,
    )
    with pytest.raises(Exception):
        c.tenant_id = "other"  # type: ignore[misc]


def test_entity_no_persona_attribute():
    now = datetime(2026, 5, 23, tzinfo=timezone.utc)
    e = Entity(
        id=Entity.derive_id("project", "Project_X"),
        kind="project",
        canonical_name="Project_X",
        created_at=now,
    )
    assert not hasattr(e, "persona")
    assert not hasattr(e, "knowledge_frontier")
    assert not hasattr(e, "trust_priors")


def test_access_policy_default():
    p = AccessPolicy()
    assert p.policy_name == "default"
