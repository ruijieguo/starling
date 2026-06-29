"""E2E #2 — Extractor -> ConflictProbe -> basic_retrieve in one trace.

Exercises M0.4 + M0.5 + M0.6 in a single end-to-end scenario.

Spec §15.3 (M0.7 acceptance gate, second E2E):
  1. Seed S_old (POS, high-confidence, interval ends before query date) and
     mark it CONSOLIDATED — simulates a belief that has been through the
     consolidation pipeline.
  2. Write S_new with polarity=NEG and an overlapping interval through
     Bus.write — the ConflictProbe sees a direct_contradiction and fires the
     atomic §15.3.4 4-item commit: S_old archived, SUPERSEDES edge inserted,
     statement.written + statement.archived + statement.superseded events
     emitted.
  3. Mark S_new CONSOLIDATED so basic_retrieve accepts it
     (consolidation_state IN ('consolidated','archived')).
  4. basic_retrieve at an as_of that falls inside S_new's valid interval but
     OUTSIDE S_old's valid interval returns exactly S_new with
     sufficiency_status == 'SUFFICIENT', evidence_erased_count == 0, and
     candidate_counts.fetched == candidate_counts.returned == 1.

Interval design (why intervals overlap for conflict AND S_old is excluded at retrieval):
  - S_old:  valid_from=2026-05-01, valid_to=2026-08-01  (closed upper bound)
  - S_new:  valid_from=2026-06-01, valid_to=2027-01-01  (extends past S_old)
  - as_of:  2026-09-01 — AFTER S_old's valid_to, INSIDE S_new's interval
  The intervals [2026-05-01, 2026-08-01) and [2026-06-01, 2027-01-01) overlap
  in [2026-06-01, 2026-08-01), which triggers the ConflictProbe's overlap
  predicate and causes the direct_contradiction path to fire.
  At retrieval as_of=2026-09-01: S_old is excluded by the time-anchor predicate
  (valid_to=2026-08-01 <= as_of), S_new is included (valid_to=2027-01-01 > as_of).
  Even though S_old is 'archived' (which is in the consolidation_state filter),
  the time-anchor predicate removes it from the result set.

4-item atomic commit (§15.3.4):
  The bus_events count in this test is 6 total:
    1x S_old statement.written         (step 2 Bus::write)
    1x testing.mark_consolidated       (step 3 mark_consolidated call)
    1x S_new statement.written         (step 4 Bus::write)
    1x S_old statement.archived        (atomic SUPERSEDES path)
    1x S_new statement.superseded      (atomic SUPERSEDES path)
    1x testing.mark_consolidated       (step 5 mark_consolidated on S_new)
  The SUPERSEDES path itself is a 4-item payload commit in the C++ layer
  (S_old archived row, SUPERSEDES edge, statement.archived event, and
  statement.superseded event) — the test verifies all four items exist.

Pattern mirrors test_tc_new_conflict_severe.py + test_basic_retrieve_smoke.py:
  - _core.ExtractedStatement() DTO constructed directly
  - _core.Bus(rt.adapter).write(...) for writes
  - out["stmt_id"] for the returned statement id
  - rt.adapter.db_path for second-connection SQL assertions
  - starling.testing.mark_consolidated for VOLATILE -> CONSOLIDATED
  - starling.retrieval.basic_retrieve for the end-to-end retrieve leg
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from starling import _core, runtime
from starling.retrieval import basic_retrieve
from starling.testing import mark_consolidated


@pytest.fixture
def rt(tmp_path):
    """File-backed Runtime for tests.

    Mirrors the fixture pattern from test_tc_new_conflict_severe.py and
    test_basic_retrieve_smoke.py: build a real SqliteAdapter-backed Runtime
    at a tmp path and start it.

    File-backed (not :memory:) so we can open a second stdlib sqlite3
    connection to verify bus_events count and statement_edges rows,
    ruling out any in-memory adapter cache.
    """
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_engram(rt, engram_id: str, content_hash: str) -> None:
    """Seed a minimal Engram row via direct SQL.

    Mirrors test_tc_new_conflict_severe.py::_seed_engram exactly. Two
    distinct engrams are required because StatementWriter's chunk-level
    duplicate guard (§15.3.2 — find_existing_in_chunk) keys on
    (tenant_id, holder_id, predicate, canonical_object_hash, evidence_engram_id).
    S_old and S_new share every field except polarity + interval, so attaching
    them to the same Engram would classify S_new as a chunk_duplicate and
    short-circuit before ConflictProbe ever runs.
    """
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            "INSERT INTO engrams("
            "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
            "  privacy_class,retention_mode,refcount,payload_inline,created_at,"
            "  source_item_id"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (engram_id, "default", content_hash, "user_input", "store",
             "whole_record", "internal", "audit_retain", 0, bytes([0]),
             "2026-05-25T09:00:00Z", engram_id))
        conn.commit()


def _make_extracted(polarity: str, confidence: float,
                    valid_from: str, valid_to):
    """Construct an ExtractedStatement DTO via the C++ binding.

    All identity / predicate / object fields are held constant across S_old
    and S_new so the canonical_conflict_key collides — this is what makes
    the pair eligible for direct_contradiction (opposite polarity + overlapping
    interval).

    valid_to is str | None; None encodes the open upper bound (NULL in SQL).
    """
    s = _core.ExtractedStatement()
    s.holder_id              = "cog-self"
    s.holder_tenant_id       = "default"
    s.holder_perspective     = _core.Perspective.FIRST_PERSON
    s.subject_kind           = "cognizer"
    s.subject_id             = "cog-bob"
    s.predicate              = "responsible_for"
    s.object_kind            = "str"
    s.object_value           = "auth"
    s.canonical_object_hash  = ("deadbeef01234567deadbeef01234567"
                                "deadbeef01234567deadbeef01234567")
    s.modality               = _core.Modality.BELIEVES
    s.polarity               = (_core.Polarity.POS if polarity == "pos"
                                else _core.Polarity.NEG)
    s.confidence             = confidence
    s.observed_at            = "2026-05-25T10:00:00Z"
    s.source_hash            = "e2e-conflict-hash"
    s.valid_from             = valid_from
    s.valid_to               = valid_to
    s.perceived_by           = ["cog-self"]
    return s


def test_e2e_severe_conflict_and_retrieve(rt):
    """E2E #2: severe conflict + retrieve in one trace — §15.3 acceptance.

    Sequence:
      1. Seed two Engrams (FK targets; see _seed_engram for rationale).
      2. Bus::write S_old (POS, conf 0.85, valid 2026-05-01..2026-08-01).
      3. mark_consolidated(S_old) — VOLATILE -> CONSOLIDATED.
      4. Bus::write S_new (NEG, conf 0.85, valid 2026-06-01..2027-01-01) —
         opposite polarity + overlapping interval => direct_contradiction
         => atomic 4-item commit (S_old archived, SUPERSEDES edge,
         statement.archived + statement.superseded events).
      5. mark_consolidated(S_new) — so basic_retrieve can return it.
      6. basic_retrieve at 2026-09-01 — S_old excluded by time anchor
         (valid_to=2026-08-01 <= as_of), S_new included (valid_to=2027-01-01).

    §15.3.4 atomic commit assertions (via second sqlite3 connection):
      - S_old.consolidation_state == 'archived'
      - S_new.consolidation_state == 'consolidated'   (after step 5)
      - exactly 1 supersedes edge (src=S_new, dst=S_old)
      - 1x statement.written for S_new, 1x statement.archived for S_old,
        1x statement.superseded for S_new (from the atomic path)
      - archive payload contains 'direct_contradiction'

    basic_retrieve assertions:
      - fetched == returned == 1
      - evidence_erased_count == 0
      - sufficiency_status == 'SUFFICIENT'
      - only S_new is in result.rows
    """
    _seed_engram(rt, "engram-old", "hash-e2e-old")
    _seed_engram(rt, "engram-new", "hash-e2e-new")
    bus = _core.Bus(rt.adapter)

    # Step 2: Write S_old — POS belief, closed upper bound at 2026-08-01.
    # Interval [2026-05-01, 2026-08-01) overlaps with S_new's [2026-06-01, 2027-01-01).
    s_old_dto = _make_extracted("pos", 0.85,
                                "2026-05-01T00:00:00Z", "2026-08-01T00:00:00Z")
    out_old = bus.write(s_old_dto, "engram-old", "e2e-span-old", None)
    assert out_old["kind"] == "accepted", \
        f"S_old write must be accepted, got {out_old!r}"
    s_old_id = out_old["stmt_id"]

    # Step 3: Mark S_old CONSOLIDATED (VOLATILE -> CONSOLIDATED).
    ok = mark_consolidated(rt.adapter, s_old_id, "default")
    assert ok is True, "mark_consolidated must transition VOLATILE -> CONSOLIDATED"

    # Step 4: Write S_new — NEG, opposite polarity, overlapping interval.
    # valid_from=2026-06-01 and valid_to=2027-01-01 overlaps with S_old's
    # [2026-05-01, 2026-08-01) in the window [2026-06-01, 2026-08-01),
    # satisfying the ConflictProbe's overlap predicate.
    s_new_dto = _make_extracted("neg", 0.85,
                                "2026-06-01T00:00:00Z", "2027-01-01T00:00:00Z")
    out_new = bus.write(s_new_dto, "engram-new", "e2e-span-new", None)
    assert out_new["kind"] == "accepted", \
        f"S_new write must be accepted, got {out_new!r}"
    s_new_id = out_new["stmt_id"]

    # Step 5: Mark S_new CONSOLIDATED so basic_retrieve can return it.
    # Bus.write lands rows as VOLATILE; basic_retrieve's
    # consolidation_state IN ('consolidated','archived') filter excludes them.
    ok2 = mark_consolidated(rt.adapter, s_new_id, "default")
    assert ok2 is True, "mark_consolidated must transition S_new VOLATILE -> CONSOLIDATED"

    # -- §15.3.4 atomic commit assertions (second sqlite3 connection) -------
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")

        # S_old must be archived (T7-P1 bypass — CONSOLIDATED -> ARCHIVED directly).
        state_old = conn.execute(
            "SELECT consolidation_state FROM statements WHERE id=?",
            (s_old_id,)).fetchone()[0]
        assert state_old == "archived", \
            f"S_old must be archived after severe conflict; got {state_old!r}"

        # S_new must be consolidated (mark_consolidated in step 5).
        state_new = conn.execute(
            "SELECT consolidation_state FROM statements WHERE id=?",
            (s_new_id,)).fetchone()[0]
        assert state_new == "consolidated", \
            f"S_new must be consolidated after step 5; got {state_new!r}"

        # Exactly 1 SUPERSEDES edge (src=S_new, dst=S_old).
        n_supersedes = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE src_id=? AND dst_id=? AND edge_kind='supersedes'",
            (s_new_id, s_old_id)).fetchone()[0]
        assert n_supersedes == 1, \
            f"expected exactly 1 supersedes edge, got {n_supersedes}"

        # No non-supersedes conflict edges between the pair.
        n_other = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE src_id=? AND dst_id=? "
            "AND edge_kind IN ('conflicts_with','may_overlap_with','adjacent')",
            (s_new_id, s_old_id)).fetchone()[0]
        assert n_other == 0, \
            f"expected zero non-supersedes edges, got {n_other}"

        # statement.written for S_new (part of the 4-item atomic commit).
        n_written = conn.execute(
            "SELECT COUNT(*) FROM bus_events "
            "WHERE event_type='statement.written' AND primary_id=?",
            (s_new_id,)).fetchone()[0]
        assert n_written == 1, \
            f"expected 1 statement.written for S_new, got {n_written}"

        # statement.archived for S_old (part of the 4-item atomic commit).
        n_archived = conn.execute(
            "SELECT COUNT(*) FROM bus_events "
            "WHERE event_type='statement.archived' AND primary_id=?",
            (s_old_id,)).fetchone()[0]
        assert n_archived == 1, \
            f"expected 1 statement.archived for S_old, got {n_archived}"

        # Archive event payload must cite direct_contradiction as the reason.
        archive_payload = conn.execute(
            "SELECT payload_json FROM bus_events "
            "WHERE event_type='statement.archived' AND primary_id=?",
            (s_old_id,)).fetchone()[0]
        assert "direct_contradiction" in archive_payload, \
            f"archive payload missing 'direct_contradiction'; got {archive_payload!r}"

        # statement.superseded for S_new (part of the 4-item atomic commit).
        n_superseded = conn.execute(
            "SELECT COUNT(*) FROM bus_events "
            "WHERE event_type='statement.superseded' AND primary_id=?",
            (s_new_id,)).fetchone()[0]
        assert n_superseded == 1, \
            f"expected 1 statement.superseded for S_new, got {n_superseded}"

    # -- basic_retrieve assertions ------------------------------------------
    # Query at 2026-09-01:
    #   S_old excluded -- valid_to=2026-08-01 is NOT NULL and <= 2026-09-01
    #                     (time-anchor predicate: valid_to IS NULL OR valid_to > as_of)
    #   S_new included -- valid_from=2026-06-01 <= 2026-09-01 AND
    #                     valid_to=2027-01-01 > 2026-09-01
    result = basic_retrieve(
        rt.adapter,
        tenant_id="default",
        holder="cog-self",
        subject="cog-bob",
        predicate="responsible_for",
        as_of=datetime(2026, 9, 1, tzinfo=timezone.utc),
        trace_id="e2e-trace-severe",
        query_id="e2e-query-severe",
    )

    # Only S_new must appear; S_old is excluded by the time-anchor predicate.
    assert len(result.rows) == 1, \
        f"expected exactly S_new, got rows={[r.id for r in result.rows]!r}"
    row = result.rows[0]
    assert row.id == s_new_id, \
        f"returned row must be S_new ({s_new_id}), got {row.id}"

    # Candidate counts: fetched == returned == 1.
    assert result.receipt.candidate_counts.fetched == 1, \
        f"fetched must be 1 (S_new only), got {result.receipt.candidate_counts.fetched}"
    assert result.receipt.candidate_counts.returned == 1, \
        f"returned must be 1, got {result.receipt.candidate_counts.returned}"

    # No evidence was erased.
    assert result.receipt.evidence_erased_count == 0, \
        f"evidence_erased_count must be 0, got {result.receipt.evidence_erased_count}"

    # Sufficiency: one returned row => SUFFICIENT.
    # Note: the Python retrieval layer maps the C++ Sufficiency enum to
    # UPPERCASE string names ('SUFFICIENT', 'MISSING_INFO', etc.).
    assert result.receipt.sufficiency_status == "SUFFICIENT", \
        f"one returned row must yield SUFFICIENT; got {result.receipt.sufficiency_status!r}"

    # Trace/query ids echo the caller's values.
    assert result.receipt.trace_id == "e2e-trace-severe"
    assert result.receipt.query_id == "e2e-query-severe"
