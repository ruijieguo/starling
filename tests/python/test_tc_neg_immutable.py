"""TC-NEG-IMMUTABLE [CRITICAL] — SQLite triggers reject direct UPDATE of immutable fields.

Spec §15.3.1:
  "post-write in-place UPDATE on holder / source_speaker / perceived_by /
   tenant_id / provenance must be rejected by Validator; correct path is
   statement.corrected + supersedes."

DB column mapping (actual schema vs. plan):
  holder          → holder_id
  source_speaker  → holder_perspective  (QUOTED perspective encodes source-speaker
                    attribution; source_speaker XML attr is merged into perceived_by_json
                    at ingest but holder_perspective carries the mode)
  perceived_by    → perceived_by_json
  tenant_id       → tenant_id
  provenance      → provenance           (NOT provenance_json — schema uses plain 'provenance')

Implementation: migration 0006 adds 5 BEFORE UPDATE triggers that RAISE(ABORT, ...)
when any of those columns would change.

Test structure:
  - 5 parametrized negative cases: direct SQL UPDATE of each immutable column must
    raise sqlite3.DatabaseError whose message contains "immutable".
  - 1 sanity case: UPDATE statements SET confidence = ? must SUCCEED (mutable column).

Pattern mirrors test_tc_q3b_001.py / test_tc_neg_timeanchor.py:
  - _core.ExtractedStatement() DTO constructed directly
  - _core.Bus(rt.adapter).write(...) for first write
  - out["stmt_id"] for the returned statement id
  - rt.adapter.db_path for direct sqlite3 assertions
"""

from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def rt(tmp_path):
    """File-backed Runtime with the M0.3 preflight relaxed for tests."""
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_engram(rt, engram_id: str, content_hash: str) -> None:
    """Seed a minimal Engram row via direct SQL (mirrors test_tc_q3b_001 pattern)."""
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
             "2026-05-25T09:00:00Z", engram_id),
        )
        conn.commit()


def _make_base_stmt() -> "_core.ExtractedStatement":
    """Construct a minimal ExtractedStatement for the immutable-field tests."""
    s = _core.ExtractedStatement()
    s.holder_id             = "alice"
    s.holder_tenant_id      = "default"
    s.holder_perspective    = _core.Perspective.FIRST_PERSON
    s.subject_kind          = "cognizer"
    s.subject_id            = "bob"
    s.predicate             = "responsible_for"
    s.object_kind           = "str"
    s.object_value          = "auth"
    s.canonical_object_hash = "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222"
    s.modality              = _core.Modality.BELIEVES
    s.polarity              = _core.Polarity.POS
    s.confidence            = 0.80
    s.observed_at           = "2026-05-25T10:00:00Z"
    s.source_hash           = "cafebabe"
    s.perceived_by          = ["alice"]
    return s


@pytest.fixture
def written_stmt_id(rt):
    """Write one Statement once; return its id for reuse across negative-case tests."""
    _seed_engram(rt, "engram-immutable-01", "hash-immutable-01")
    bus = _core.Bus(rt.adapter)
    s = _make_base_stmt()
    out = bus.write(s, "engram-immutable-01", "span-immutable-01", None)
    assert out["kind"] == "accepted", \
        f"Seed write must succeed; got {out!r}"
    return out["stmt_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Negative cases: direct SQL UPDATE of immutable columns must be rejected
# ─────────────────────────────────────────────────────────────────────────────

_IMMUTABLE_CASES = [
    # (test_id, column, new_value)
    ("holder_id",          "holder_id",          "mallory"),
    ("holder_perspective", "holder_perspective",  "quoted"),
    ("perceived_by_json",  "perceived_by_json",   '["mallory"]'),
    ("tenant_id",          "tenant_id",           "other-tenant"),
    ("provenance",         "provenance",          "direct"),
]


@pytest.mark.parametrize("test_id,column,new_value", _IMMUTABLE_CASES,
                         ids=[c[0] for c in _IMMUTABLE_CASES])
def test_immutable_field_rejected(rt, written_stmt_id, test_id, column, new_value):
    """Each immutable column must raise sqlite3.DatabaseError on direct UPDATE.

    The BEFORE UPDATE trigger fires and RAISE(ABORT, 'immutable field: ...')
    surfaces as a sqlite3.DatabaseError.  The error message must contain the
    word "immutable" (supplied by the trigger's RAISE message).
    """
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        with pytest.raises(sqlite3.DatabaseError) as exc_info:
            conn.execute(
                f"UPDATE statements SET {column} = ? WHERE id = ?",
                (new_value, written_stmt_id),
            )
        assert "immutable" in str(exc_info.value).lower(), (
            f"Expected 'immutable' in error message for column {column!r}; "
            f"got: {exc_info.value!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Sanity: mutable column must still succeed
# ─────────────────────────────────────────────────────────────────────────────

def test_mutable_confidence_update_succeeds(rt, written_stmt_id):
    """confidence is mutable (mild-correction path); UPDATE must NOT raise.

    This guards against over-broad triggers that block all updates.
    """
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        # Should not raise — confidence is the only mutable field tested here.
        conn.execute(
            "UPDATE statements SET confidence = ? WHERE id = ?",
            (0.55, written_stmt_id),
        )
        conn.commit()

    # Verify the update actually landed.
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        row = conn.execute(
            "SELECT confidence FROM statements WHERE id = ?",
            (written_stmt_id,),
        ).fetchone()
    assert row is not None, "Row must still exist after confidence update"
    assert abs(row[0] - 0.55) < 1e-9, (
        f"confidence must be 0.55 after UPDATE; got {row[0]!r}"
    )
