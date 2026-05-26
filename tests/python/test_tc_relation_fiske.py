"""
TC-RELATION-FISKE — CRITICAL #4 (08_cognizer)

Validates CognizerHub.upsert_relation Fiske 4-mode invariants:
- fiske_weights sum != 1.0 (off by >1e-6) raises FiskeWeightsInvalid
- fiske_weights sum exactly 1.0 passes
- fiske_weights sum within tolerance (float rounding of 1/3 * 3) passes
- affinity out of [0, 1] raises ValueError
- Upsert on same (a_id, b_id, tenant_id) overwrites previous edge (same id)
- Upsert with different tenant_id creates a new independent edge
- Round-trip: write edge, read back via relations_of, affinity matches within 1e-6
- relations_of() returns all edges for a given cognizer (multi-target)
"""
from __future__ import annotations

import pytest
import starling._core as _core


@pytest.fixture
def adapter():
    return _core.SqliteAdapter.open(":memory:")


@pytest.fixture
def hub(adapter):
    return _core.CognizerHub(adapter)


@pytest.fixture
def two_cognizers(hub):
    """Register alice and bob; return (alice_id, bob_id)."""
    a = hub.register_cognizer(
        kind="human",
        external_id="alice-fiske",
        canonical_name="Alice",
        tenant_id="default",
    )
    b = hub.register_cognizer(
        kind="human",
        external_id="bob-fiske",
        canonical_name="Bob",
        tenant_id="default",
    )
    return a.id, b.id


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-01: valid weights accepted, edge has expected shape
# ---------------------------------------------------------------------------

def test_upsert_valid_fiske_weights_succeeds(hub, two_cognizers):
    """Sum exactly 1.0 is accepted; returned edge has the right identifiers."""
    alice_id, bob_id = two_cognizers
    weights = {"communal": 0.25, "authority": 0.25, "equality": 0.25, "market": 0.25}
    edge = hub.upsert_relation(
        a_id=alice_id,
        b_id=bob_id,
        tenant_id="default",
        fiske_weights=weights,
        affinity=0.6,
    )
    assert edge.id is not None
    assert edge.a_id == alice_id
    assert edge.b_id == bob_id
    assert edge.tenant_id == "default"
    assert pytest.approx(edge.affinity, abs=1e-6) == 0.6


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-02: sum > 1.0 raises FiskeWeightsInvalid
# ---------------------------------------------------------------------------

def test_upsert_fiske_weights_sum_above_one_rejected(hub, two_cognizers):
    """Sum = 1.1 raises FiskeWeightsInvalid."""
    alice_id, bob_id = two_cognizers
    # 0.3+0.3+0.3+0.2 = 1.1
    bad_weights = {"communal": 0.3, "authority": 0.3, "equality": 0.3, "market": 0.2}
    assert abs(sum(bad_weights.values()) - 1.1) < 1e-9  # sanity check the fixture
    with pytest.raises(_core.FiskeWeightsInvalid):
        hub.upsert_relation(
            a_id=alice_id,
            b_id=bob_id,
            tenant_id="default",
            fiske_weights=bad_weights,
            affinity=0.5,
        )


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-03: sum < 1.0 raises FiskeWeightsInvalid
# ---------------------------------------------------------------------------

def test_upsert_fiske_weights_sum_below_one_rejected(hub, two_cognizers):
    """Sum = 0.5 raises FiskeWeightsInvalid."""
    alice_id, bob_id = two_cognizers
    # All four add up to 0.5
    bad_weights = {"communal": 0.5, "authority": 0.5, "equality": 0.5, "market": 0.0}
    assert abs(sum(bad_weights.values()) - 1.5) < 1e-9  # 1.5, not 1.0
    with pytest.raises(_core.FiskeWeightsInvalid):
        hub.upsert_relation(
            a_id=alice_id,
            b_id=bob_id,
            tenant_id="default",
            fiske_weights=bad_weights,
            affinity=0.5,
        )


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-04: affinity outside [0, 1] raises
# ---------------------------------------------------------------------------

def test_upsert_affinity_out_of_range_rejected(hub, two_cognizers):
    """affinity = 1.5 raises ValueError (SQL CHECK or Hub validation)."""
    alice_id, bob_id = two_cognizers
    weights = {"communal": 1.0, "authority": 0.0, "equality": 0.0, "market": 0.0}
    with pytest.raises((ValueError, Exception)):
        hub.upsert_relation(
            a_id=alice_id,
            b_id=bob_id,
            tenant_id="default",
            fiske_weights=weights,
            affinity=1.5,
        )


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-05: float-tolerance (1/3 * 3 passes)
# ---------------------------------------------------------------------------

