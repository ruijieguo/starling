"""§15.3.2 retention: source_kind=system_internal -> NO_STORE.

RetrievalReceipt and PipelineRun traces are commonly re-fed into the system
during debugging or playback. The self-pollution guard ensures they cannot
silently become user-profile evidence. M0.3 owns the storage-layer half:
no engrams row, audit row only. M0.4/M0.6 own the inference-layer half.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from starling import runtime as rt_mod
from starling import testing as starling_testing  # NOLINT(starling-testing-isolation)
from starling._core import PrivacyClass, EngramRetentionMode
from starling.evidence import (
    for_system_internal, for_observer_agent, for_replay_output,
)


@pytest.fixture
def runtime(tmp_path):
    original = starling_testing.relax_preflight_for_m0_3()
    rt = rt_mod._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    yield rt
    rt_mod.LOCAL_STORE_REQUIRED = original


def _count(rt, table):
    conn = sqlite3.connect(str(rt.adapter.db_path))
    try:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _bus_event_rows(rt):
    conn = sqlite3.connect(str(rt.adapter.db_path))
    try:
        return conn.execute(
            "SELECT event_type, dispatch_status FROM bus_events ORDER BY outbox_sequence"
        ).fetchall()
    finally:
        conn.close()


def test_system_internal_payload_does_not_create_engram(runtime):
    inp = for_system_internal(
        tenant_id="t1",
        adapter_name="retrieval_planner",
        adapter_version="0.1.0",
        source_item_id="receipt-abc",
        source_version="1",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        payload_bytes=b"sufficiency_status=SUFFICIENT|trace=...",
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)

    assert outcome["kind"] == "no_store"
    assert outcome["audit_event_id"]
    assert _count(runtime, "engrams") == 0
    assert _bus_event_rows(runtime) == [("evidence.no_store_audit", "delivered")]


def test_observer_agent_payload_is_also_no_store(runtime):
    inp = for_observer_agent(
        tenant_id="t1",
        adapter_name="tom_observer",
        adapter_version="0.1.0",
        source_item_id="obs-1",
        source_version="1",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        payload_bytes=b"observed_event=...",
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)
    assert outcome["kind"] == "no_store"
    assert _count(runtime, "engrams") == 0


def test_replay_output_payload_is_also_no_store(runtime):
    inp = for_replay_output(
        tenant_id="t1",
        adapter_name="replay_scheduler",
        adapter_version="0.1.0",
        source_item_id="replay-1",
        source_version="1",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        payload_bytes=b"derived=...",
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)
    assert outcome["kind"] == "no_store"
    assert _count(runtime, "engrams") == 0
