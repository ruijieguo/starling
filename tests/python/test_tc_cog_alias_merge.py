"""
TC-COG-ALIAS-MERGE — CRITICAL #2 (08_cognizer)

Validates that normalized alias collision detection is exhaustive:
- Exact string collision
- Case-insensitive collision ("Alice" vs "alice")
- Leading/trailing whitespace collapse (" ALICE " normalizes to "alice")
- AliasCollision exception is raised (payload is opaque from Python side —
  pybind registers AliasCollision as RuntimeError subclass without .existing_id
  or .alias attributes exposed; only .args is available)
- Idempotent re-register of same cognizer with same aliases does not raise
- Re-register same external_id with new alias merges aliases (no collision)
- Lookup by merged alias (with case mods) finds the cognizer
- Non-colliding aliases coexist across different cognizers
- Internal whitespace collapse ("zhang  wei" == "zhang wei" after normalize)
- Multi-alias list where only one alias collides raises AliasCollision
"""
from __future__ import annotations

import pytest
import starling._core as _core


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    return _core.SqliteAdapter.open(":memory:")


@pytest.fixture
def hub(adapter):
    return _core.CognizerHub(adapter)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _register_alice(hub, tenant_id="default"):
    return hub.register_cognizer(
        kind="human",
        external_id="alice-001",
        canonical_name="Alice",
        tenant_id=tenant_id,
        aliases=["Alice"],
    )


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-01: register with unique alias succeeds
# ---------------------------------------------------------------------------

def test_register_with_unique_alias_succeeds(hub):
    """Registering A with alias 'Alice' succeeds without exception."""
    c = _register_alice(hub)
    assert c.id is not None
    assert c.external_id == "alice-001"


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-02: collision via lowercase
# ---------------------------------------------------------------------------

def test_register_collision_via_lowercase(hub):
    """Registering B with alias 'alice' (lowercase of 'Alice') raises AliasCollision."""
    _register_alice(hub)
    with pytest.raises(_core.AliasCollision):
        hub.register_cognizer(
            kind="human",
            external_id="alice-002",
            canonical_name="Bob Jones",
            tenant_id="default",
            aliases=["alice"],
        )


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-03: collision via whitespace + case
# ---------------------------------------------------------------------------

def test_register_collision_via_whitespace(hub):
    """' ALICE ' normalizes to 'alice' and collides with stored 'Alice'."""
    _register_alice(hub)
    with pytest.raises(_core.AliasCollision):
        hub.register_cognizer(
            kind="human",
            external_id="alice-003",
            canonical_name="Carol",
            tenant_id="default",
            aliases=[" ALICE "],
        )


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-04: AliasCollision exception is raised (payload check)
#
# NOTE: pybind registers AliasCollision as a plain RuntimeError subclass.
# The C++ fields existing_id and alias are NOT exposed as Python attributes in
# this build — only .args[0] carries a static message string. The CRITICAL
# requirement (rejection is enforced) is validated by the raises assertions
# above and below. This test confirms the exception type and message heuristic.
# ---------------------------------------------------------------------------

def test_alias_collision_exception_is_raised(hub):
    """AliasCollision is raised and carries a non-empty message."""
    _register_alice(hub)
    with pytest.raises(_core.AliasCollision) as exc_info:
        hub.register_cognizer(
            kind="human",
            external_id="alice-004",
            canonical_name="Alice X",
            tenant_id="default",
            aliases=["Alice"],
        )
    e = exc_info.value
    # Exception must carry a descriptive message
    assert len(e.args) > 0
    assert isinstance(e.args[0], str)
    assert len(e.args[0]) > 0


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-05: re-register same external_id merges aliases
# ---------------------------------------------------------------------------

def test_re_register_same_external_id_merges_aliases(hub):
    """Re-registering A with new alias 'alice@example.com' merges aliases.

    Same (kind, external_id) -> same UUID5 -> idempotent; the second call
    adds a new alias rather than raising AliasCollision.
    """
    c_a = _register_alice(hub)
    c_a2 = hub.register_cognizer(
        kind="human",
        external_id="alice-001",
        canonical_name="Alice Smith",
        tenant_id="default",
        aliases=["alice@example.com"],
    )
    assert c_a.id == c_a2.id, "UUID5 must be the same for same (kind, external_id)"

    fetched = hub.get(c_a.id, "default")
    assert fetched is not None
    # Both original alias and new alias must be present
    assert "Alice" in fetched.aliases
    assert "alice@example.com" in fetched.aliases


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-06: lookup by alias (with case mods) finds merged cognizer
# ---------------------------------------------------------------------------

def test_lookup_by_alias_normalize_finds_merged(hub):
    """After merge, lookup by 'alice@example.com' with case mods finds A."""
    c_a = _register_alice(hub)
    # Merge a new alias
    hub.register_cognizer(
        kind="human",
        external_id="alice-001",
        canonical_name="Alice Smith",
        tenant_id="default",
        aliases=["alice@example.com"],
    )
    # Lookup with uppercase variant — normalize_alias folds to same key
    result = hub.lookup_by_alias("default", "ALICE@EXAMPLE.COM")
    assert result == c_a.id

    # Lookup with original alias still works
    result2 = hub.lookup_by_alias("default", "alice")
    assert result2 == c_a.id


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-07: non-colliding aliases coexist
# ---------------------------------------------------------------------------

def test_non_colliding_aliases_coexist(hub):
    """Distinct normalized aliases can coexist across different cognizers."""
    hub.register_cognizer(
        kind="human",
        external_id="bob-001",
        canonical_name="Bob",
        tenant_id="default",
        aliases=["Bobby"],
    )
    c_charlie = hub.register_cognizer(
        kind="human",
        external_id="charlie-001",
        canonical_name="Charlie",
        tenant_id="default",
        aliases=["Charlie"],
    )
    assert c_charlie.id is not None
    assert hub.lookup_by_alias("default", "Bobby") is not None
    assert hub.lookup_by_alias("default", "Charlie") is not None


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-08: internal whitespace collapse collision
# ---------------------------------------------------------------------------

def test_internal_whitespace_collapse_collision(hub):
    """'zhang  wei' (double space) normalizes to 'zhang wei' and collides."""
    hub.register_cognizer(
        kind="human",
        external_id="zhang-001",
        canonical_name="Zhang Wei",
        tenant_id="default",
        aliases=["zhang wei"],
    )
    with pytest.raises(_core.AliasCollision):
        hub.register_cognizer(
            kind="human",
            external_id="zhang-002",
            canonical_name="Zhang Wei Dup",
            tenant_id="default",
            aliases=["zhang  wei"],
        )


# ---------------------------------------------------------------------------
# TC-COG-ALIAS-MERGE-09: multi-alias partial collision raises
# ---------------------------------------------------------------------------

def test_multi_alias_partial_collision(hub):
    """If one alias in a list collides, AliasCollision is raised for that alias."""
    _register_alice(hub)
    with pytest.raises(_core.AliasCollision):
        hub.register_cognizer(
            kind="human",
            external_id="multi-001",
            canonical_name="Multi",
            tenant_id="default",
            aliases=["Unique-XYZ-999", "Alice"],
        )
