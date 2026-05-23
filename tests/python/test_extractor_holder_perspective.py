"""TC-Q2-001..004 acceptance: each holder_perspective fixture round-trips
to the statements table with the correct enum value.

Per docs/design/system_design.md §15.3.1 these are P1 CRITICAL ship-gates."""
from __future__ import annotations

import sqlite3
import textwrap

import pytest

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


# Canned XML responses keyed by perspective; matches the parser fixtures from
# tests/cpp/test_xml_parser.cpp so we exercise the same shape end-to-end.
FIXTURES = {
    "first_person": textwrap.dedent("""
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
    """).strip(),
    "quoted": textwrap.dedent("""
        <extraction>
          <statement source_speaker="cog-bob">
            <holder ref="cog-self"/>
            <perspective>quoted</perspective>
            <subject kind="cognizer" id="cog-bob"/>
            <predicate>responsible_for</predicate>
            <object kind="str" canonical_hash="hash-auth">auth</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.75</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
            <perceived_by ref="cog-bob"/>
          </statement>
        </extraction>
    """).strip(),
    "hearsay": textwrap.dedent("""
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>hearsay</perspective>
            <subject kind="cognizer" id="cog-bob"/>
            <predicate>left_company</predicate>
            <object kind="bool" canonical_hash="hash-true">true</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.55</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>
    """).strip(),
    "inferred": textwrap.dedent("""
        <extraction>
          <statement>
            <holder ref="cog-self"/>
            <perspective>inferred</perspective>
            <subject kind="cognizer" id="cog-bob"/>
            <predicate>upset_about</predicate>
            <object kind="str" canonical_hash="hash-x">scope_change</object>
            <modality>believes</modality>
            <polarity>pos</polarity>
            <confidence>0.40</confidence>
            <observed_at>2026-05-23T10:00:00Z</observed_at>
            <perceived_by ref="cog-self"/>
          </statement>
        </extraction>
    """).strip(),
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
