"""
TC-FRONTIER-FIVE-WAY — CRITICAL #5 (08_cognizer)

Tests KnowledgeFrontier::visible_engrams_at 5-way set logic.

Design: does NOT depend on extractor v12 (Task 32) — uses raw SQL INSERT to
seed all 5 fact_kinds directly into cognizer_presence_log and
cognizer_frontier_facts, then calls visible_engrams_at and verifies the
union/except result.

Tables involved:
  cognizer_presence_log:
    id, tenant_id, cognizer_id, engram_id, observed_at, channel

  cognizer_frontier_facts:
    id, tenant_id, cognizer_id, statement_id, source_engram_id,
    fact_kind, asserted_at, metadata_json

  fact_kind values: explicit_told | accessible_source | membership
                    | explicit_not_told  (+ presence_log is its own source)

visible_engrams_at logic (per spec §13.1 + §6.5):
  UNION of:
    - presence_log.engram_id  (observed_at <= as_of)
    - frontier_facts WHERE fact_kind IN ('explicit_told','accessible_source')
          AND source_engram_id IS NOT NULL  AND asserted_at <= as_of
  EXCEPT:
    - frontier_facts WHERE fact_kind = 'explicit_not_told'
          AND source_engram_id IS NOT NULL  AND asserted_at <= as_of

  membership rows have NULL source_engram_id and are therefore EXCLUDED from
  the union (they are for group-level reasoning, not per-engram filtering).
"""
from __future__ import annotations

import sqlite3

import pytest

from starling import _core
from starling.cognizer import KnowledgeFrontier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter_and_conn(tmp_path):
    """Return (adapter, sqlite3.Connection) both pointing to the same on-disk db.

    The adapter is used for KnowledgeFrontier API calls; the raw connection is
    used for direct INSERT (no extractor dependency).
    """
    db_path = str(tmp_path / "frontier_test.db")
    adapter = _core.SqliteAdapter.open(db_path)
    raw = sqlite3.connect(db_path)
    yield adapter, raw
    raw.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_presence(
    raw: sqlite3.Connection,
    *,
    id: str,
    tenant: str,
    cognizer: str,
    engram: str,
    observed_at: str,
    channel: str = "default",
) -> None:
    raw.execute(
        "INSERT INTO cognizer_presence_log "
        "(id, tenant_id, cognizer_id, engram_id, observed_at, channel) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (id, tenant, cognizer, engram, observed_at, channel),
    )
    raw.commit()


def _insert_frontier_fact(
    raw: sqlite3.Connection,
    *,
    id: str,
    tenant: str,
    cognizer: str,
    fact_kind: str,
    statement_id: str | None = None,
    source_engram_id: str | None = None,
    asserted_at: str,
    metadata_json: str = "{}",
) -> None:
    raw.execute(
        "INSERT INTO cognizer_frontier_facts "
        "(id, tenant_id, cognizer_id, statement_id, source_engram_id, "
        "fact_kind, asserted_at, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            id,
            tenant,
            cognizer,
            statement_id,
            source_engram_id,
            fact_kind,
            asserted_at,
            metadata_json,
        ),
    )
    raw.commit()


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-01: empty DB → empty visible set
# ---------------------------------------------------------------------------


def test_empty_when_nothing_recorded(adapter_and_conn):
    """Fresh DB with no rows: visible_engrams_at returns an empty collection."""
    adapter, _raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)
    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert list(result) == []


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-02: presence_log rows → visible includes those engrams
# ---------------------------------------------------------------------------


def test_presence_log_only_returns_those_engrams(adapter_and_conn):
    """3 presence_log rows for alice → visible_engrams_at returns those 3 engrams."""
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    for i, eid in enumerate(["engram-P1", "engram-P2", "engram-P3"], 1):
        _insert_presence(
            raw,
            id=f"pres-{i}",
            tenant="default",
            cognizer="alice",
            engram=eid,
            observed_at="2026-05-01T00:00:00Z",
        )

    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert sorted(result) == ["engram-P1", "engram-P2", "engram-P3"]


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-03: explicit_told contributes source_engram_id to visible
# ---------------------------------------------------------------------------


