"""TC-Q3b-001 [CRITICAL] — 2nd-order Statement object hash distinction.

When two Statements both reference an inner Statement as their object
(object_kind == "statement"), but the inner Statements differ, their
canonical_object_hash values MUST differ.  The ConflictProbe keys on
canonical_object_hash; identical hashes would cause a false collision and
incorrectly archive a valid belief.

Spec §15.3.1 (M0.7 acceptance gate):
  1. Both writes succeed (kind == "accepted").
  2. canonical_object_hash differs between the two DB rows.
  3. Both rows end up in a "kept" state (volatile or consolidated) — no
     conflict-driven archival occurs.

Pattern mirrors test_tc_q3a_001.py (most-recently-landed acceptance test):
  - _core.ExtractedStatement() DTO constructed directly
  - _core.Bus(rt.adapter).write(...) for writes
  - out["stmt_id"] for the returned statement id
  - rt.adapter.db_path for second-connection SQL assertions
"""

from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime

# Pre-computed SHA-256 hex digests representing two distinct inner Statements:
#   S_inner_1: bob knows calculus
#   S_inner_2: bob knows physics
# These are canonical object hashes that the XML extractor would compute
# from the referenced Statement rows (object_kind="statement", object_value
# == the referenced Statement.id).  In this direct-DTO test we supply them
# verbatim so the test is self-contained without a second-level Bus::write.
_HASH_CALCULUS = "94bb35d05a4d22800fc4dffb9df03ae8a281ecb3a0f9cfbe9e288f326c1cc834"
_HASH_PHYSICS  = "ac40a9f5028f5e04b3f12aa6ebeea6d855bf9abfcce6b55a3b80267337ac2535"

# Synthetic Statement IDs for the two "inner" statements that alice believes.
_INNER_ID_CALCULUS = "inner-stmt-bob-knows-calculus"
_INNER_ID_PHYSICS  = "inner-stmt-bob-knows-physics"


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
             "2026-05-25T09:00:00Z", engram_id))
        conn.commit()


def _make_extracted(*, inner_stmt_id: str, canonical_hash: str):
    """Construct an ExtractedStatement DTO where alice believes an inner Statement.

    object_kind = "statement" means the object is a reference to another
    Statement row.  object_value carries the referenced Statement's id.
    canonical_object_hash is the pre-computed hash that distinguishes one
    inner Statement from another — this is the field the ConflictProbe keys
    on, so it MUST differ when the inner Statements differ.

    All identity / predicate fields are held constant across the two writes so
    that IF the canonical_object_hash were accidentally identical, the
    ConflictProbe would see a collision and archive one of the rows (violating
    invariant 3).  The test thus checks both the hash difference AND the
    no-archival property as independent guards.
    """
    s = _core.ExtractedStatement()
    s.holder_id              = "alice"
    s.holder_tenant_id       = "default"
    s.holder_perspective     = _core.Perspective.FIRST_PERSON
    s.subject_kind           = "cognizer"
    s.subject_id             = "alice"
    s.predicate              = "believes"
    s.object_kind            = "statement"
    s.object_value           = inner_stmt_id   # id of the referenced Statement
    s.canonical_object_hash  = canonical_hash
    s.modality               = _core.Modality.BELIEVES
    s.polarity               = _core.Polarity.POS
    s.confidence             = 0.80
    s.observed_at            = "2026-05-25T10:00:00Z"
    s.source_hash            = "aabbcc"
    s.perceived_by           = ["alice"]
    return s


def _seed_inner_statement(rt, stmt_id: str) -> None:
    """Seed a minimal flat (nesting_depth=0) Statement row so that
    Bus::write with object_kind='statement' can look up the parent depth.

    P2.a makes nesting_depth load-bearing: StatementWriter calls
    compute_nesting_depth which does SELECT nesting_depth FROM statements
    WHERE id = object_value.  Without this seed the write would throw
    'parent statement not found'.
    """
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            "INSERT INTO statements("
            "  id, tenant_id, holder_id, holder_perspective,"
            "  subject_kind, subject_id, predicate, object_kind, object_value,"
            "  canonical_object_hash, canonical_object_hash_version,"
            "  modality, polarity, confidence, observed_at,"
            "  salience, affect_json, activation, last_accessed,"
            "  provenance, evidence_json, source_spans_json, perceived_by_json,"
            "  consolidation_state, review_status,"
            "  derived_from_json, derived_depth, nesting_depth,"
            "  created_at, updated_at"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                stmt_id, "default", "bob", "first_person",
                "cognizer", "bob", "knows", "str", "placeholder",
                "hash-placeholder", "v1",
                "believes", "pos", 0.9, "2026-05-25T09:00:00Z",
                0.0, "{}", 0.0, "2026-05-25T09:00:00Z",
                "user_input", "[]", "[]", "[]",
                "volatile", "approved",
                "[]", 0, 0,
                "2026-05-25T09:00:00Z", "2026-05-25T09:00:00Z",
            ))
        conn.commit()


