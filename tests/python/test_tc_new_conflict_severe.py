"""TC-NEW-CONFLICT-SEVERE [P1 CRITICAL] — direct_contradiction atomic 4-item commit.

Per system_design.md §15.3.4 + 05_bus.md §3.5 P1 sync severe-conflict path.
Covers: M0.5 ConflictProbe, §3.5 T7-P1 (CONSOLIDATED → ARCHIVED bypass),
§3.12 SUPERSEDES edge, §14.1 write path.

This test is the M0.5 ship gate. Failure here = M0.5 cannot close.

Drives the severe-conflict path end-to-end through the same Python
entrypoints production extractor pipelines will use post-M0.5 (Extractor →
Bus rewiring is post-M0.5 work; until that lands, Bus::write + the
ExtractedStatement DTO are bound on the main `_core` module purely so this
acceptance test can exercise §15.3.4 without a C++ harness — see
bindings/python/module.cpp comments at the Bus::write / ExtractedStatement
defs).

The CI static scan (scripts/ci_static_scan.py) bans starling.testing imports
from prod entrypoints — this test lives under tests/python/ which is in the
allowed-roots list, so the imports of `mark_consolidated` and
`relax_preflight_for_m0_3` are intentional and safe.
"""
from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime
from starling.testing import mark_consolidated, relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    """File-backed Runtime with the M0.3 preflight relaxed for tests.

    Mirrors the fixture pattern established in test_m0_4_acceptance and the
    M0.5 mark_consolidated suite: relax preflight, build a real
    SqliteAdapter-backed Runtime at a tmp path, start it, and restore the
    preflight requirement at teardown.
    """
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_engram(rt, engram_id: str, content_hash: str) -> None:
    """Seed a minimal Engram row via direct SQL.

    Bus::append_evidence is overkill here — the test only needs the
    foreign-key target so the statement_writer can attach extraction-span
    rows. Direct INSERT keeps the seed deterministic and outside the audit
    trail (so the bus_events count assertion stays clean).

    Two distinct engrams are needed because StatementWriter's chunk-level
    duplicate guard (§15.3.2 — `find_existing_in_chunk`) keys on
    `(tenant_id, holder_id, predicate, canonical_object_hash,
    evidence_engram_id)` and does NOT include polarity. S_old and S_new
    share every field except polarity + interval, so attaching them to the
    same Engram would classify S_new as a chunk_duplicate and short-circuit
    before ConflictProbe ever runs. Production extractors avoid this by
    associating each extraction call with a distinct chunk Engram.

    `chunk_index` is set per call so we don't collide on the migration-0003
    UNIQUE(tenant_id, adapter_name, source_item_id, source_version,
    chunk_index) — the M0.3 columns all default to '' / 0, so two seeded
    rows in the same tenant must differ on at least one tuple member.
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
             "whole_record", "internal", "audit_retain", 0, b"\x00",
             "2026-05-24T09:00:00Z", engram_id))
        conn.commit()


def _make_extracted(polarity: str, confidence: float,
                    valid_from: str, valid_to: str):
    """Construct an ExtractedStatement DTO via the C++ binding.

    All identity / predicate / object fields are held constant across S_old
    and S_new so the canonical_conflict_key collides — this is what makes
    the pair eligible for direct_contradiction (opposite polarity + same
    scope + overlapping interval).
    """
    s = _core.ExtractedStatement()
    s.holder_id          = "cog-self"
    s.holder_tenant_id   = "default"
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind       = "cognizer"
    s.subject_id         = "cog-bob"
    s.predicate          = "responsible_for"
    s.object_kind        = "str"
    s.object_value       = "auth"
    s.canonical_object_hash = "deadbeef"
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = (_core.Polarity.POS if polarity == "pos"
                            else _core.Polarity.NEG)
    s.confidence         = confidence
    s.observed_at        = "2026-05-24T10:00:00Z"
    s.source_hash        = "fff"
    s.valid_from         = valid_from
    s.valid_to           = valid_to
    return s


def test_tc_new_conflict_severe_atomic_commit(rt):
    """TC-NEW-CONFLICT-SEVERE happy path — see §15.3.4 invariants 1-7.

    Sequence:
      1. Seed an Engram (FK target for span attachment).
      2. Bus::write S_old (POS, conf 0.85, [2026-05-01, 2027-01-01)).
      3. mark_consolidated(S_old) — flips VOLATILE → CONSOLIDATED so the
         severe-conflict path takes T7-P1 (skips REPLAYING_RECONSOLIDATING).
      4. Bus::write S_new (NEG, conf 0.85, [2026-06-01, 2026-12-31)) —
         opposite polarity + overlapping interval ⇒ direct_contradiction
         ⇒ atomic 4-item commit.

    Then asserts the §15.3.4 invariants directly via stdlib sqlite3 from a
    second connection (rules out any in-memory adapter cache).
    """
    _seed_engram(rt, "engram-old", "hash-old")
    _seed_engram(rt, "engram-new", "hash-new")
    bus = _core.Bus(rt.adapter)

    # 1. Write S_old (POS, fully populated interval, high confidence).
    s_old = _make_extracted("pos", 0.85,
                            "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z")
    out_old = bus.write(s_old, "engram-old", "span-old", None)
    assert out_old["kind"] == "accepted", \
        f"S_old write must be 'accepted', got {out_old!r}"
    s_old_id = out_old["stmt_id"]

    # 2. Mark S_old CONSOLIDATED (flip from VOLATILE).
    ok = mark_consolidated(rt.adapter, s_old_id, "default")
    assert ok is True, "mark_consolidated should transition VOLATILE → CONSOLIDATED"

    # 3. Write S_new (NEG, opposite polarity, overlapping interval) —
    #    triggers direct_contradiction → atomic 4-item path.
    s_new = _make_extracted("neg", 0.85,
                            "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z")
    out_new = bus.write(s_new, "engram-new", "span-new", None)
    assert out_new["kind"] == "accepted", \
        f"S_new write must be 'accepted', got {out_new!r}"
    s_new_id = out_new["stmt_id"]

    # ── Assertions on the final DB state (§15.3.4 invariants 1-7) ─────
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")

        # Invariant 1: 2 statements rows.
        n_total = conn.execute("SELECT COUNT(*) FROM statements").fetchone()[0]
        assert n_total == 2, f"expected 2 statements rows, got {n_total}"

        # Invariant 2: S_new.consolidation_state='volatile'.
        state_new = conn.execute(
            "SELECT consolidation_state FROM statements WHERE id=?",
            (s_new_id,)).fetchone()[0]
        assert state_new == "volatile", \
            f"S_new state should be 'volatile', got {state_new!r}"

        # Invariant 3: S_old.consolidation_state='archived' (T7-P1 bypass —
        # NOT 'replaying_reconsolidating'; that path is for CONSOLIDATED rows
        # under non-severe conflict, which this test does not exercise).
        state_old = conn.execute(
            "SELECT consolidation_state FROM statements WHERE id=?",
            (s_old_id,)).fetchone()[0]
        assert state_old == "archived", \
            f"S_old state should be 'archived' (T7-P1 bypass), got {state_old!r}"

        # Invariant 4: exactly 1 SUPERSEDES edge (src=S_new, dst=S_old).
        n_supersedes = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE src_id=? AND dst_id=? AND edge_kind='supersedes'",
            (s_new_id, s_old_id)).fetchone()[0]
        assert n_supersedes == 1, \
            f"expected exactly 1 supersedes edge, got {n_supersedes}"

        # Invariant 5: NO conflicts_with / may_overlap_with / adjacent edges
        # between S_new and S_old — severe conflict must short-circuit the
        # debounced edge writers (see Bus::write Task 8 logic).
        n_other = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE src_id=? AND dst_id=? "
            "AND edge_kind IN ('conflicts_with','may_overlap_with','adjacent')",
            (s_new_id, s_old_id)).fetchone()[0]
        assert n_other == 0, \
            f"expected zero non-supersedes edges, got {n_other}"

        # Invariant 6a: 1 statement.written for S_new.
        n_written_new = conn.execute(
            "SELECT COUNT(*) FROM bus_events "
            "WHERE event_type='statement.written' AND primary_id=?",
            (s_new_id,)).fetchone()[0]
        assert n_written_new == 1, \
            f"expected 1 statement.written for S_new, got {n_written_new}"

        # Invariant 6b: 1 statement.archived for S_old, payload reasons
        # contains 'direct_contradiction'.
        n_archived = conn.execute(
            "SELECT COUNT(*) FROM bus_events "
            "WHERE event_type='statement.archived' AND primary_id=?",
            (s_old_id,)).fetchone()[0]
        assert n_archived == 1, \
            f"expected 1 statement.archived for S_old, got {n_archived}"

        archive_payload = conn.execute(
            "SELECT payload_json FROM bus_events "
            "WHERE event_type='statement.archived' AND primary_id=?",
            (s_old_id,)).fetchone()[0]
        assert "direct_contradiction" in archive_payload, \
            f"archive payload missing 'direct_contradiction'; got {archive_payload!r}"

        # Invariant 6c: 1 statement.superseded for S_new.
        n_superseded = conn.execute(
            "SELECT COUNT(*) FROM bus_events "
            "WHERE event_type='statement.superseded' AND primary_id=?",
            (s_new_id,)).fetchone()[0]
        assert n_superseded == 1, \
            f"expected 1 statement.superseded for S_new, got {n_superseded}"

        # Invariant 7: total bus_events = 5 across the whole sequence.
        #   Contributing events:
        #     1× S_old's statement.written   (from step 2 Bus::write)
        #     1× testing.mark_consolidated   (from step 3 helper)
        #     1× S_new's statement.written   (from step 4 Bus::write)
        #     1× S_old's statement.archived  (atomic SUPERSEDES path)
        #     1× S_new's statement.superseded (atomic SUPERSEDES path)
        # If this count drifts, inspect the breakdown via:
        #   SELECT event_type, COUNT(*) FROM bus_events GROUP BY event_type;
        n_total_events = conn.execute(
            "SELECT COUNT(*) FROM bus_events").fetchone()[0]
        assert n_total_events == 5, \
            f"expected 5 total bus_events, got {n_total_events}"
