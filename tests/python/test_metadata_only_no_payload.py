"""FOLLOWUP-1 [P1 privacy]: STORE_METADATA_ONLY must not write payload_inline.

Spec (docs/design/system_design.md:1090):
    STORE_METADATA_ONLY    -- 写 metadata，不写 verbatim

Verifies that when IngestPolicyResolver downgrades a write to
STORE_METADATA_ONLY (e.g. tool_observation), EngramStore::put records
the row's metadata but leaves payload_inline NULL — no encrypted
verbatim bytes leaked into storage.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from starling import _core, runtime
from starling.bus.append_evidence import BusFacade
from starling.evidence import (
    for_tool_observation,
    PrivacyClass,
    EngramRetentionMode,
)
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def test_tool_observation_metadata_only_no_payload_inline(rt):
    bus = BusFacade(rt.adapter)
    inp = for_tool_observation(
        tenant_id="default",
        adapter_name="search_tool", adapter_version="1.0.0",
        source_item_id="obs-1", source_version="1",
        payload_bytes=b"raw search-result text that must NOT land in payload_inline",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 26, 9, 0, tzinfo=timezone.utc),
    )
    outcome = bus.append_evidence(inp)
    assert outcome["kind"] == "accepted"
    engram_id = outcome["engram_ref"].id

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        row = conn.execute(
            "SELECT ingest_policy, ingest_mode, payload_inline, content_hash "
            "FROM engrams WHERE id = ?",
            (engram_id,),
        ).fetchone()

    assert row is not None
    policy, mode, payload, content_hash = row
    assert policy == "store_metadata_only", \
        f"resolver should downgrade tool_observation to store_metadata_only; got {policy!r}"
    assert mode == "metadata_only"
    assert payload is None, (
        f"payload_inline must be NULL when ingest_policy=store_metadata_only; "
        f"got {len(payload) if payload else 0} bytes — privacy violation"
    )
    assert content_hash, "content_hash must still be populated for dedup/idempotency"
