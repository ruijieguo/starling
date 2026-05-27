"""Smoke tests for starling.cognizer Python package and builders.

Verifies:
  1. All public types importable from starling.cognizer
  2. for_human builder + CognizerHub.register_cognizer round-trip
  3. for_group with explicit tenant_id works
  4. for_group() with no tenant_id raises TypeError (Python keyword-only enforcement)
"""
from __future__ import annotations

import pytest

from starling import runtime
from starling.testing import relax_preflight_for_m0_3  # NOLINT(starling-testing-isolation)


@pytest.fixture
def rt(tmp_path, monkeypatch):
    """File-backed Runtime with the M0.3 preflight relaxed for tests."""
    original = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", original)
    return r


def test_imports_work():
    """All public symbols importable from starling.cognizer."""
    from starling.cognizer import (
        CognizerKind,
        FiskeMode,
        Cognizer,
        RelationEdge,
        CognizerHub,
        KnowledgeFrontier,
        AliasCollision,
        FiskeWeightsInvalid,
        GroupTenantImplicit,
        CognizerNotFound,
        for_human,
        for_agent,
        for_group,
        for_role,
        for_external,
        for_self,
    )
    assert CognizerKind.Human is not None
    assert FiskeMode.Communal is not None


def test_for_human_register(rt):
    """for_human builder + CognizerHub.register_cognizer produces a Cognizer."""
    from starling._core import CognizerHub
    from starling.cognizer.builders import for_human

    hub = CognizerHub(rt.adapter)
    kwargs = for_human("alice@example.com", canonical_name="Alice Smith")
    cognizer = hub.register_cognizer(**kwargs)

    assert cognizer.id
    assert cognizer.kind.name == "Human"
    assert cognizer.canonical_name == "Alice Smith"
    assert cognizer.external_id == "alice@example.com"
    assert cognizer.tenant_id == "default"


def test_for_group_with_tenant_id(rt):
    """for_group with explicit tenant_id registers successfully."""
    from starling._core import CognizerHub
    from starling.cognizer.builders import for_group

    hub = CognizerHub(rt.adapter)
    kwargs = for_group("team-alpha", tenant_id="acme", canonical_name="Team Alpha")
    assert kwargs["tenant_explicitly_set"] is True

    cognizer = hub.register_cognizer(**kwargs)
    assert cognizer.kind.name == "Group"
    assert cognizer.tenant_id == "acme"


def test_for_group_no_tenant_raises_typeerror():
    """for_group() without tenant_id raises TypeError at Python call site."""
    from starling.cognizer.builders import for_group

    with pytest.raises(TypeError):
        for_group("team-beta", canonical_name="Team Beta")  # missing tenant_id
