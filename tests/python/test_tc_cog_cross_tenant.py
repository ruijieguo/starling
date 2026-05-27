"""
TC-COG-CROSS-TENANT — CRITICAL #3 (08_cognizer)

Validates:
- kind=group with implicit 'default' tenant raises GroupTenantImplicit
- kind=group with explicit non-default tenant_id succeeds
- for_group() builder always sets tenant_explicitly_set=True
- Non-group kinds allow tenant_id='default' (implicit)
- group with tenant_explicitly_set=True and the string 'default' does not raise
- Multi-tenant: same group external_id in different tenants stored independently
"""
from __future__ import annotations

import pytest
import starling._core as _core
from starling.cognizer.builders import for_group


@pytest.fixture
def adapter():
    return _core.SqliteAdapter.open(":memory:")


@pytest.fixture
def hub(adapter):
    return _core.CognizerHub(adapter)


# ---------------------------------------------------------------------------
# TC-COG-CROSS-TENANT-01: implicit default tenant for group raises
# ---------------------------------------------------------------------------

def test_group_without_explicit_tenant_raises(hub):
    """kind=group + default tenant without explicit flag -> GroupTenantImplicit."""
    with pytest.raises(_core.GroupTenantImplicit):
        hub.register_cognizer(
            kind="group",
            external_id="team-alpha",
            canonical_name="Team Alpha",
            tenant_id="default",
            tenant_explicitly_set=False,
        )


# ---------------------------------------------------------------------------
# TC-COG-CROSS-TENANT-02: explicit non-default tenant for group succeeds
# ---------------------------------------------------------------------------

def test_group_with_explicit_tenant_succeeds(hub):
    """kind=group + explicit non-default tenant -> succeeds."""
    c = hub.register_cognizer(
        kind="group",
        external_id="team-alpha",
        canonical_name="Team Alpha",
        tenant_id="acme-corp",
        tenant_explicitly_set=True,
    )
    assert c.id is not None
    assert c.tenant_id == "acme-corp"
    assert str(c.kind) in ("group", "CognizerKind.Group")


# ---------------------------------------------------------------------------
# TC-COG-CROSS-TENANT-03: for_group() builder always sets tenant_explicitly_set
# ---------------------------------------------------------------------------

def test_for_group_builder_always_explicit(hub):
    """for_group() builder sets tenant_explicitly_set=True, preventing the error."""
    kwargs = for_group(
        "team-beta",
        canonical_name="Team Beta",
        tenant_id="acme-corp",
    )
    assert kwargs["tenant_explicitly_set"] is True
    c = hub.register_cognizer(**kwargs)
    assert c.id is not None
    assert c.tenant_id == "acme-corp"


# ---------------------------------------------------------------------------
# TC-COG-CROSS-TENANT-04: non-group kinds allow implicit default tenant
# ---------------------------------------------------------------------------

def test_non_group_allows_default_tenant(hub):
    """Non-group kinds (human, agent, role, external) allow implicit default."""
    for kind in ("human", "agent", "role", "external"):
        c = hub.register_cognizer(
            kind=kind,
            external_id=f"user-{kind}",
            canonical_name=f"Test {kind.capitalize()}",
            tenant_id="default",
            tenant_explicitly_set=False,
        )
        assert c.id is not None


# ---------------------------------------------------------------------------
# TC-COG-CROSS-TENANT-05: group with explicit default string does not raise
# ---------------------------------------------------------------------------

def test_group_explicit_default_string_does_not_raise(hub):
    """Group with tenant_explicitly_set=True and tenant_id='default' is allowed.

    The intent is: user explicitly chose 'default' as their tenant name.
    Only the implicit/silent default is rejected.
    """
    c = hub.register_cognizer(
        kind="group",
        external_id="team-gamma",
        canonical_name="Team Gamma",
        tenant_id="default",
        tenant_explicitly_set=True,
    )
    assert c.id is not None
    assert c.tenant_id == "default"


# ---------------------------------------------------------------------------
# TC-COG-CROSS-TENANT-06: multi-tenant group isolation
# ---------------------------------------------------------------------------

def test_multi_tenant_group_isolation(hub):
    """Same group external_id in two tenants -> stored independently per tenant.

    UUID5 is computed from (kind, external_id) — not tenant — so c1.id == c2.id.
    Each tenant record is independently retrievable by its own tenant_id.
    A completely absent tenant returns None.
    """
    c1 = hub.register_cognizer(
        kind="group",
        external_id="shared-group",
        canonical_name="Shared Group T1",
        tenant_id="tenant-a",
        tenant_explicitly_set=True,
    )
    c2 = hub.register_cognizer(
        kind="group",
        external_id="shared-group",
        canonical_name="Shared Group T2",
        tenant_id="tenant-b",
        tenant_explicitly_set=True,
    )
    # Each tenant can retrieve its own record
    r_a = hub.get(c1.id, "tenant-a")
    r_b = hub.get(c2.id, "tenant-b")
    assert r_a is not None
    assert r_b is not None
    assert r_a.tenant_id == "tenant-a"
    assert r_b.tenant_id == "tenant-b"
    # A tenant that never registered this group sees None
    assert hub.get(c1.id, "tenant-never-registered") is None
