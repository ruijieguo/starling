"""Partial-success path: one Statement validates, one does not. The
attempt records as PARTIAL_SUCCESS; the run completes (not failed) since
at least one Statement was written."""
from __future__ import annotations

import sqlite3
import json

import pytest

from starling import _core, runtime


# Two-element JSON array. Element 1 validates cleanly (confidence 0.85).
# Element 2 parses cleanly but carries confidence 0.10 < 0.3 → the VALIDATOR
# drops it (the drop is at validation, not parsing). UPPERCASE enums match the
# real eval prompt; the parser lowercases them.
JSON_PARTIAL = json.dumps([
    {"holder": "cog-self", "holder_perspective": "FIRST_PERSON",
     "subject": "cog-self", "predicate": "responsible_for", "object": "auth",
     "modality": "BELIEVES", "polarity": "POS", "confidence": 0.85,
     "nesting_depth": 0},
    {"holder": "cog-self", "holder_perspective": "INFERRED",
     "subject": "cog-bob", "predicate": "likes_cake", "object": "true",
     "modality": "BELIEVES", "polarity": "POS", "confidence": 0.10,
     "nesting_depth": 0},
])


@pytest.fixture
def rt(tmp_path):
    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    rt.start()
    yield rt


def test_partial_success(rt):
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
    llm.set_response(h, raw_xml=JSON_PARTIAL, ok=True)

    r = extractor.run("engram-1", b"\x01\x02\x03", "cog-self", "default", {})
    assert len(r.accepted_statement_ids) == 1

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        attempt_status = conn.execute(
            "SELECT status FROM extraction_attempt ORDER BY rowid DESC LIMIT 1"
        ).fetchone()[0]
        run_status = conn.execute(
            "SELECT status FROM pipeline_run"
        ).fetchone()[0]

    assert attempt_status == "partial_success"
    assert run_status == "finished"
    assert r.status == "partial_success"