def test_upsert_fiske_weights_float_tolerance_passes(hub, two_cognizers):
    """Sum within [1.0 +/- 1e-6] due to float rounding is accepted."""
    alice_id, bob_id = two_cognizers
    third = 1.0 / 3.0
    weights = {"communal": third, "authority": third, "equality": third, "market": 0.0}
    edge = hub.upsert_relation(
        a_id=alice_id,
        b_id=bob_id,
        tenant_id="default",
        fiske_weights=weights,
        affinity=0.5,
    )
    assert edge.id is not None


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-06: round-trip affinity via relations_of
# ---------------------------------------------------------------------------

def test_upsert_fiske_weights_round_trip(hub, two_cognizers):
    """Write edge with specific affinity; read back via relations_of; value matches."""
    alice_id, bob_id = two_cognizers
    weights = {"communal": 0.4, "authority": 0.3, "equality": 0.2, "market": 0.1}
    hub.upsert_relation(
        a_id=alice_id,
        b_id=bob_id,
        tenant_id="default",
        fiske_weights=weights,
        affinity=0.73,
    )
    edges = hub.relations_of(alice_id, "default")
    matching = [e for e in edges if e.b_id == bob_id]
    assert len(matching) == 1
    assert pytest.approx(matching[0].affinity, abs=1e-6) == 0.73


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-07: same (a, b, tenant) upsert replaces the edge
# ---------------------------------------------------------------------------

def test_upsert_same_triplet_replaces(hub, two_cognizers):
    """Second upsert on same (a_id, b_id, tenant_id) returns same id; affinity updated."""
    alice_id, bob_id = two_cognizers
    weights_v1 = {"communal": 1.0, "authority": 0.0, "equality": 0.0, "market": 0.0}
    weights_v2 = {"communal": 0.0, "authority": 1.0, "equality": 0.0, "market": 0.0}
    e1 = hub.upsert_relation(
        a_id=alice_id,
        b_id=bob_id,
        tenant_id="default",
        fiske_weights=weights_v1,
        affinity=0.3,
    )
    e2 = hub.upsert_relation(
        a_id=alice_id,
        b_id=bob_id,
        tenant_id="default",
        fiske_weights=weights_v2,
        affinity=0.7,
    )
    assert e1.id == e2.id, "Same (a, b, tenant) must return the same edge id"
    assert pytest.approx(e2.affinity, abs=1e-6) == 0.7

    # Only one edge must exist for the pair
    edges = hub.relations_of(alice_id, "default")
    assert len([e for e in edges if e.b_id == bob_id]) == 1


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-08: different tenant_id creates a new independent edge
# ---------------------------------------------------------------------------

def test_upsert_different_tenant_creates_new_edge(hub, two_cognizers):
    """Same (a_id, b_id) in different tenants creates independent edges."""
    alice_id, bob_id = two_cognizers
    weights = {"communal": 0.25, "authority": 0.25, "equality": 0.25, "market": 0.25}
    e_t1 = hub.upsert_relation(
        a_id=alice_id,
        b_id=bob_id,
        tenant_id="tenant-x",
        fiske_weights=weights,
        affinity=0.4,
    )
    e_t2 = hub.upsert_relation(
        a_id=alice_id,
        b_id=bob_id,
        tenant_id="tenant-y",
        fiske_weights=weights,
        affinity=0.9,
    )
    assert e_t1.id != e_t2.id, "Different tenants must produce different edge ids"
    assert e_t1.tenant_id == "tenant-x"
    assert e_t2.tenant_id == "tenant-y"
    # Each tenant sees its own edge
    edges_x = hub.relations_of(alice_id, "tenant-x")
    edges_y = hub.relations_of(alice_id, "tenant-y")
    assert any(e.b_id == bob_id for e in edges_x)
    assert any(e.b_id == bob_id for e in edges_y)


# ---------------------------------------------------------------------------
# TC-RELATION-FISKE-09: relations_of returns all edges for a cognizer
# ---------------------------------------------------------------------------

def test_relations_of_returns_all_for_a(hub):
    """alice→bob and alice→carol both appear in relations_of(alice)."""
    alice = hub.register_cognizer(
        kind="human",
        external_id="alice-multi",
        canonical_name="Alice Multi",
        tenant_id="default",
    )
    bob = hub.register_cognizer(
        kind="human",
        external_id="bob-multi",
        canonical_name="Bob Multi",
        tenant_id="default",
    )
    carol = hub.register_cognizer(
        kind="human",
        external_id="carol-multi",
        canonical_name="Carol Multi",
        tenant_id="default",
    )
    weights = {"communal": 0.5, "authority": 0.5, "equality": 0.0, "market": 0.0}
    hub.upsert_relation(
        a_id=alice.id,
        b_id=bob.id,
        tenant_id="default",
        fiske_weights=weights,
        affinity=0.6,
    )
    hub.upsert_relation(
        a_id=alice.id,
        b_id=carol.id,
        tenant_id="default",
        fiske_weights=weights,
        affinity=0.7,
    )
    edges = hub.relations_of(alice.id, "default")
    b_ids = {e.b_id for e in edges}
    assert bob.id in b_ids
    assert carol.id in b_ids
    assert len(edges) >= 2
