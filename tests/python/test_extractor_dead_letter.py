"""Adapter ok=false on every retry → ExtractionRunResult.status='failed' →
pipeline.run_failed event."""
from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime


@pytest.fixture
def rt(tmp_path):
    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    rt.start()
    yield rt


def test_failed_run(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute(
            "INSERT INTO engrams("
            "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
            "  privacy_class,retention_mode,refcount,payload_inline,created_at"
            ") VALUES('engram-1','default','hash-1','user_input','store',"
            "'whole_record','internal','audit_retain',0,X'','2026-05-23T10:00:00Z')")
        conn.commit()

    llm = _core.FakeLLMAdapter()  # no response set → all calls return ok=false
    extractor = _core.Extractor(rt.adapter.connection(), llm)
    r = extractor.run("engram-1", b"\x01\x02\x03", "cog-self", "default", {})

    assert r.status == "failed"
    assert len(r.accepted_statement_ids) == 0

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        n_attempts = conn.execute(
            "SELECT COUNT(*) FROM extraction_attempt WHERE status='failed'"
        ).fetchone()[0]
        n_run_failed = conn.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='pipeline.run_failed'"
        ).fetchone()[0]

    assert n_attempts == 3, f"expected 3 failed attempts, got {n_attempts}"
    assert n_run_failed == 1
