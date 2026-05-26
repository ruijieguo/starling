"""
TC-COG-REGISTER — CRITICAL #1 (08_cognizer)

Validates:
- UUID5 idempotency: register same (kind, external_id) twice -> same id
- UUID5 format: matches RFC 4122 version-5 pattern
- last_seen_at refresh on re-register
- Different kind -> different id
- Different external_id -> different id
- Round-trip fetch via get()
- lookup_by_alias
- Case-insensitive alias lookup
- Tenant isolation (alias scoping and per-tenant records)
"""
from __future__ import annotations

import re
import time

import pytest

import starling._core as _core


UUID5_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


@pytest.fixture
def adapter():
    return _core.SqliteAdapter.open(":memory:")


@pytest.fixture
def hub(adapter):
    return _core.CognizerHub(adapter)


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-01: UUID5 idempotency
# ---------------------------------------------------------------------------

def test_uuid5_idempotency(hub):
    """Registering same (kind, external_id) twice returns the same UUID5 id."""
    c1 = hub.register_cognizer(
        kind="human",
        external_id="alice@example.com",
        canonical_name="Alice",
        tenant_id="default",
    )
    c2 = hub.register_cognizer(
        kind="human",
        external_id="alice@example.com",
        canonical_name="Alice Updated",
        tenant_id="default",
    )
    assert c1.id == c2.id, "UUID5 must be deterministic for same (kind, external_id)"


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-02: UUID5 format
# ---------------------------------------------------------------------------

def test_uuid5_format(hub):
    """Registered id must be a valid RFC 4122 version-5 UUID."""
    c = hub.register_cognizer(
        kind="human",
        external_id="bob@example.com",
        canonical_name="Bob",
        tenant_id="default",
    )
    assert UUID5_RE.match(c.id), f"Not a UUID5: {c.id!r}"


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-03: last_seen_at refresh on re-register
# ---------------------------------------------------------------------------

def test_last_seen_at_refresh(hub):
    """Re-registering with a later timestamp refreshes last_seen_at."""
    c1 = hub.register_cognizer(
        kind="human",
        external_id="carol@example.com",
        canonical_name="Carol",
        tenant_id="default",
    )
    t1 = c1.last_seen_at
    # Sleep 1.1 s so the wall-clock timestamp advances (granularity is 1 s)
    time.sleep(1.1)
    c2 = hub.register_cognizer(
        kind="human",
        external_id="carol@example.com",
        canonical_name="Carol",
        tenant_id="default",
    )
    assert c2.last_seen_at >= t1, (
        f"last_seen_at must be refreshed on re-register: {t1!r} -> {c2.last_seen_at!r}"
    )


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-04: Different kind -> different id
# ---------------------------------------------------------------------------

def test_different_kind_different_id(hub):
    """Same external_id but different kind -> different UUID5."""
    c_human = hub.register_cognizer(
        kind="human",
        external_id="dave@example.com",
        canonical_name="Dave Human",
        tenant_id="default",
    )
    c_agent = hub.register_cognizer(
        kind="agent",
        external_id="dave@example.com",
        canonical_name="Dave Agent",
        tenant_id="default",
    )
    assert c_human.id != c_agent.id


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-05: Different external_id -> different id
# ---------------------------------------------------------------------------

def test_different_external_id_different_id(hub):
    """Different external_id -> different UUID5."""
    c1 = hub.register_cognizer(
        kind="human",
        external_id="user-001",
        canonical_name="User One",
        tenant_id="default",
    )
    c2 = hub.register_cognizer(
        kind="human",
        external_id="user-002",
        canonical_name="User Two",
        tenant_id="default",
    )
    assert c1.id != c2.id


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-06: Round-trip get()
# ---------------------------------------------------------------------------

def test_round_trip_get(hub):
    """Registered cognizer can be fetched back via get()."""
    c = hub.register_cognizer(
        kind="human",
        external_id="eve@example.com",
        canonical_name="Eve",
        tenant_id="default",
    )
    fetched = hub.get(c.id, "default")
    assert fetched is not None
    assert fetched.id == c.id
    assert fetched.external_id == "eve@example.com"
    assert fetched.canonical_name == "Eve"


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-07: lookup_by_alias returns id
# ---------------------------------------------------------------------------

def test_lookup_by_alias(hub):
    """Register with alias; lookup_by_alias returns the cognizer id."""
    c = hub.register_cognizer(
        kind="human",
        external_id="frank@example.com",
        canonical_name="Frank",
        tenant_id="default",
        aliases=["Frankie"],
    )
    result_id = hub.lookup_by_alias("default", "Frankie")
    assert result_id == c.id


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-08: Case-insensitive alias lookup
# ---------------------------------------------------------------------------

def test_lookup_by_alias_case_insensitive(hub):
    """Alias lookup is case-insensitive (ASCII fold via normalize_alias)."""
    c = hub.register_cognizer(
        kind="human",
        external_id="grace@example.com",
        canonical_name="Grace",
        tenant_id="default",
        aliases=["GRACE"],
    )
    result_id = hub.lookup_by_alias("default", "grace")
    assert result_id == c.id


# ---------------------------------------------------------------------------
# TC-COG-REGISTER-09: Tenant isolation
# ---------------------------------------------------------------------------

def test_tenant_isolation(hub):
    """
    Same (kind, external_id) in different tenants are stored as separate
    tenant-scoped records.  UUID5 is computed from kind+external_id (no
    tenant), so the ids are equal — but each record is independently
    retrievable by its own tenant_id, and alias lookups are tenant-scoped.
    """
    c_t1 = hub.register_cognizer(
        kind="human",
        external_id="shared@example.com",
        canonical_name="Shared T1",
        tenant_id="tenant-1",
    )
    c_t2 = hub.register_cognizer(
        kind="human",
        external_id="shared@example.com",
        canonical_name="Shared T2",
        tenant_id="tenant-2",
    )

    # Each record carries its own tenant_id
    assert c_t1.tenant_id == "tenant-1"
    assert c_t2.tenant_id == "tenant-2"

    # get() with the correct tenant returns the record
    fetched_t1 = hub.get(c_t1.id, "tenant-1")
    fetched_t2 = hub.get(c_t2.id, "tenant-2")
    assert fetched_t1 is not None
    assert fetched_t2 is not None
    assert fetched_t1.tenant_id == "tenant-1"
    assert fetched_t2.tenant_id == "tenant-2"

    # Alias registered in tenant-1 must not be visible in tenant-2
    hub.register_cognizer(
        kind="human",
        external_id="shared@example.com",
        canonical_name="Shared T1",
        tenant_id="tenant-1",
        aliases=["shared-alias"],
    )
    assert hub.lookup_by_alias("tenant-2", "shared-alias") is None
    assert hub.lookup_by_alias("tenant-1", "shared-alias") == c_t1.id
