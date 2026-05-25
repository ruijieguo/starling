"""FOLLOWUP-2 [P1 receipt]: filters_applied must include holder_perspective.

Spec (docs/design/subsystems_design/13_retrieval.md:291):
    filters_applied: list[dict]
      P1 必填：holder/perspective/tenant/review/evidence erasure

basic_retrieve had been recording 9 entries (no perspective). This file
verifies the now-mandatory entry:
  - present in every receipt (recorded as "any" when caller leaves it unset)
  - records the bound value when the caller constrains perspective
  - SQL filter actually applies — a row with the wrong perspective is
    excluded from results
"""

from __future__ import annotations

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


@pytest.fixture
def adapter():
    return _core.SqliteAdapter.open(":memory:")


def _seed_engram(adapter) -> str:
    bus = BusFacade(adapter)
    inp = for_user_input(
        tenant_id="default",
        adapter_name="test_perspective_filter", adapter_version="1.0.0",
        source_item_id="seed-msg", source_version="1",
        payload_bytes=b"seed",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
    )
    out = bus.append_evidence(inp)
    assert out["kind"] == "accepted"
    return out["engram_ref"].id


def _seed_statement(adapter, engram_id: str, *, perspective: _core.Perspective,
                    object_hash: str) -> str:
    s = _core.ExtractedStatement()
    s.holder_id          = "alice"
    s.holder_tenant_id   = "default"
    s.holder_perspective = perspective
    s.subject_kind       = "cognizer"
    s.subject_id         = "bob"
    s.predicate          = "responsible_for"
    s.object_kind        = "str"
    s.object_value       = "auth"
    s.canonical_object_hash = object_hash
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = _core.Polarity.POS
    s.confidence         = 0.9
    s.observed_at        = "2026-04-14T09:00:00Z"
    s.source_hash        = "abc123"
    s.valid_from         = "2026-04-01T00:00:00Z"
    s.valid_to           = "2026-12-31T00:00:00Z"
    s.perceived_by       = ["alice"]
    out = _core.Bus(adapter).write(s, engram_id, "span-1", None)
    assert out["kind"] == "accepted", f"Bus.write must accept, got {out!r}"
    stmt_id = out["stmt_id"]
    assert mark_consolidated(adapter, stmt_id, "default") is True
    return stmt_id


def test_receipt_records_perspective_any_when_unconstrained(adapter):
    """No holder_perspective kwarg → receipt entry == 'any'."""
    engram_id = _seed_engram(adapter)
    _seed_statement(adapter, engram_id,
                    perspective=_core.Perspective.FIRST_PERSON,
                    object_hash="a" * 64)

    result = basic_retrieve(
        adapter,
        tenant_id="default", holder="alice",
        subject="bob", predicate="responsible_for",
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    filters = {f.name: f.value for f in result.receipt.filters_applied}
    assert "holder_perspective" in filters, \
        "filters_applied must include holder_perspective (13_retrieval.md:291)"
    assert filters["holder_perspective"] == "any"
    # Row is still returned — no SQL predicate added.
    assert len(result.rows) == 1


def test_receipt_records_bound_perspective_when_constrained(adapter):
    """holder_perspective=FIRST_PERSON → receipt records 'first_person'."""
    engram_id = _seed_engram(adapter)
    _seed_statement(adapter, engram_id,
                    perspective=_core.Perspective.FIRST_PERSON,
                    object_hash="b" * 64)

    result = basic_retrieve(
        adapter,
        tenant_id="default", holder="alice",
        holder_perspective="first_person",
        subject="bob", predicate="responsible_for",
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    filters = {f.name: f.value for f in result.receipt.filters_applied}
    assert filters["holder_perspective"] == "first_person"
    assert len(result.rows) == 1


def test_perspective_predicate_actually_filters(adapter):
    """Two rows, different perspectives — only the matching one returns.

    Without the SQL predicate added in FOLLOWUP-2, both rows would come
    back even though only one matches the requested perspective. The
    receipt would then misrepresent what was filtered.
    """
    engram_id = _seed_engram(adapter)
    _seed_statement(adapter, engram_id,
                    perspective=_core.Perspective.FIRST_PERSON,
                    object_hash="c" * 64)
    _seed_statement(adapter, engram_id,
                    perspective=_core.Perspective.INFERRED,
                    object_hash="d" * 64)

    # Request only FIRST_PERSON
    result = basic_retrieve(
        adapter,
        tenant_id="default", holder="alice",
        holder_perspective="first_person",
        subject="bob", predicate="responsible_for",
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    assert len(result.rows) == 1
    assert result.rows[0].holder_perspective == "first_person"

    # Unconstrained → both rows returned
    result_all = basic_retrieve(
        adapter,
        tenant_id="default", holder="alice",
        subject="bob", predicate="responsible_for",
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    perspectives = sorted(r.holder_perspective for r in result_all.rows)
    assert perspectives == ["first_person", "inferred"]