def test_explicit_told_contributes_to_visible(adapter_and_conn):
    """frontier_facts with fact_kind='explicit_told' → visible includes those source_engram_ids."""
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    _insert_frontier_fact(
        raw,
        id="fact-et-1",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-1",
        source_engram_id="engram-ET1",
        asserted_at="2026-05-01T00:00:00Z",
    )
    _insert_frontier_fact(
        raw,
        id="fact-et-2",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-2",
        source_engram_id="engram-ET2",
        asserted_at="2026-05-01T00:00:00Z",
    )

    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert sorted(result) == ["engram-ET1", "engram-ET2"]


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-04: accessible_source contributes source_engram_id to visible
# ---------------------------------------------------------------------------


def test_accessible_source_contributes(adapter_and_conn):
    """frontier_facts with fact_kind='accessible_source' → visible includes those source_engram_ids."""
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    _insert_frontier_fact(
        raw,
        id="fact-as-1",
        tenant="default",
        cognizer="alice",
        fact_kind="accessible_source",
        source_engram_id="engram-AS1",
        asserted_at="2026-05-01T00:00:00Z",
    )
    _insert_frontier_fact(
        raw,
        id="fact-as-2",
        tenant="default",
        cognizer="alice",
        fact_kind="accessible_source",
        source_engram_id="engram-AS2",
        asserted_at="2026-05-01T00:00:00Z",
    )

    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert sorted(result) == ["engram-AS1", "engram-AS2"]


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-05: membership with NULL source_engram_id does NOT contribute
# ---------------------------------------------------------------------------


def test_membership_does_not_contribute_to_visible(adapter_and_conn):
    """membership rows have NULL source_engram_id (they record group_id, not engrams).

    The visible_engrams_at SQL filters with AND source_engram_id IS NOT NULL on
    the UNION side, so membership rows must NOT contribute to engram visibility.
    """
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    # membership row — NULL source_engram_id per spec
    _insert_frontier_fact(
        raw,
        id="fact-mb-1",
        tenant="default",
        cognizer="alice",
        fact_kind="membership",
        statement_id=None,
        source_engram_id=None,
        asserted_at="2026-05-01T00:00:00Z",
        metadata_json='{"group_id": "group-X"}',
    )

    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert list(result) == [], (
        "membership rows must NOT contribute to engram visibility "
        "(source_engram_id is NULL by design)"
    )


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-06: explicit_not_told subtracts from the union
# ---------------------------------------------------------------------------


def test_explicit_not_told_subtracts_from_union(adapter_and_conn):
    """Engram E in both explicit_told and explicit_not_told for alice → EXCLUDED from visible."""
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    # First assert alice was told about engram-E
    _insert_frontier_fact(
        raw,
        id="fact-told-E",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-told",
        source_engram_id="engram-E",
        asserted_at="2026-05-01T00:00:00Z",
    )
    # Also a second engram that stays visible
    _insert_frontier_fact(
        raw,
        id="fact-told-F",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-told-f",
        source_engram_id="engram-F",
        asserted_at="2026-05-01T00:00:00Z",
    )
    # Negate engram-E via explicit_not_told
    _insert_frontier_fact(
        raw,
        id="fact-neg-E",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_not_told",
        statement_id="stmt-neg",
        source_engram_id="engram-E",
        asserted_at="2026-05-02T00:00:00Z",
    )

    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert "engram-E" not in result, "explicit_not_told must remove engram-E from visible"
    assert "engram-F" in result, "engram-F (no negation) must remain visible"


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-07: full five-way combination
# ---------------------------------------------------------------------------


