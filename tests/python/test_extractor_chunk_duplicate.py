"""§15.3.2 'chunk-level idempotency': two Statements with the same
(predicate, canonical_object) inside the same chunk → first APPROVED,
second REVIEW_REQUESTED."""
from __future__ import annotations

import sqlite3
import textwrap

import pytest

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


XML_TWO_DUPS = textwrap.dedent("""
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
      <statement>
        <holder ref="cog-self"/>
        <perspective>first_person</perspective>
        <subject kind="cognizer" id="cog-self"/>
        <predicate>responsible_for</predicate>
        <object kind="str" canonical_hash="hash-auth">auth</object>
        <modality>believes</modality>
        <polarity>pos</polarity>
        <confidence>0.80</confidence>
        <observed_at>2026-05-23T10:00:01Z</observed_at>
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


def test_chunk_duplicate(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute(
            "INSERT INTO engrams("
            "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
            "  privacy_class,retention_mode,refcount,payload_inline,created_at"
            ") VALUES('engram-1','default','hash-1','user_input','store',"
            "'whole_record','internal','audit_retain',0,X'','2026-05-23T10:00:00Z')")
        conn.commit()

    llm = _core.FakeLLMAdapter()
    extractor = _core.Extractor(rt.adapter.connection(), llm)
    body = _core.Extractor.build_prompt_body("cog-self", b"\x01\x02\x03", {})
    h = _core.Extractor.compute_prompt_input_hash(body)
    llm.set_response(h, raw_xml=XML_TWO_DUPS, ok=True)

    r = extractor.run("engram-1", b"\x01\x02\x03", "cog-self", "default", {})
    assert r.status == "success"
    assert len(r.accepted_statement_ids) == 2

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        rows = conn.execute(
            "SELECT review_status FROM statements ORDER BY created_at ASC"
        ).fetchall()

    assert len(rows) == 2
    assert rows[0][0] == "approved"
    assert rows[1][0] == "review_requested"
