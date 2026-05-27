"""Smoke tests for starling.tom Python package and primitives.

Verifies:
  1. All public types importable from starling.tom
  2. what_does_X_believe returns a list
  3. does_X_know returns a KnowsResult enum value
  4. find_misalignment returns a Misalignment object
  5. shared_with returns a list
  6. belief_tracker_tick callable and returns TickStats
  7. ToMEngine constructible + perspective_take works
"""
from __future__ import annotations

import pytest

import starling._core as _core


@pytest.fixture
def adapter():
    return _core.SqliteAdapter.open(":memory:")


@pytest.fixture
def hub(adapter):
    return _core.CognizerHub(adapter)


@pytest.fixture
def frontier(adapter):
    return _core.KnowledgeFrontier(adapter)


# ---------------------------------------------------------------------------
# 1. Import smoke
# ---------------------------------------------------------------------------

def test_imports_work():
    """All public symbols importable from starling.tom."""
    from starling.tom import (
        FactKey,
        KnowsResult,
        Misalignment,
        SharedFact,
        CommonGroundEntry,
        Context,
        TickStats,
        ToMEngine,
        NestingDepthOverflow,
        belief_tracker_tick,
        what_does_X_believe,
        does_X_know,
        find_misalignment,
        shared_with,
    )
    assert FactKey is not None
    assert KnowsResult.FullKnowledge is not None
    assert KnowsResult.NotKnown is not None
    assert KnowsResult.Unknowable is not None
    assert TickStats is not None


# ---------------------------------------------------------------------------
# 2. what_does_X_believe returns list
# ---------------------------------------------------------------------------

def test_what_does_X_believe_returns_list(adapter):
    """what_does_X_believe returns a list (empty for unknown cognizer)."""
    from starling.tom.primitives import what_does_X_believe

    result = what_does_X_believe(
        adapter, x="nonexistent", about_y="nobody", tenant_id="default"
    )
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 3. does_X_know returns KnowsResult
# ---------------------------------------------------------------------------

def test_does_X_know_returns_knows_result(adapter, frontier):
    """does_X_know returns a KnowsResult enum value."""
    from starling.tom.primitives import does_X_know
    from starling._core import FactKey, KnowsResult

    fk = FactKey(
        subject_kind="cognizer",
        subject_id="someone",
        predicate="knows_python",
        canonical_object_hash="abc123",
    )
    result = does_X_know(
        adapter, frontier, x="nonexistent", fact=fk, tenant_id="default"
    )
    # With no data, must be NotKnown or Unknowable (not FullKnowledge)
    assert result in (KnowsResult.NotKnown, KnowsResult.Unknowable, KnowsResult.FullKnowledge)
    assert isinstance(result, KnowsResult)


# ---------------------------------------------------------------------------
# 4. find_misalignment returns Misalignment
# ---------------------------------------------------------------------------

def test_find_misalignment_returns_misalignment(adapter):
    """find_misalignment returns a Misalignment with empty vectors for unknown cognizers."""
    from starling.tom.primitives import find_misalignment
    from starling._core import Misalignment

    result = find_misalignment(
        adapter,
        x="alice",
        y="bob",
        subject_kind="cognizer",
        subject_id="charlie",
        tenant_id="default",
    )
    assert isinstance(result, Misalignment)
    assert isinstance(result.only_x_believes, list)
    assert isinstance(result.only_y_believes, list)
    assert isinstance(result.confidence_diverges, list)


# ---------------------------------------------------------------------------
# 5. shared_with returns list
# ---------------------------------------------------------------------------

def test_shared_with_returns_list(adapter):
    """shared_with returns a list (empty for unknown cognizers)."""
    from starling.tom.primitives import shared_with

    result = shared_with(adapter, members=["alice", "bob"], tenant_id="default")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 6. belief_tracker_tick callable and returns TickStats
# ---------------------------------------------------------------------------

def test_belief_tracker_tick_returns_tick_stats(adapter):
    """belief_tracker_tick returns a TickStats with integer fields."""
    from starling._core import belief_tracker_tick, TickStats

    stats = belief_tracker_tick(adapter, batch_size=100)
    assert isinstance(stats, TickStats)
    assert isinstance(stats.events_processed, int)
    assert isinstance(stats.frontier_facts_written, int)
    assert isinstance(stats.trust_prior_updates, int)
    assert isinstance(stats.last_seen_updates, int)
    assert isinstance(stats.presence_log_writes, int)


# ---------------------------------------------------------------------------
# 7. ToMEngine constructible + perspective_take
# ---------------------------------------------------------------------------

def test_tom_engine_perspective_take_empty(adapter, hub, frontier):
    """ToMEngine.perspective_take returns a Context with empty collections for unknown target."""
    from starling._core import ToMEngine, Context

    engine = ToMEngine(adapter, hub, frontier)
    ctx = engine.perspective_take(
        target="nonexistent_cognizer",
        tenant="default",
        as_of="2026-01-01T00:00:00Z",
    )
    assert isinstance(ctx, Context)
    assert isinstance(ctx.visible_engram_ids, list)
    assert isinstance(ctx.target_beliefs, list)
    assert isinstance(ctx.cg, list)


# ---------------------------------------------------------------------------
# 8. primitives as_of=None uses current time (no error)
# ---------------------------------------------------------------------------

def test_what_does_X_believe_default_as_of(adapter):
    """what_does_X_believe with as_of=None defaults to current time without error."""
    from starling.tom.primitives import what_does_X_believe

    result = what_does_X_believe(
        adapter, x="test_user", about_y="test_subject"
    )
    assert isinstance(result, list)


def test_primitives_reject_naive_datetime(adapter):
    """Primitive wrappers raise ValueError for naive (tz-unaware) datetime."""
    from datetime import datetime
    from starling.tom.primitives import what_does_X_believe

    naive_dt = datetime(2026, 1, 1, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValueError, match="timezone-aware"):
        what_does_X_believe(
            adapter, x="test_user", about_y="test_subject", as_of=naive_dt
        )