def test_2nd_order_statement_hash_distinction(rt):
    """TC-Q3b-001 happy path — §15.3.1 2nd-order statement object invariants.

    Sequence:
      1. Seed two Engrams (one FK target per Bus::write call).
      2. Seed the two inner Statement rows that alice will reference
         (required since P2.a makes nesting_depth load-bearing: the writer
         looks up parent.nesting_depth before INSERT).
      3. Bus::write S1: alice believes (inner stmt = bob knows calculus).
      4. Bus::write S2: alice believes (inner stmt = bob knows physics).

    Invariants:
      1. Both writes return kind == "accepted".
      2. canonical_object_hash of S1 != canonical_object_hash of S2 in DB.
      3. Both rows are in a kept consolidation_state (volatile or consolidated);
         neither has been archived by the ConflictProbe.
    """
    _seed_engram(rt, "engram-calculus", "hash-calculus")
    _seed_engram(rt, "engram-physics",  "hash-physics")
    # P2.a: seed the inner statement rows so the nesting_depth lookup succeeds.
    _seed_inner_statement(rt, _INNER_ID_CALCULUS)
    _seed_inner_statement(rt, _INNER_ID_PHYSICS)
    bus = _core.Bus(rt.adapter)

    # Step 3: Write S1 — alice believes bob knows calculus.
    s1 = _make_extracted(inner_stmt_id=_INNER_ID_CALCULUS,
                         canonical_hash=_HASH_CALCULUS)
    out1 = bus.write(s1, "engram-calculus", "span-calculus", None)
    assert out1["kind"] == "accepted", \
        f"S1 write must be 'accepted', got {out1!r}"
    s1_id = out1["stmt_id"]

    # Step 4: Write S2 — alice believes bob knows physics (different inner stmt).
    s2 = _make_extracted(inner_stmt_id=_INNER_ID_PHYSICS,
                         canonical_hash=_HASH_PHYSICS)
    out2 = bus.write(s2, "engram-physics", "span-physics", None)
    assert out2["kind"] == "accepted", \
        f"S2 write must be 'accepted', got {out2!r}"
    s2_id = out2["stmt_id"]

    # Sanity: two distinct statement ids.
    assert s1_id != s2_id, "S1 and S2 must be stored as separate rows"

    # ── Assertions on the final DB state ──────────────────────────────────
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")

        row1 = conn.execute(
            "SELECT canonical_object_hash, consolidation_state "
            "FROM statements WHERE id = ?",
            (s1_id,)).fetchone()
        row2 = conn.execute(
            "SELECT canonical_object_hash, consolidation_state "
            "FROM statements WHERE id = ?",
            (s2_id,)).fetchone()

    assert row1 is not None, "S1 row must exist in DB"
    assert row2 is not None, "S2 row must exist in DB"

    s1_hash, s1_state = row1
    s2_hash, s2_state = row2

    # Invariant 2: hashes must differ — different inner Statements → different
    # canonical_object_hash → ConflictProbe sees them as unrelated.
    assert s1_hash != s2_hash, (
        f"canonical_object_hash must differ for distinct inner Statements; "
        f"both got {s1_hash!r}"
    )

    # Also confirm the stored hashes match what we supplied (no silent rewrite).
    assert s1_hash == _HASH_CALCULUS, \
        f"S1 canonical_object_hash mismatch: expected {_HASH_CALCULUS!r}, got {s1_hash!r}"
    assert s2_hash == _HASH_PHYSICS, \
        f"S2 canonical_object_hash mismatch: expected {_HASH_PHYSICS!r}, got {s2_hash!r}"

    # Invariant 3: both rows must be in a "kept" state (not archived).
    _KEPT = {"volatile", "consolidated"}
    assert s1_state in _KEPT, \
        f"S1 must not be archived; consolidation_state={s1_state!r}"
    assert s2_state in _KEPT, \
        f"S2 must not be archived; consolidation_state={s2_state!r}"
