"""§15.3.2 'idempotent write': re-extracting the same Engram does not
produce a duplicate Statement."""
from __future__ import annotations

import sqlite3
import textwrap

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3
import pytest


XML_OK = textwrap.dedent("""
    <extraction>
      <statement>
        <holder ref="cog-self"/>
        <perspective>first_person</perspective>
        <subject kind="cognizer" id="cog-self"/>
        <predicate>responsible_for</predicate>
        <object kind="str" canonical_hash="hash-auth">auth</object>
        <modality>believes</modality>
        <polarity>pos</polarity>
        <confidence>0.85</confidence>
        <observed_at>2026-05-23T10:00:00Z</observed_at>
        <perceived_by ref="cog-self"/>
      </statement>
    </extraction>
""").strip()


@pytest.fixture
def rt(tmp_path, monkeypatch):
    original = relax_preflight_for_m0_3()
    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    rt.start()
    yield rt
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", original)


def _seed_engram(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute(
            "INSERT INTO engrams("
            "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
            "  privacy_class,retention_mode,refcount,payload_inline,created_at"
            ") VALUES('engram-1','default','hash-1','user_input','store',"
            "'whole_record','internal','audit_retain',0,X'','2026-05-23T10:00:00Z')")
        conn.commit()


def test_idempotent_rerun(rt):
    _seed_engram(rt)
    llm = _core.FakeLLMAdapter()
    extractor = _core.Extractor(rt.adapter.connection(), llm)
    body = _core.Extractor.build_prompt_body("cog-self", b"\x01\x02\x03", {})
    h = _core.Extractor.compute_prompt_input_hash(body)
    llm.set_response(h, raw_xml=XML_OK, ok=True)

    r1 = extractor.run("engram-1", b"\x01\x02\x03", "cog-self", "default", {})
    assert r1.status == "success"
    assert len(r1.accepted_statement_ids) == 1

    r2 = extractor.run("engram-1", b"\x01\x02\x03", "cog-self", "default", {})
    # The second run still creates its own PipelineRun, but the extractor
    # detects extraction_span_key already succeeded and emits an extraction.noop.
    assert r2.status == "success"
    assert len(r2.accepted_statement_ids) == 0

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        n_stmt = conn.execute("SELECT COUNT(*) FROM statements").fetchone()[0]
        n_noop = conn.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='extraction.noop'"
        ).fetchone()[0]
        n_runs = conn.execute("SELECT COUNT(*) FROM pipeline_run").fetchone()[0]

    assert n_stmt == 1, f"expected 1 statement after idempotent rerun, got {n_stmt}"
    assert n_noop >= 1, f"expected at least 1 extraction.noop event, got {n_noop}"
    assert n_runs == 2, f"expected 2 pipeline_run rows, got {n_runs}"
