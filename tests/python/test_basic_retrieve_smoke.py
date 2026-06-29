"""§14.1 minimal-variant smoke (P1 retrieve gate, CRITICAL).

Per system_design.md line 1663 + §14.1 — this is the M0.6 ship gate.

Scenario (Alice's perspective):
  Alice 在 4/15 群聊宣布 Bob 不再负责 auth, Carol 接手. The narrative carries
  two of Alice's beliefs about Bob:
    S_old: Bob responsible_for "auth"             valid 2026-03-01..2026-04-15
    S_new: Bob responsible_for "auth_owner_change" valid 2026-04-15..open

Wire-up:
  1. Seed two engrams (one per statement) via direct SQL — see §15.3.2 chunk
     duplicate guard, mirrored from test_tc_new_conflict_severe.py.
  2. Bus.write(S_old) — lands VOLATILE.
  3. testing.mark_consolidated(S_old) — flips VOLATILE → CONSOLIDATED.
  4. Bus.write(S_new) — different object_value gives a different
     canonical_object_hash so the chunk-dup guard does not collapse them.
     The pair shares (holder, subject, predicate) so basic_retrieve will
     match both; the time anchor at 2026-04-16 is what excludes S_old.
  5. basic_retrieve at 2026-04-16 returns only S_new.

Asserts the §"RetrievalReceipt（P1 最小字段加粗）" minimum field contract +
the §"statement.recalled emit 契约" event-emission requirement.

This smoke does NOT route through the live Extractor — that is M0.4
territory and orthogonal to the retrieval gate. Bus.write + the
testing.mark_consolidated helper are the spec-blessed shortcut.

The CI static scan (scripts/ci_static_scan.py) bans starling.testing
imports from prod entrypoints; tests/python is in the allowed-roots list,
so the import of `mark_consolidated` is intentional and safe.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from starling import _core, runtime
from starling.retrieval import basic_retrieve
from starling.testing import (  # NOLINT(starling-testing-isolation)
    mark_consolidated,
)


@pytest.fixture
def rt(tmp_path):
    """File-backed Runtime for tests.

    File-backed (not :memory:) because §14.1 specifically tests the same
    persistence path the M0.5 SUPERSEDES atomic transaction exercises, and
    we read back from a second stdlib sqlite3 connection to count
    statement.recalled events — which only works against a real path.
    """
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_engram(rt, engram_id: str, content_hash: str) -> None:
    """Seed a minimal Engram row via direct SQL.

    Mirrors test_tc_new_conflict_severe.py::_seed_engram exactly. Two
    distinct engrams are required because StatementWriter's chunk-level
    duplicate guard (§15.3.2 — `find_existing_in_chunk`) keys on
    `(tenant_id, holder_id, predicate, canonical_object_hash,
    evidence_engram_id)`. S_old and S_new differ on canonical_object_hash
    (different object_value), so attaching them to the same engram would
    actually be safe — but mirroring the M0.5 pattern keeps the seed shape
    representative of production extractor output (each extraction call
    associates with a distinct chunk Engram).

    `chunk_index` defaults to 0 here; distinct `source_item_id` keeps the
    migration-0003 UNIQUE(tenant_id, adapter_name, source_item_id,
    source_version, chunk_index) constraint satisfied across the two seeds.
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
             "2026-04-15T09:00:00Z", engram_id))
        conn.commit()


def _build_statement(
    *,
    object_value: str,
    canonical_object_hash: str,
    valid_from: str,
    valid_to,  # str | None — None encodes the open upper bound (NULL in SQL).
    observed_at: str,
    source_hash: str,
):
    """Construct an ExtractedStatement for the smoke.

    All identity / predicate fields are held constant across S_old and
    S_new (holder=alice, subject=bob, predicate=responsible_for) so a
    single basic_retrieve(holder=alice, subject=bob, predicate=...) call
    sees both candidates. object_value (and therefore
    canonical_object_hash) differs so the chunk-dup guard does not fire.

    `valid_to=None` is the canonical "open upper bound" encoding: the
    binding stores it as `optional<string>::nullopt` ⇒ SQL NULL ⇒ the
    retrieval predicate `(valid_to IS NULL OR valid_to > ?)` always
    evaluates true for that branch. Passing an empty string here would
    make the lexical comparison `'' > '2026-04-16T...'` always false and
    incorrectly exclude the row.
    """
    s = _core.ExtractedStatement()
    s.holder_id          = "alice"
    s.holder_tenant_id   = "default"
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind       = "cognizer"
    s.subject_id         = "bob"
    s.predicate          = "responsible_for"
    s.object_kind        = "str"
    s.object_value       = object_value
    s.canonical_object_hash = canonical_object_hash
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = _core.Polarity.POS
    s.confidence         = 0.9
    s.observed_at        = observed_at
    s.source_hash        = source_hash
    s.valid_from         = valid_from
    s.valid_to           = valid_to
    s.perceived_by       = ["alice"]
    return s


