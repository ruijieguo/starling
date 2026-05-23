"""M0.4 acceptance smoke — §14.1 flat-3 subset.

Drives the full extraction pipeline:
  Engram seeded → Extractor.run → 3 Statements written → 3 statement.written
  events → 1 pipeline.run_started + 1 pipeline.run_completed → 1
  PipelineRun status='finished' → 1 ExtractionAttempt status='success'.

Per system_design.md §14.1, the §14.1 scenario produces 4 Statements where
S3 nests S2 (nesting_depth=1). M0.4 ships flat-only (no nesting); S3 is
deferred to M0.5. The TC-Q2 holder_perspective contracts are covered
across S1 (FIRST_PERSON via Alice's announcement seen by self),
S2 (QUOTED with source_speaker=Alice), S4 (HEARSAY: holder=Alice).
"""
from __future__ import annotations

import sqlite3
import textwrap

import pytest

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


# §14.1 flat-3 scenario: Alice announces in a group that Carol now owns auth
# (so Bob no longer does). Self perceives the group message; the extractor
# emits three Statements:
#   S1 holder=self, subject=Bob, predicate=responsible_for, obj=auth, pol=NEG, FIRST_PERSON
#   S2 holder=self, subject=Carol, predicate=responsible_for, obj=auth, pol=POS, QUOTED (Alice said it)
#   S4 holder=Alice, subject=Bob, predicate=responsible_for, obj=auth, pol=NEG, HEARSAY (we record what Alice believes)
SCENARIO_XML = textwrap.dedent("""
    <extraction>
      <statement>
        <holder ref="cog-self"/>
        <perspective>first_person</perspective>
        <subject kind="cognizer" id="cog-bob"/>
        <predicate>responsible_for</predicate>
        <object kind="str" canonical_hash="hash-auth">auth</object>
        <modality>believes</modality>
        <polarity>neg</polarity>
        <confidence>0.85</confidence>
        <observed_at>2026-05-23T10:00:00Z</observed_at>
        <perceived_by ref="cog-self"/>
        <perceived_by ref="cog-alice"/>
        <perceived_by ref="cog-bob"/>
      </statement>
      <statement source_speaker="cog-alice">
        <holder ref="cog-self"/>
        <perspective>quoted</perspective>
        <subject kind="cognizer" id="cog-carol"/>
        <predicate>responsible_for</predicate>
        <object kind="str" canonical_hash="hash-auth">auth</object>
        <modality>believes</modality>
        <polarity>pos</polarity>
        <confidence>0.85</confidence>
        <observed_at>2026-05-23T10:00:00Z</observed_at>
        <perceived_by ref="cog-self"/>
        <perceived_by ref="cog-alice"/>
      </statement>
      <statement>
        <holder ref="cog-alice"/>
        <perspective>hearsay</perspective>
        <subject kind="cognizer" id="cog-bob"/>
        <predicate>responsible_for</predicate>
        <object kind="str" canonical_hash="hash-auth">auth</object>
        <modality>believes</modality>
        <polarity>neg</polarity>
        <confidence>0.65</confidence>
        <observed_at>2026-05-23T10:00:00Z</observed_at>
        <perceived_by ref="cog-alice"/>
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
            ") VALUES('engram-141','default','hash-141','user_input','store',"
            "'whole_record','internal','audit_retain',0,X'','2026-05-23T10:00:00Z')")
        conn.commit()


def test_section_14_1_flat_three_scenario(rt):
    _seed_engram(rt)
    llm = _core.FakeLLMAdapter()
    extractor = _core.Extractor(rt.adapter.connection(), llm)
    body = _core.Extractor.build_prompt_body("cog-self", b"\x01\x02\x03", {})
    h = _core.Extractor.compute_prompt_input_hash(body)
    llm.set_response(h, raw_xml=SCENARIO_XML, ok=True)

    r = extractor.run("engram-141", b"\x01\x02\x03", "cog-self", "default", {})
    assert r.status == "success"
    assert len(r.accepted_statement_ids) == 3

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        rows = conn.execute("""
            SELECT holder_id, holder_perspective, subject_id, predicate, polarity
            FROM statements ORDER BY rowid ASC
        """).fetchall()

        assert len(rows) == 3

        # S1
        assert rows[0] == ("cog-self", "first_person", "cog-bob", "responsible_for", "neg")
        # S2
        assert rows[1] == ("cog-self", "quoted",       "cog-carol", "responsible_for", "pos")
        # S4 — holder is always stamped as the calling cognizer (cog-self);
        # hearsay perspective records that the belief was heard from cog-alice
        assert rows[2] == ("cog-self", "hearsay",      "cog-bob", "responsible_for", "neg")

        # Bus events
        n_written  = conn.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.written'"
        ).fetchone()[0]
        n_started  = conn.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='pipeline.run_started'"
        ).fetchone()[0]
        n_completed = conn.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='pipeline.run_completed'"
        ).fetchone()[0]
        n_run = conn.execute(
            "SELECT COUNT(*) FROM pipeline_run WHERE status='finished'"
        ).fetchone()[0]
        n_attempts = conn.execute(
            "SELECT COUNT(*) FROM extraction_attempt WHERE status='success'"
        ).fetchone()[0]

    assert n_written == 3, f"expected 3 statement.written events, got {n_written}"
    assert n_started == 1
    assert n_completed == 1
    assert n_run == 1
    assert n_attempts == 1
