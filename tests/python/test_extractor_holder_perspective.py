"""TC-Q2-001..004 acceptance: each holder_perspective fixture round-trips
to the statements table with the correct enum value.

Per docs/design/system_design.md §15.3.1 these are P1 CRITICAL ship-gates."""
from __future__ import annotations

import sqlite3
import json

import pytest

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


# Single-element JSON-array fixtures keyed by perspective. Each element's
# holder_perspective is the UPPERCASE of the key (matches the real eval prompt);
# the parser lowercases it, so the stored value round-trips to the lowercase
# key. object is a plain string (bool true → "true"); the canonical hash is
# computed C++-side. All confidences are ≥0.3, so all are accepted.
FIXTURES = {
    "first_person": json.dumps([
        {"holder": "cog-self", "holder_perspective": "FIRST_PERSON",
         "subject": "cog-self", "predicate": "responsible_for", "object": "auth",
         "modality": "BELIEVES", "polarity": "POS", "confidence": 0.85,
         "nesting_depth": 0},
    ]),
    "quoted": json.dumps([
        {"holder": "cog-self", "holder_perspective": "QUOTED",
         "subject": "cog-bob", "predicate": "responsible_for", "object": "auth",
         "modality": "BELIEVES", "polarity": "POS", "confidence": 0.75,
         "nesting_depth": 0},
    ]),
    "hearsay": json.dumps([
        {"holder": "cog-self", "holder_perspective": "HEARSAY",
         "subject": "cog-bob", "predicate": "left_company", "object": "true",
         "modality": "BELIEVES", "polarity": "POS", "confidence": 0.55,
         "nesting_depth": 0},
    ]),
    "inferred": json.dumps([
        {"holder": "cog-self", "holder_perspective": "INFERRED",
         "subject": "cog-bob", "predicate": "upset_about", "object": "scope_change",
         "modality": "BELIEVES", "polarity": "POS", "confidence": 0.40,
         "nesting_depth": 0},
    ]),
}


@pytest.fixture
def rt(tmp_path, monkeypatch):
    original = relax_preflight_for_m0_3()
    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    rt.start()
    yield rt
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", original)


def _seed_engram(rt, engram_id="engram-1"):
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute(
            "INSERT INTO engrams("
            "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
            "  privacy_class,retention_mode,refcount,payload_inline,created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (engram_id, "default", "hash-1", "user_input", "store",
             "whole_record", "internal", "audit_retain", 0, b"", "2026-05-23T10:00:00Z"),
        )
        conn.commit()


@pytest.mark.parametrize("perspective", ["first_person", "quoted", "hearsay", "inferred"])
def test_holder_perspective_round_trip(rt, perspective):
    _seed_engram(rt)
    adapter = rt.adapter
    llm = _core.FakeLLMAdapter()
    extractor = _core.Extractor(adapter.connection(), llm)

    prompt_body = extractor.build_prompt_body("cog-self", b"\x01\x02\x03", {})
    h = extractor.compute_prompt_input_hash(prompt_body)
    llm.set_response(h, raw_xml=FIXTURES[perspective], ok=True, error="")

    result = extractor.run("engram-1", b"\x01\x02\x03", "cog-self", "default", {})
    assert result.status == "success"
    assert len(result.accepted_statement_ids) == 1

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        row = conn.execute(
            "SELECT holder_perspective FROM statements WHERE id = ?",
            (result.accepted_statement_ids[0],),
        ).fetchone()
    assert row is not None, "statement row missing"
    assert row[0] == perspective