def test_smoke_returns_only_s_new(rt):
    """End-to-end: only the post-announcement statement is returned at 4/16.

    Asserts every §"RetrievalReceipt（P1 最小字段加粗）" minimum field plus
    the §"statement.recalled emit 契约" event count. If any of these
    drift, the M0.6 retrieve gate is broken and shipping is blocked.
    """
    bus = _core.Bus(rt.adapter)

    # 1. Seed two distinct engrams (one per statement). See _seed_engram
    #    docstring + test_tc_new_conflict_severe.py for the chunk-dup guard
    #    rationale.
    _seed_engram(rt, "engram-old", "hash-old")
    _seed_engram(rt, "engram-new", "hash-new")

    # 2. Bus.write S_old: Bob responsible_for "auth", valid 2026-03-01..2026-04-15.
    s_old = _build_statement(
        object_value="auth",
        canonical_object_hash="aa" * 32,
        valid_from="2026-03-01T00:00:00Z",
        valid_to="2026-04-15T00:00:00Z",
        observed_at="2026-03-01T09:00:00Z",
        source_hash="smoke-source-old",
    )
    out_old = bus.write(s_old, "engram-old", "smoke-span-old", None)
    assert out_old["kind"] == "accepted", \
        f"S_old write must be 'accepted', got {out_old!r}"
    s_old_id = out_old["stmt_id"]

    # 3. Flip S_old VOLATILE → CONSOLIDATED so it would otherwise pass the
    #    retrieval consolidation_state filter — confirming that what excludes
    #    it at 4/16 is the time-anchor predicate, not the state filter.
    assert mark_consolidated(rt.adapter, s_old_id, "default") is True, \
        "mark_consolidated should transition VOLATILE → CONSOLIDATED"

    # 4. Bus.write S_new: Bob responsible_for "auth_owner_change", valid
    #    2026-04-15..open. Different object_value ⇒ different
    #    canonical_object_hash ⇒ chunk-dup guard does not collapse the pair.
    s_new = _build_statement(
        object_value="auth_owner_change",
        canonical_object_hash="bb" * 32,
        valid_from="2026-04-15T00:00:00Z",
        valid_to=None,
        observed_at="2026-04-15T09:00:00Z",
        source_hash="smoke-source-new",
    )
    out_new = bus.write(s_new, "engram-new", "smoke-span-new", None)
    assert out_new["kind"] == "accepted", \
        f"S_new write must be 'accepted', got {out_new!r}"
    s_new_id = out_new["stmt_id"]

    # 4b. Flip S_new VOLATILE → CONSOLIDATED so it passes the retrieval
    #     consolidation_state filter (`IN ('consolidated','archived')`).
    #     Bus.write lands new statements as VOLATILE; the basic_retrieve
    #     SELECT excludes VOLATILE rows by design (see test_basic_retrieve
    #     _filters.py::test_volatile_excluded). In production this transition
    #     happens via the consolidator; in the smoke we drive it directly via
    #     the testing helper, mirroring test_basic_retrieve_receipt.py.
    assert mark_consolidated(rt.adapter, s_new_id, "default") is True, \
        "mark_consolidated should transition S_new VOLATILE → CONSOLIDATED"

    # 5. basic_retrieve at 2026-04-16 — only S_new should come back.
    #    S_old is excluded by the time-anchor predicate (valid_to=2026-04-15
    #    < as_of), S_new is included (valid_from=2026-04-15 <= as_of and
    #    valid_to is open).
    result = basic_retrieve(
        rt.adapter,
        tenant_id="default",
        holder="alice",
        subject="bob",
        predicate="responsible_for",
        as_of=datetime(2026, 4, 16, tzinfo=timezone.utc),
    )

    # ── Row-level assertions ────────────────────────────────────────────
    assert len(result.rows) == 1, \
        f"expected exactly S_new, got rows={[r.id for r in result.rows]!r}"
    row = result.rows[0]
    assert row.id == s_new_id, \
        f"returned row must be S_new ({s_new_id}), got {row.id}"
    # S_new was flipped to CONSOLIDATED in step 4b. The retrieval SELECT's
    # `consolidation_state IN ('consolidated','archived')` predicate is
    # what allows it through; the spec only requires NOT 'archived' for a
    # positive recall, but in practice consolidated is what we will see.
    assert row.consolidation_state in ("consolidated", "archived"), \
        f"S_new state must be CONSOLIDATED or ARCHIVED, got {row.consolidation_state!r}"

    # ── §"RetrievalReceipt（P1 最小字段加粗）" minimum field assertions ──
    receipt = result.receipt
    assert receipt.sufficiency_status == "SUFFICIENT", \
        f"one returned row ⇒ SUFFICIENT, got {receipt.sufficiency_status!r}"
    assert receipt.evidence_erased_count == 0, \
        f"no engrams were erased, expected 0, got {receipt.evidence_erased_count}"
    assert receipt.trace_id, "trace_id must be auto-populated when caller omits"
    assert receipt.query_id, "query_id must be auto-populated when caller omits"
    assert receipt.candidate_counts.fetched == 1, \
        f"SELECT should match exactly S_new, got fetched={receipt.candidate_counts.fetched}"
    assert receipt.candidate_counts.returned == 1, \
        f"S_new should pass the post-filter, got returned={receipt.candidate_counts.returned}"

    # ── §"statement.recalled emit 契約" — exactly one event for one recall ──
    # Mirrors test_tc_new_conflict_severe.py's bus_events count pattern: open
    # a second stdlib sqlite3 connection to rule out any in-memory adapter
    # cache. Per 13_retrieval.md, statement.recalled is emitted outside the
    # retrieval transaction once per (key, 2s window) bucket.
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        n_recalled = conn.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type=?",
            ("statement.recalled",)).fetchone()[0]
    assert n_recalled == 1, \
        f"expected exactly 1 statement.recalled event, got {n_recalled}"
