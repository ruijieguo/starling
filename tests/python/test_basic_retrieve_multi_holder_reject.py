"""Argument-validation tests for `starling.retrieval.basic_retrieve`.

The Python facade rejects multi-holder lists, naive datetimes, and
non-FACT_LOOKUP intents BEFORE reaching the C++ layer (see
13_retrieval.md §"P1 basic_retrieve 闭环"). These tests pin that contract
so future refactors can't silently broaden the surface — every reject
case here corresponds to a bullet in the spec's negative list.

Uses `:memory:` SQLite (per project convention; no seeding required since
all calls must raise before reaching the SELECT).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from starling import _core
from starling.retrieval import basic_retrieve


@pytest.fixture
def adapter():
    # SqliteAdapter::open runs migrations during open() — see
    # include/starling/persistence/sqlite_adapter.hpp:11. So a `:memory:`
    # adapter has the full schema applied immediately and is ready for use.
    # No seeding needed — all tests below assert the call rejects before
    # touching the SELECT.
    return _core.SqliteAdapter.open(":memory:")


def _call(adapter, **overrides):
    """Drive basic_retrieve with caller-supplied overrides on top of a
    minimal valid kwargs set. The defaults below DO pass validation, so a
    test that overrides only the field under test isolates that one
    rejection rule."""
    defaults = dict(
        tenant_id="t1",
        holder="alice",
        subject="bob",
        predicate="responsible_for",
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return basic_retrieve(adapter, **defaults)


def test_reject_list_holder(adapter):
    """List-shaped holder must raise — P1 ships single-holder only.

    Spec: 13_retrieval.md §"P1 basic_retrieve 闭环" rejects multi-holder
    plans. The error message must mention 'multi-holder' so callers who
    grep their logs find the right §.
    """
    with pytest.raises(ValueError, match="multi-holder"):
        _call(adapter, holder=["alice", "carol"])


def test_reject_tuple_holder(adapter):
    """Tuple-shaped holder treated identically to list (both are sequences).

    A regression that only checks `isinstance(holder, list)` would pass
    the list test but fail this one — pinning both shapes keeps the guard
    on `(list, tuple)` rather than just `list`.
    """
    with pytest.raises(ValueError, match="multi-holder"):
        _call(adapter, holder=("alice",))


def test_reject_empty_holder(adapter):
    """Empty string holder is rejected as `not a non-empty string`.

    Distinct from the multi-holder case — this exercises the second
    `isinstance(holder, str) or not holder` guard, which catches both
    empty string and non-string non-sequence values.
    """
    with pytest.raises(ValueError, match="holder"):
        _call(adapter, holder="")


def test_reject_non_fact_lookup_intent(adapter):
    """Anything other than FACT_LOOKUP raises — only one P1 intent ships.

    The 8 other intents (BELIEF_OF_OTHER, META_BELIEF, HISTORY,
    COMMITMENT_DUE, PREFERENCE, NORM_LOOKUP, COMMON_GROUND, ABSTAIN_CHECK)
    are spec'd at 13_retrieval.md §"QueryIntent 枚举（9 种）" but rejected
    at runtime in P1.
    """
    with pytest.raises(ValueError, match="FACT_LOOKUP"):
        _call(adapter, intent="BELIEF_OF_OTHER")


def test_reject_naive_datetime(adapter):
    """Naive datetime (no tzinfo) is rejected — UTC must be explicit.

    The C++ layer canonicalizes to ISO-8601 'Z' suffix; passing a naive
    datetime would silently apply local-clock offset, which the spec
    explicitly forbids (the receipt's filters_applied.as_of must match
    a canonical UTC string).
    """
    with pytest.raises(ValueError, match="timezone-aware"):
        _call(adapter, as_of=datetime(2026, 4, 15))  # no tzinfo


def test_reject_empty_tenant(adapter):
    """Empty tenant_id is rejected — multi-tenant isolation depends on it.

    The C++ BasicRetriever::run also rejects an empty tenant_id (see
    include/starling/retrieval/basic_retriever.hpp:46), but the Python
    facade rejects first to keep the error message tied to the spec §.
    """
    with pytest.raises(ValueError, match="tenant_id"):
        _call(adapter, tenant_id="")
