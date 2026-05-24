"""TC-NEG-CROSSTENANT [CRITICAL] — system_design.md §15.3.1.

Cross-tenant derived_from is rejected by Validator unless an explicit
protocol_id is present in provenance metadata, in which case the
derived Statement is admitted with review_status=REVIEW_REQUESTED.

Pattern mirrors test_tc_new_conflict_severe.py:
  - _core.ExtractedStatement() DTO constructed directly (no rt.extracted_statement factory)
  - _core.Bus(rt.adapter).write(...) for statement writes
  - out["stmt_id"] for the returned statement id
  - rt.adapter.db_path for second-connection SQL assertions

The plan's `rt.extracted_statement(...)` and `rt.bus.write(...)` calls are
adapted here to match the established codebase pattern.
"""

from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3  # NOLINT(starling-testing-isolation)
from starling.evidence import (
    EngramRetentionMode,
    PrivacyClass,
    for_user_input,
)
from starling.bus.append_evidence import BusFacade

from datetime import datetime, timezone


@pytest.fixture
def rt(tmp_path, monkeypatch):
    """File-backed Runtime with M0.3 preflight relaxed for tests."""
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_engram(adapter, *, tenant_id: str, source_item_id: str) -> str:
    """Append a user_input engram and return its id."""
    bus = BusFacade(adapter)
    inp = for_user_input(
        tenant_id=tenant_id,
        adapter_name="test_tc_neg_crosstenant",
        adapter_version="1.0.0",
        source_item_id=source_item_id,
        source_version="1",
        payload_bytes=source_item_id.encode(),
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc),
    )
    outcome = bus.append_evidence(inp)
    assert outcome["kind"] == "accepted", \
        f"engram seed must succeed, got {outcome!r}"
    return outcome["engram_ref"].id


def _make_statement(
    *,
    holder_id: str,
    tenant_id: str,
    subject_id: str,
    derived_from: list[str] | None = None,
    provenance_protocol_id: str = "",
) -> "_core.ExtractedStatement":
    """Build an ExtractedStatement DTO via the C++ binding."""
    s = _core.ExtractedStatement()
    s.holder_id          = holder_id
    s.holder_tenant_id   = tenant_id
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind       = "cognizer"
    s.subject_id         = subject_id
    s.predicate          = "knows"
    s.object_kind        = "str"
    s.object_value       = "calculus"
    s.canonical_object_hash = "deadbeef01234567deadbeef01234567" \
                              "deadbeef01234567deadbeef01234567"
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = _core.Polarity.POS
    s.confidence         = 0.9
    s.observed_at        = "2026-05-24T09:00:00Z"
    s.source_hash        = "abc123"
    s.perceived_by       = [holder_id]
    if derived_from is not None:
        s.derived_from = derived_from
    if provenance_protocol_id:
        s.provenance_protocol_id = provenance_protocol_id
    return s


def _seed_parent(rt, *, tenant: str, holder: str, stmt_id_hint: str) -> str:
    """Seed a parent statement in the given tenant and return its id."""
    engram_id = _seed_engram(rt.adapter, tenant_id=tenant,
                             source_item_id=f"parent-{stmt_id_hint}")
    bus = _core.Bus(rt.adapter)
    stmt = _make_statement(
        holder_id=holder,
        tenant_id=tenant,
        subject_id="bob",
    )
    out = bus.write(stmt, engram_id, f"span-parent-{stmt_id_hint}", None)
    assert out["kind"] == "accepted", \
        f"parent statement write must succeed, got {out!r}"
    return out["stmt_id"]


def test_cross_tenant_derived_from_rejected(rt):
    """Cross-tenant derivation without protocol_id must raise with 'cross_tenant_derivation'."""
    parent_id = _seed_parent(rt, tenant="t1", holder="alice",
                             stmt_id_hint="parent")

    child_engram_id = _seed_engram(rt.adapter, tenant_id="t2",
                                   source_item_id="child-engram")
    child = _make_statement(
        holder_id="charlie",
        tenant_id="t2",
        subject_id="dan",
        derived_from=[parent_id],
    )
    bus = _core.Bus(rt.adapter)

    with pytest.raises(Exception) as exc_info:
        bus.write(child, child_engram_id, "span-child", None)

    err = str(exc_info.value).lower()
    assert "cross_tenant_derivation" in err or "derived_tenant_mismatch" in err, \
        f"Expected cross_tenant_derivation error, got: {exc_info.value!r}"


def test_cross_tenant_with_protocol_id_marks_review_requested(rt):
    """Cross-tenant derivation WITH protocol_id must be admitted with REVIEW_REQUESTED."""
    parent_id = _seed_parent(rt, tenant="t1", holder="alice",
                             stmt_id_hint="parent2")

    child_engram_id = _seed_engram(rt.adapter, tenant_id="t2",
                                   source_item_id="child-engram2")
    child = _make_statement(
        holder_id="charlie",
        tenant_id="t2",
        subject_id="dan",
        derived_from=[parent_id],
        provenance_protocol_id="cross-tenant-protocol-v1",
    )
    bus = _core.Bus(rt.adapter)

    out = bus.write(child, child_engram_id, "span-child2", None)
    assert out["kind"] == "accepted", \
        f"write with protocol_id must be accepted, got {out!r}"
    child_id = out["stmt_id"]

    conn = sqlite3.connect(str(rt.adapter.db_path))
    row = conn.execute(
        "SELECT review_status FROM statements WHERE id = ?",
        (child_id,)
    ).fetchone()
    conn.close()
    assert row is not None, "statement row must exist"
    assert row[0] == "review_requested", \
        f"review_status must be REVIEW_REQUESTED, got {row[0]!r}"
