"""TC-CONFLICT-KEY-UNIQUE [P2.a CRITICAL #6] — canonical_conflict_key deduplication.

Spec §13.1 / §16.3-5: CONFLICTS_WITH edges must be deduplicated via the
partial UNIQUE index on (tenant_id, canonical_conflict_key) for conflicts_with
edges. When multiple statements share the same canonical_conflict_key, only one
conflicts_with edge must be persisted — subsequent inserts hit the UNIQUE
constraint and are silently dropped per §8.4.

This test drives the real Bus.write path (not raw SQL) so the ConflictProbe +
insert_statement_edge + UNIQUE catch all engage end-to-end.

Three acceptance scenarios:
  1. test_three_partial_overlaps_produce_one_edge — MAIN: 3 writes with the
     same canonical_conflict_key → exactly 1 conflicts_with edge in DB.
  2. test_distinct_conflict_keys_produce_multiple_edges — NEGATIVE: 2 writes
     with DIFFERENT (holder, subject, predicate, hash) tuples produce 2
     distinct edges (UNIQUE only constrains identical keys).
  3. test_supersedes_edges_unaffected_by_unique — GUARD: direct_contradiction
     → supersedes edges have NULL canonical_conflict_key and are unaffected by
     the UNIQUE constraint; both supersedes edges from a chain land independently.

Patterns mirror test_tc_new_conflict_severe.py (direct_contradiction end-to-end)
and test_p1_non_critical.py case 7 (partial_overlap with seed_consolidated_stmt).
"""
from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime
from starling.testing import mark_consolidated


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures and helpers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def rt(tmp_path):
    """File-backed Runtime for tests.

    Mirrors the canonical fixture from test_tc_q3b_001.py: build a real
    SqliteAdapter-backed Runtime at a tmp path, start it.  File-backed (not
    :memory:) so we can open a second stdlib sqlite3 connection to verify
    statement_edges without touching the in-memory adapter cache.
    """
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_engram(rt, engram_id: str, content_hash: str) -> None:
    """Seed a minimal Engram row via direct SQL.

    Follows the pattern from test_tc_q3b_001.py / test_tc_new_conflict_severe.py.
    Two distinct engrams are required per scenario because StatementWriter's
    chunk-level duplicate guard keys on
    (tenant_id, holder_id, predicate, canonical_object_hash, evidence_engram_id).
    Statements sharing every field except the evidence engram would be classified
    as chunk_duplicate and short-circuit before ConflictProbe ever runs.
    source_item_id is set to engram_id to avoid the UNIQUE constraint on
    (tenant_id, adapter_name, source_item_id, source_version, chunk_index).
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
             "2026-05-26T09:00:00Z", engram_id))
        conn.commit()


def _seed_consolidated_stmt(rt, stmt_id: str, polarity: str,
                            confidence: float, valid_from: str,
                            valid_to: str,
                            canonical_hash: str,
                            holder_id: str = "cog-self",
                            subject_id: str = "cog-bob",
                            predicate: str = "responsible_for") -> None:
    """Insert a CONSOLIDATED statement row directly for ConflictProbe to find.

    ConflictProbe's fetch_candidates() query requires consolidation_state in
    ('consolidated', 'archived'). We seed with 'consolidated' so the probe
    returns the row and classify() does not clamp to PartialOverlap on the
    'volatile' S_old guard.

    Using direct SQL (not Bus.write) so the seed is outside the bus_events
    audit trail and does not add noise to the events count assertions.
    """
    sql = (
        "INSERT INTO statements("
        "id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,"
        "polarity,confidence,observed_at,salience,affect_json,activation,"
        "last_accessed,provenance,consolidation_state,review_status,"
        "valid_from,valid_to,created_at,updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(sql, (
            stmt_id, "default", holder_id, "first_person",
            "cognizer", subject_id, predicate, "str", "auth",
            canonical_hash, "v1", "believes",
            polarity, confidence, "2026-05-26T09:00:00Z", 0.5, "{}", 1.0,
            "2026-05-26T09:00:00Z", "user_input", "consolidated", "approved",
            valid_from, valid_to,
            "2026-05-26T09:00:00Z", "2026-05-26T09:00:00Z",
        ))
        conn.commit()


def _make_partial_overlap_stmt(
    *,
    canonical_hash: str,
    valid_from: str,
    valid_to: str,
    source_hash: str,
    holder_id: str = "cog-self",
    subject_id: str = "cog-bob",
    predicate: str = "responsible_for",
) -> _core.ExtractedStatement:
    """Construct an ExtractedStatement for a partial_overlap scenario.

    The canonical_conflict_key is computed from:
        (holder_id, modality, subject_kind:subject_id, predicate,
         canonical_object_hash, interval_bytes, scope_bytes)
    so all fields above are held constant across the 3 writes to guarantee
    all three produce the SAME canonical_conflict_key.

    confidence=0.50 < kThetaSevere (0.6) so even with opposite polarity the
    ConflictProbe classify() cannot escalate to DirectContradiction — the
    floor is PartialOverlap (the test scenario we want).

    polarity=NEG with S_OLD=POS satisfies "opposite polarity" but since
    confidence < kThetaSevere neither both_above_theta branch fires.
    """
    s = _core.ExtractedStatement()
    s.holder_id              = holder_id
    s.holder_tenant_id       = "default"
    s.holder_perspective     = _core.Perspective.FIRST_PERSON
    s.subject_kind           = "cognizer"
    s.subject_id             = subject_id
    s.predicate              = predicate
    s.object_kind            = "str"
    s.object_value           = "auth"
    s.canonical_object_hash  = canonical_hash
    s.modality               = _core.Modality.BELIEVES
    s.polarity               = _core.Polarity.NEG   # opposite to S_OLD (POS)
    s.confidence             = 0.50                 # < kThetaSevere → PartialOverlap
    s.observed_at            = "2026-05-26T10:00:00Z"
    s.source_hash            = source_hash
    s.valid_from             = valid_from
    s.valid_to               = valid_to
    s.perceived_by           = [holder_id]
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Three partial_overlap writes → exactly 1 conflicts_with edge
# ─────────────────────────────────────────────────────────────────────────────

def test_three_partial_overlaps_produce_one_edge(rt):
    """TC-CONFLICT-KEY-UNIQUE main acceptance scenario — §16.3-5.

    Scenario:
      - Seed S_OLD (POS, conf=0.50, consolidated, interval [2026-05-01,
        2027-01-01)) so ConflictProbe can find it.
      - Write S1, S2, S3: all NEG, conf=0.50, same interval [2026-06-01,
        2026-12-31), same (holder, modality, subject, predicate, hash) →
        canonical_conflict_key is identical for all three.
      - Each write uses a distinct evidence_engram_id to bypass the
        chunk-level duplicate guard.

    Invariants:
      1. All three Bus.write calls return kind='accepted'.
      2. After 3 writes, exactly 1 conflicts_with edge exists in DB for
         tenant_id='default' — the UNIQUE partial index on
         (tenant_id, canonical_conflict_key) WHERE edge_kind='conflicts_with'
         AND canonical_conflict_key IS NOT NULL silently drops the 2nd and 3rd.
      3. That single edge has canonical_conflict_key IS NOT NULL.
      4. S_OLD remains consolidated (PartialOverlap does not archive it).
      5. No row was archived.
    """
    _HASH = "cccccc0303030303cccccc0303030303cccccc0303030303cccccc0303030303"

    # Seed S_OLD: POS, conf=0.50 (below kThetaSevere), wide interval so all
    # three new statements' [2026-06-01, 2026-12-31) overlap with it.
    _seed_consolidated_stmt(
        rt, "s-old-unique-test", "pos", 0.50,
        "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
        canonical_hash=_HASH,
    )

    # Seed 3 distinct engrams (bypass chunk-level duplicate guard).
    for i in range(3):
        _seed_engram(rt, f"engram-unique-{i}", f"hash-unique-{i}")

    bus = _core.Bus(rt.adapter)

    # Write S1, S2, S3 — all produce the same canonical_conflict_key.
    # Same (holder, modality, subject, predicate, hash, valid_from, valid_to)
    # → canonical_conflict_key is byte-for-byte identical.
    for i in range(3):
        stmt = _make_partial_overlap_stmt(
            canonical_hash=_HASH,
            valid_from="2026-06-01T00:00:00Z",
            valid_to="2026-12-31T00:00:00Z",
            source_hash=f"src-unique-{i}",
        )
        out = bus.write(stmt, f"engram-unique-{i}", f"span-unique-{i}", None)
        assert out["kind"] == "accepted", (
            f"S{i+1} write must be 'accepted', got {out!r}"
        )

    # ── DB assertions (second sqlite3 connection rules out adapter cache) ───
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")

        # Invariant 2: exactly 1 conflicts_with edge total for tenant_id='default'.
        n_cw = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE edge_kind='conflicts_with' AND tenant_id='default'"
        ).fetchone()[0]
        assert n_cw == 1, (
            f"expected exactly 1 conflicts_with edge (UNIQUE dedup), got {n_cw}"
        )

        # Invariant 3: the surviving edge has canonical_conflict_key IS NOT NULL.
        ck = conn.execute(
            "SELECT canonical_conflict_key FROM statement_edges "
            "WHERE edge_kind='conflicts_with' AND tenant_id='default'"
        ).fetchone()[0]
        assert ck is not None and ck != "", (
            f"surviving conflicts_with edge must have non-NULL canonical_conflict_key, "
            f"got {ck!r}"
        )

        # Invariant 4: S_OLD remains consolidated (PartialOverlap does not archive).
        old_state = conn.execute(
            "SELECT consolidation_state FROM statements WHERE id='s-old-unique-test'"
        ).fetchone()[0]
        assert old_state == "consolidated", (
            f"S_OLD must remain consolidated after partial_overlap, got {old_state!r}"
        )

        # Invariant 5: no statement was archived.
        n_archived = conn.execute(
            "SELECT COUNT(*) FROM statements "
            "WHERE consolidation_state='archived'"
        ).fetchone()[0]
        assert n_archived == 0, (
            f"no statement should be archived in a partial_overlap scenario, "
            f"got {n_archived}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Distinct canonical_conflict_keys → multiple edges (UNIQUE not violated)
# ─────────────────────────────────────────────────────────────────────────────

def test_distinct_conflict_keys_produce_multiple_edges(rt):
    """NEGATIVE: two partial_overlap pairs with distinct keys → 2 edges.

    The UNIQUE partial index is scoped to (tenant_id, canonical_conflict_key).
    When two writes have DIFFERENT canonical_conflict_keys (because they differ
    in subject_id, which is part of the conflict key computation), the UNIQUE
    constraint does not fire and both edges must be persisted.

    Scenario:
      - Scenario A: holder=cog-self, subject=cog-bob, hash=_HASH_A
      - Scenario B: holder=cog-self, subject=cog-carol, hash=_HASH_B
      Both have opposite polarity to their respective S_OLD (POS) and
      overlapping intervals → PartialOverlap → conflicts_with edge per pair.
      The canonical_conflict_key computation includes subject_id, so A and B
      have different keys → 2 distinct edges in DB.
    """
    _HASH_A = "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"
    _HASH_B = "bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222"

    # Seed two distinct S_OLDs (consolidated, POS, conf=0.50).
    _seed_consolidated_stmt(
        rt, "s-old-A", "pos", 0.50,
        "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
        canonical_hash=_HASH_A,
        subject_id="cog-bob",
    )
    _seed_consolidated_stmt(
        rt, "s-old-B", "pos", 0.50,
        "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
        canonical_hash=_HASH_B,
        subject_id="cog-carol",
    )

    # Seed 2 engrams (one per write).
    _seed_engram(rt, "engram-dk-A", "hash-dk-A")
    _seed_engram(rt, "engram-dk-B", "hash-dk-B")

    bus = _core.Bus(rt.adapter)

    # Write S_A (conflicts with s-old-A).
    stmt_a = _make_partial_overlap_stmt(
        canonical_hash=_HASH_A,
        valid_from="2026-06-01T00:00:00Z",
        valid_to="2026-12-31T00:00:00Z",
        source_hash="src-dk-A",
        subject_id="cog-bob",
    )
    out_a = bus.write(stmt_a, "engram-dk-A", "span-dk-A", None)
    assert out_a["kind"] == "accepted", f"write A must be accepted, got {out_a!r}"

    # Write S_B (conflicts with s-old-B, different subject → different key).
    stmt_b = _make_partial_overlap_stmt(
        canonical_hash=_HASH_B,
        valid_from="2026-06-01T00:00:00Z",
        valid_to="2026-12-31T00:00:00Z",
        source_hash="src-dk-B",
        subject_id="cog-carol",
    )
    out_b = bus.write(stmt_b, "engram-dk-B", "span-dk-B", None)
    assert out_b["kind"] == "accepted", f"write B must be accepted, got {out_b!r}"

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")

        # Both edges must exist (distinct canonical_conflict_keys → no dedup).
        n_cw = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE edge_kind='conflicts_with' AND tenant_id='default'"
        ).fetchone()[0]
        assert n_cw == 2, (
            f"expected 2 conflicts_with edges for distinct conflict keys, got {n_cw}"
        )

        # Each edge has a distinct (non-NULL) canonical_conflict_key.
        keys = conn.execute(
            "SELECT DISTINCT canonical_conflict_key FROM statement_edges "
            "WHERE edge_kind='conflicts_with' AND tenant_id='default'"
        ).fetchall()
        assert len(keys) == 2, (
            f"expected 2 distinct canonical_conflict_key values, got {keys!r}"
        )
        for (k,) in keys:
            assert k is not None and k != "", (
                f"each conflicts_with edge must have non-NULL key, got {k!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: supersedes edges (NULL canonical_conflict_key) unaffected by UNIQUE
# ─────────────────────────────────────────────────────────────────────────────

def test_supersedes_edges_unaffected_by_unique(rt):
    """GUARD: direct_contradiction → supersedes edge has NULL canonical_conflict_key.

    The UNIQUE partial index filters on:
        edge_kind = 'conflicts_with' AND canonical_conflict_key IS NOT NULL
    Supersedes edges have NULL canonical_conflict_key and are outside the
    partial index entirely — they must not be affected by the UNIQUE constraint.

    Scenario:
      - Seed S_OLD_A (POS, conf=0.85, consolidated).
      - Write S_NEW_A (NEG, conf=0.85, overlapping interval) → both above
        kThetaSevere + opposite polarity + S_OLD_A consolidated → direct_contradiction
        → atomic 4-item commit: S_OLD_A archived, supersedes edge inserted.
      - Seed S_OLD_B (POS, conf=0.85, consolidated) with a DIFFERENT hash.
      - Write S_NEW_B (NEG, conf=0.85) → second supersedes edge.

    Invariants:
      1. Both Bus.write calls return kind='accepted'.
      2. Exactly 0 conflicts_with edges.
      3. Exactly 2 supersedes edges.
      4. Both supersedes edges have NULL canonical_conflict_key (the UNIQUE
         index does not cover supersedes; NULL values are excluded anyway).
    """
    _HASH_A = "dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444"
    _HASH_B = "eeee5555eeee5555eeee5555eeee5555eeee5555eeee5555eeee5555eeee5555"

    # Seed pair A (POS, conf=0.85, consolidated).
    _seed_consolidated_stmt(
        rt, "s-old-sup-A", "pos", 0.85,
        "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
        canonical_hash=_HASH_A,
        subject_id="cog-x",
    )
    # Seed pair B (POS, conf=0.85, consolidated, different hash+subject).
    _seed_consolidated_stmt(
        rt, "s-old-sup-B", "pos", 0.85,
        "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
        canonical_hash=_HASH_B,
        subject_id="cog-y",
    )

    # Seed 2 engrams.
    _seed_engram(rt, "engram-sup-A", "hash-sup-A")
    _seed_engram(rt, "engram-sup-B", "hash-sup-B")

    bus = _core.Bus(rt.adapter)

    # Write S_NEW_A: NEG, conf=0.85 → both above kThetaSevere + opposite polarity
    # + S_OLD_A consolidated → direct_contradiction → atomic SUPERSEDES path.
    s_new_a = _make_partial_overlap_stmt(
        canonical_hash=_HASH_A,
        valid_from="2026-06-01T00:00:00Z",
        valid_to="2026-12-31T00:00:00Z",
        source_hash="src-sup-A",
        subject_id="cog-x",
    )
    s_new_a.confidence = 0.85   # override to above kThetaSevere
    out_a = bus.write(s_new_a, "engram-sup-A", "span-sup-A", None)
    assert out_a["kind"] == "accepted", f"S_NEW_A must be accepted, got {out_a!r}"

    # Write S_NEW_B: same but for pair B.
    s_new_b = _make_partial_overlap_stmt(
        canonical_hash=_HASH_B,
        valid_from="2026-06-01T00:00:00Z",
        valid_to="2026-12-31T00:00:00Z",
        source_hash="src-sup-B",
        subject_id="cog-y",
    )
    s_new_b.confidence = 0.85   # above kThetaSevere
    out_b = bus.write(s_new_b, "engram-sup-B", "span-sup-B", None)
    assert out_b["kind"] == "accepted", f"S_NEW_B must be accepted, got {out_b!r}"

    s_new_a_id = out_a["stmt_id"]
    s_new_b_id = out_b["stmt_id"]

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")

        # Invariant 2: no conflicts_with edges (direct_contradiction takes
        # the atomic SUPERSEDES path, not the PartialOverlap path).
        n_cw = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE edge_kind='conflicts_with'"
        ).fetchone()[0]
        assert n_cw == 0, (
            f"direct_contradiction must not produce conflicts_with edges, got {n_cw}"
        )

        # Invariant 3: exactly 2 supersedes edges.
        n_sup = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE edge_kind='supersedes'"
        ).fetchone()[0]
        assert n_sup == 2, (
            f"expected exactly 2 supersedes edges, got {n_sup}"
        )

        # Invariant 4: both supersedes edges have NULL canonical_conflict_key.
        n_null_key = conn.execute(
            "SELECT COUNT(*) FROM statement_edges "
            "WHERE edge_kind='supersedes' AND canonical_conflict_key IS NULL"
        ).fetchone()[0]
        assert n_null_key == 2, (
            f"both supersedes edges must have NULL canonical_conflict_key, "
            f"got {n_null_key} with NULL key (out of 2 total)"
        )

        # Also confirm both S_OLDs were archived (direct_contradiction path).
        n_archived = conn.execute(
            "SELECT COUNT(*) FROM statements "
            "WHERE consolidation_state='archived'"
        ).fetchone()[0]
        assert n_archived == 2, (
            f"both S_OLD rows must be archived after direct_contradiction, "
            f"got {n_archived}"
        )
