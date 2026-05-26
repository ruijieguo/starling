"""Integration tests for apply_frontier_filter in basic_retrieve (P2.a).

Tests cover:
  - Default apply_frontier_filter=False: existing P1 behavior preserved even
    when no frontier records exist for the statement's evidence engram.
  - apply_frontier_filter=True with frontier set up: only visible rows returned.
  - Receipt has exactly 12 filters_applied entries.
  - Receipt.frontier_masked_count is correct.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from starling import _core
from starling.bus.append_evidence import BusFacade
from starling.evidence import (
    EngramRetentionMode,
    PrivacyClass,
    for_user_input,
)
from starling.retrieval import basic_retrieve
from starling.testing import mark_consolidated  # NOLINT(starling-testing-isolation)


AS_OF = datetime(2026, 5, 1, tzinfo=timezone.utc)
TENANT = "default"
HOLDER = "alice"
SUBJECT = "bob"
PREDICATE = "knows"

# Use an on-disk path so we can open a stdlib sqlite3 connection alongside the
# C++ adapter for direct-insert helpers.


@pytest.fixture
def db_pair(tmp_path):
    """Return (adapter, raw_conn) pointing to the same on-disk db."""
    db_path = str(tmp_path / "frontier_integ.db")
    adapter = _core.SqliteAdapter.open(db_path)
    raw = sqlite3.connect(db_path)
    yield adapter, raw
    raw.close()


def _append_engram(adapter, raw: sqlite3.Connection, *,
                   tenant_id: str = TENANT,
                   idx: int = 0) -> str:
    bus = BusFacade(adapter)
    inp = for_user_input(
        tenant_id=tenant_id,
        adapter_name="test_frontier_integration",
        adapter_version="1.0.0",
        source_item_id=f"src-ff-{idx}",
        source_version="1",
        payload_bytes=f"frontier integration test payload {idx}".encode(),
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    out = bus.append_evidence(inp)
    assert out["kind"] in ("accepted", "idempotent"), f"engram seed failed: {out!r}"
    return out["engram_ref"].id


def _write_statement(adapter, engram_id: str, *,
                     tenant_id: str = TENANT,
                     obj_value: str = "testval") -> str:
    """Seed a consolidated statement directly via SQL.

    NOTE: we deliberately bypass Bus.write here. Bus.write would tick the
    BeliefTracker subscriber, which auto-records explicit_told + presence_log
    for every cognizer in perceived_by. That side effect would pre-populate
    the holder's frontier with ALL engrams used in the test, defeating the
    point of the apply_frontier_filter assertion.

    Direct SQL leaves cognizer_presence_log + cognizer_frontier_facts empty
    until the test explicitly inserts the rows it wants.
    """
    import sqlite3
    import uuid as _uuid

    db_path = adapter.db_path
    stmt_id = str(_uuid.uuid4())
    obj_hash = format(hash(obj_value) & ((1 << 256) - 1), '064x')
    now_iso = "2026-04-14T09:00:00Z"
    evidence_json = (
        '[{"engram_ref":"' + engram_id +
        '","content_hash":"' + ('0' * 64) +
        '","status":"active"}]'
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO statements ("
            "  id, tenant_id, holder_id, holder_perspective,"
            "  subject_kind, subject_id, predicate,"
            "  object_kind, object_value, canonical_object_hash,"
            "  canonical_object_hash_version,"
            "  modality, polarity, confidence,"
            "  observed_at, salience, affect_json, activation,"
            "  last_accessed, provenance, evidence_json,"
            "  source_spans_json, derived_from_json, derived_depth,"
            "  perceived_by_json, access_count, replay_count,"
            "  consolidation_state, review_status, nesting_depth,"
            "  visibility_json, created_at, updated_at"
            ") VALUES ("
            "  ?, ?, ?, ?,"
            "  ?, ?, ?,"
            "  ?, ?, ?,"
            "  'v1',"
            "  ?, ?, ?,"
            "  ?, 0.5, '{}', 0.5,"
            "  ?, 'observed', ?,"
            "  '[]', '[]', 0,"
            "  ?, 0, 0,"
            "  'consolidated', 'approved', 0,"
            "  '[]', ?, ?"
            ")",
            (
                stmt_id, tenant_id, HOLDER, "first_person",
                "cognizer", SUBJECT, PREDICATE,
                "str", obj_value, obj_hash,
                "believes", "pos", 0.9,
                now_iso, now_iso, evidence_json,
                '["' + HOLDER + '"]', now_iso, now_iso,
            )
        )
        conn.commit()
    return stmt_id


def _insert_presence(raw: sqlite3.Connection, *,
                     pres_id: str, tenant: str, cognizer: str,
                     engram: str, observed_at: str) -> None:
    raw.execute(
        "INSERT INTO cognizer_presence_log "
        "(id, tenant_id, cognizer_id, engram_id, observed_at, channel) "
        "VALUES (?, ?, ?, ?, ?, 'default')",
        (pres_id, tenant, cognizer, engram, observed_at),
    )
    raw.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_default_false_preserves_p1_behavior(db_pair):
    """apply_frontier_filter=False (default) returns row even with no frontier records."""
    adapter, raw = db_pair
    engram_id = _append_engram(adapter, raw, idx=0)
    _write_statement(adapter, engram_id)

    result = basic_retrieve(
        adapter,
        tenant_id=TENANT,
        holder=HOLDER,
        subject=SUBJECT,
        predicate=PREDICATE,
        as_of=AS_OF,
        # apply_frontier_filter not passed => defaults to False
    )
    assert len(result.rows) == 1, "row should be visible without frontier filter"
    assert result.receipt.sufficiency_status == "SUFFICIENT"
    assert result.receipt.frontier_masked_count == 0


def test_frontier_filter_returns_visible_only(db_pair):
    """apply_frontier_filter=True: only rows with visible engrams returned."""
    adapter, raw = db_pair

    # Append two distinct engrams.
    vis_engram = _append_engram(adapter, raw, idx=0)
    hid_engram = _append_engram(adapter, raw, idx=1)

    _write_statement(adapter, vis_engram, obj_value="visible")
    _write_statement(adapter, hid_engram, obj_value="hidden")

    # Record presence for vis_engram only.
    _insert_presence(raw, pres_id="p1", tenant=TENANT,
                     cognizer=HOLDER, engram=vis_engram,
                     observed_at="2026-04-01T00:00:00Z")

    result = basic_retrieve(
        adapter,
        tenant_id=TENANT,
        holder=HOLDER,
        subject=SUBJECT,
        predicate=PREDICATE,
        as_of=AS_OF,
        apply_frontier_filter=True,
    )
    assert len(result.rows) == 1
    assert result.rows[0].object_value == "visible"
    assert result.receipt.frontier_masked_count == 1


def test_receipt_has_12_filters_applied(db_pair):
    """filters_applied always has 12 entries in P2.a (10 P1 + 2 frontier)."""
    adapter, raw = db_pair
    engram_id = _append_engram(adapter, raw, idx=0)
    _write_statement(adapter, engram_id)

    result = basic_retrieve(
        adapter,
        tenant_id=TENANT,
        holder=HOLDER,
        subject=SUBJECT,
        predicate=PREDICATE,
        as_of=AS_OF,
    )
    names = [f.name for f in result.receipt.filters_applied]
    assert len(result.receipt.filters_applied) == 12, (
        f"expected 12 filters_applied entries, got {len(result.receipt.filters_applied)}: "
        f"{names}"
    )
    assert "frontier_applied" in names
    assert "frontier_masked_count" in names


def test_frontier_masked_count_correct(db_pair):
    """frontier_masked_count counts rows filtered out by the frontier EXISTS."""
    adapter, raw = db_pair

    e1 = _append_engram(adapter, raw, idx=0)
    e2 = _append_engram(adapter, raw, idx=1)
    e3 = _append_engram(adapter, raw, idx=2)

    _write_statement(adapter, e1, obj_value="v1")
    _write_statement(adapter, e2, obj_value="v2")
    _write_statement(adapter, e3, obj_value="v3")

    # Only e1 is visible.
    _insert_presence(raw, pres_id="p-e1", tenant=TENANT,
                     cognizer=HOLDER, engram=e1,
                     observed_at="2026-04-01T00:00:00Z")

    result = basic_retrieve(
        adapter,
        tenant_id=TENANT,
        holder=HOLDER,
        subject=SUBJECT,
        predicate=PREDICATE,
        as_of=AS_OF,
        apply_frontier_filter=True,
    )
    assert len(result.rows) == 1
    assert result.receipt.frontier_masked_count == 2

    # filters_applied entry should match.
    filters = {f.name: f.value for f in result.receipt.filters_applied}
    assert filters["frontier_masked_count"] == "2"
    assert filters["frontier_applied"] == "true"