def test_five_way_full_combination(adapter_and_conn):
    """All relevant fact_kinds at once + presence_log; verify final visible set.

    Setup:
      presence_log:     engram-P
      explicit_told:    engram-ET  (stays)
      accessible_source: engram-AS (stays)
      membership:       NULL source_engram_id (does NOT add anything)
      explicit_not_told: engram-ET (negates explicit_told entry for engram-ET)

    Expected visible = {engram-P, engram-AS}
    (engram-ET is added by explicit_told then removed by explicit_not_told)
    """
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    _insert_presence(
        raw,
        id="pres-5way",
        tenant="default",
        cognizer="alice",
        engram="engram-P",
        observed_at="2026-05-01T00:00:00Z",
    )
    _insert_frontier_fact(
        raw,
        id="fact-5w-et",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-5w-et",
        source_engram_id="engram-ET",
        asserted_at="2026-05-01T00:00:00Z",
    )
    _insert_frontier_fact(
        raw,
        id="fact-5w-as",
        tenant="default",
        cognizer="alice",
        fact_kind="accessible_source",
        source_engram_id="engram-AS",
        asserted_at="2026-05-01T00:00:00Z",
    )
    _insert_frontier_fact(
        raw,
        id="fact-5w-mb",
        tenant="default",
        cognizer="alice",
        fact_kind="membership",
        source_engram_id=None,
        asserted_at="2026-05-01T00:00:00Z",
        metadata_json='{"group_id": "group-5W"}',
    )
    _insert_frontier_fact(
        raw,
        id="fact-5w-neg",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_not_told",
        statement_id="stmt-5w-neg",
        source_engram_id="engram-ET",
        asserted_at="2026-05-02T00:00:00Z",
    )

    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert sorted(result) == ["engram-AS", "engram-P"], (
        f"Expected [engram-AS, engram-P], got {sorted(result)}"
    )


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-08: as_of filters out later records
# ---------------------------------------------------------------------------


def test_as_of_filters_later_records(adapter_and_conn):
    """A presence_log row with observed_at AFTER as_of must not appear in visible."""
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    # Past row — should be visible
    _insert_presence(
        raw,
        id="pres-past",
        tenant="default",
        cognizer="alice",
        engram="engram-PAST",
        observed_at="2026-05-01T00:00:00Z",
    )
    # Future row — must be excluded
    _insert_presence(
        raw,
        id="pres-future",
        tenant="default",
        cognizer="alice",
        engram="engram-FUTURE",
        observed_at="2026-05-28T00:00:00Z",  # after as_of
    )

    result = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert "engram-PAST" in result
    assert "engram-FUTURE" not in result, (
        "Record with observed_at after as_of must be excluded"
    )

    # Also verify frontier_facts cutoff
    _insert_frontier_fact(
        raw,
        id="fact-past",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-past",
        source_engram_id="engram-FF-PAST",
        asserted_at="2026-05-01T00:00:00Z",
    )
    _insert_frontier_fact(
        raw,
        id="fact-future",
        tenant="default",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-future",
        source_engram_id="engram-FF-FUTURE",
        asserted_at="2026-05-28T00:00:00Z",  # after as_of
    )

    result2 = frontier.visible_engrams_at("default", "alice", "2026-05-27T00:00:00Z")
    assert "engram-FF-PAST" in result2
    assert "engram-FF-FUTURE" not in result2, (
        "frontier_fact with asserted_at after as_of must be excluded"
    )


# ---------------------------------------------------------------------------
# TC-FRONTIER-FIVE-WAY-09: tenant_id strict isolation
# ---------------------------------------------------------------------------


def test_tenant_id_strict_isolation(adapter_and_conn):
    """alice in tenant-a has visible engrams; querying tenant-b for alice returns empty."""
    adapter, raw = adapter_and_conn
    frontier = KnowledgeFrontier(adapter)

    # Seed alice's data under tenant-a only
    _insert_presence(
        raw,
        id="pres-ta-1",
        tenant="tenant-a",
        cognizer="alice",
        engram="engram-A1",
        observed_at="2026-05-01T00:00:00Z",
    )
    _insert_presence(
        raw,
        id="pres-ta-2",
        tenant="tenant-a",
        cognizer="alice",
        engram="engram-A2",
        observed_at="2026-05-01T00:00:00Z",
    )
    _insert_frontier_fact(
        raw,
        id="fact-ta-1",
        tenant="tenant-a",
        cognizer="alice",
        fact_kind="explicit_told",
        statement_id="stmt-ta-1",
        source_engram_id="engram-A3",
        asserted_at="2026-05-01T00:00:00Z",
    )

    result_a = frontier.visible_engrams_at("tenant-a", "alice", "2026-05-27T00:00:00Z")
    result_b = frontier.visible_engrams_at("tenant-b", "alice", "2026-05-27T00:00:00Z")

    assert sorted(result_a) == ["engram-A1", "engram-A2", "engram-A3"]
    assert list(result_b) == [], (
        "alice in tenant-b must not see tenant-a's engrams"
    )
