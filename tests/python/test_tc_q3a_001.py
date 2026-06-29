"""TC-Q3a-001 [CRITICAL] — mild correction does not mutate provenance.

When ConflictProbe sees a mild_correction kind (same canonical_object,
same polarity, non-severe confidence/interval), it edits the existing
Statement's confidence + confidence_history but does NOT touch
provenance. Verifies that provenance (derivation_kind as stored in the
`provenance` column) is unchanged after a mild-correction write.

Pattern follows test_tc_new_conflict_severe.py:
  - _core.ExtractedStatement() DTO constructed directly
  - _core.Bus(rt.adapter).write(...) for statement writes
  - out["stmt_id"] for the returned statement id
  - rt.adapter.db_path for second-connection SQL assertions
"""

from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime
from starling.testing import mark_consolidated


@pytest.fixture
def rt(tmp_path):
    """File-backed Runtime for tests."""
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_engram(rt, engram_id: str, content_hash: str) -> None:
    """Seed a minimal Engram row via direct SQL (follows pattern in test_tc_new_conflict_severe)."""
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


def _make_extracted(*, confidence: float):
    """Construct an ExtractedStatement DTO via the C++ binding.

    All identity / predicate / object fields are held constant so the
    canonical_conflict_key collides between S_old and S_new.
    No valid_from / valid_to set → unknown interval → MildCorrection path.
    """
    s = _core.ExtractedStatement()
    s.holder_id          = "alice"
    s.holder_tenant_id   = "default"
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind       = "cognizer"
    s.subject_id         = "bob"
    s.predicate          = "responsible_for"
    s.object_kind        = "str"
    s.object_value       = "auth"
    s.canonical_object_hash = "deadbeef01234567deadbeef01234567" \
                              "deadbeef01234567deadbeef01234567"
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = _core.Polarity.POS
    s.confidence         = confidence
    s.observed_at        = "2026-05-24T10:00:00Z"
    s.source_hash        = "fff"
    s.perceived_by       = ["alice"]
    return s


def test_mild_correction_preserves_provenance(rt):
    """TC-Q3a-001 happy path — §15.3.1 invariants.

    Sequence:
      1. Seed two Engrams (FK targets for span attachment).
      2. Bus::write S_old (POS, conf 0.55) → accepted.
      3. mark_consolidated(S_old) → VOLATILE → CONSOLIDATED.
      4. Capture provenance + confidence from S_old row.
      5. Bus::write S_new (POS, same canonical object, conf 0.95) →
         same polarity + unknown interval → MildCorrection path →
         S_old.confidence bumped, S_old.confidence_history_json updated,
         S_old.provenance unchanged.

    Then asserts the three TC-Q3a-001 invariants directly via stdlib
    sqlite3 from a second connection (rules out in-memory adapter cache).
    """
    _seed_engram(rt, "engram-old", "hash-old")
    _seed_engram(rt, "engram-new", "hash-new")
    bus = _core.Bus(rt.adapter)

    # Step 2: Write S_old (POS, low confidence).
    s_old = _make_extracted(confidence=0.55)
    out_old = bus.write(s_old, "engram-old", "span-old", None)
    assert out_old["kind"] == "accepted", \
        f"S_old write must be 'accepted', got {out_old!r}"
    s_old_id = out_old["stmt_id"]

    # Step 3: Mark S_old CONSOLIDATED (VOLATILE → CONSOLIDATED).
    ok = mark_consolidated(rt.adapter, s_old_id, "default")
    assert ok is True, "mark_consolidated should transition VOLATILE → CONSOLIDATED"

    # Step 4: Capture provenance + confidence before mild correction.
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        row_before = conn.execute(
            "SELECT provenance, confidence FROM statements WHERE id = ?",
            (s_old_id,)
        ).fetchone()
    assert row_before is not None, "S_old row must exist"
    provenance_before = row_before[0]
    confidence_before = row_before[1]

    # Step 5: Write S_new — same canonical object, higher confidence, same polarity.
    # Unknown interval (no valid_from/valid_to) + same polarity → MildCorrection.
    s_new = _make_extracted(confidence=0.95)
    out_new = bus.write(s_new, "engram-new", "span-new", None)
    assert out_new["kind"] == "accepted", \
        f"S_new write must be 'accepted', got {out_new!r}"

    # Assert on S_old's row after mild correction.
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        row_after = conn.execute(
            "SELECT provenance, confidence, confidence_history_json "
            "FROM statements WHERE id = ?",
            (s_old_id,)
        ).fetchone()
    assert row_after is not None, "S_old row must still exist after mild correction"

    # Invariant 1: provenance must not change.
    assert row_after[0] == provenance_before, \
        f"provenance must not change in mild correction; " \
        f"before={provenance_before!r}, after={row_after[0]!r}"

    # Invariant 2: confidence may increase (or stay the same) — never decrease.
    assert row_after[1] >= confidence_before, \
        f"confidence may increase; before={confidence_before}, after={row_after[1]}"

    # Invariant 3: confidence_history_json must capture the prior value.
    history = row_after[2]
    assert history and history != "[]", \
        f"confidence_history_json must be populated after mild correction; got {history!r}"
    # The prior confidence (0.55) must appear somewhere in the history JSON.
    assert "0.55" in history or str(confidence_before) in history, \
        f"confidence_history must capture prior value {confidence_before}; got {history!r}"
