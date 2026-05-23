"""M0.3 milestone acceptance smoke. Confirms the four outcomes of
Bus.append_evidence work end-to-end against a real on-disk SQLite DB."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from starling import runtime as rt_mod
from starling import testing as starling_testing  # NOLINT(starling-testing-isolation)
from starling._core import PrivacyClass, EngramRetentionMode
from starling.evidence import for_user_input, for_system_internal


@pytest.fixture
def runtime(tmp_path):
    original = starling_testing.relax_preflight_for_m0_3()
    rt = rt_mod._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    yield rt
    rt_mod.LOCAL_STORE_REQUIRED = original


def _user_input(idx: int):
    return for_user_input(
        tenant_id="t1", adapter_name="direct_api", adapter_version="1.0.0",
        source_item_id=f"msg-{idx}", source_version="1",
        payload_bytes=f"hello-{idx}".encode(),
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )


def _conn(rt):
    return sqlite3.connect(str(rt.adapter.db_path))


def test_store_path_writes_engram_and_pending_event(runtime):
    outcome = runtime.bus.append_evidence(_user_input(1))
    assert outcome["kind"] == "accepted"
    assert outcome["engram_ref"].id
    assert outcome["event_id"]
    assert outcome["outbox_sequence"] >= 1

    conn = _conn(runtime)
    try:
        n_engrams = conn.execute("SELECT count(*) FROM engrams").fetchone()[0]
        assert n_engrams == 1
        row = conn.execute(
            "SELECT event_type, dispatch_status FROM bus_events"
        ).fetchone()
        assert row == ("evidence.appended", "pending")
    finally:
        conn.close()


def test_no_store_path_writes_audit_only(runtime):
    inp = for_system_internal(
        tenant_id="t1", adapter_name="x", adapter_version="1",
        source_item_id="s-1", source_version="1",
        payload_bytes=b"trace",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)
    assert outcome["kind"] == "no_store"
    conn = _conn(runtime)
    try:
        assert conn.execute("SELECT count(*) FROM engrams").fetchone()[0] == 0
    finally:
        conn.close()


def test_idempotent_repeat_returns_existing_ref(runtime):
    o1 = runtime.bus.append_evidence(_user_input(1))
    o2 = runtime.bus.append_evidence(_user_input(1))
    assert o1["kind"] == "accepted"
    assert o2["kind"] == "idempotent"
    assert o2["engram_ref"].id == o1["engram_ref"].id

    conn = _conn(runtime)
    try:
        assert conn.execute("SELECT count(*) FROM engrams").fetchone()[0] == 1
        types = [r[0] for r in conn.execute(
            "SELECT event_type FROM bus_events ORDER BY outbox_sequence"
        ).fetchall()]
        assert types == ["evidence.appended", "evidence.idempotent_hit"]
    finally:
        conn.close()


def test_rejected_path_leaves_both_tables_empty(runtime):
    bad = _user_input(1)
    bad.tenant_id = ""
    outcome = runtime.bus.append_evidence(bad)
    assert outcome["kind"] == "rejected"
    assert outcome["reason"] == "required_field_missing:tenant_id"
    conn = _conn(runtime)
    try:
        assert conn.execute("SELECT count(*) FROM engrams").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM bus_events").fetchone()[0] == 0
    finally:
        conn.close()


def test_pending_evidence_event_payload_carries_engram_id(runtime):
    outcome = runtime.bus.append_evidence(_user_input(1))
    conn = _conn(runtime)
    try:
        payload = conn.execute(
            "SELECT payload_json FROM bus_events WHERE event_type='evidence.appended'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert outcome["engram_ref"].id in payload
    assert outcome["engram_ref"].content_hash in payload
