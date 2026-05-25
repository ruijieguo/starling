"""Receipt-shape tests for `starling.retrieval.basic_retrieve`.

Pins the §"RetrievalReceipt（P1 最小字段加粗）" contract: trace_id and
query_id round-trip from the caller, candidate_counts populate from the
SELECT, evidence_erased_count starts at 0, sufficiency_status is one of
the four enum names, and filters_applied lists the ten entries that
mirror the SQL filter shape (the tenth is `holder_perspective`, recorded
as "any" when unconstrained per 13_retrieval.md:291).

Uses `:memory:` SQLite throughout. Statements are seeded via the same
public path production extractors will use: append_evidence -> Bus.write
(VOLATILE) -> testing.mark_consolidated (CONSOLIDATED). This keeps the
test from depending on private SQL knowledge of the statements table.

The CI static scan (scripts/ci_static_scan.py) bans starling.testing
imports from prod entrypoints; tests/python is in the allowed-roots
list, so the import here is intentional and safe.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from starling import _core
from starling.bus.append_evidence import BusFacade
from starling.evidence import (
    EngramRetentionMode,
    PrivacyClass,
    for_user_input,
)
from starling.retrieval import basic_retrieve
from starling.testing import mark_consolidated  # NOLINT(starling-testing-isolation)


@pytest.fixture
def adapter():
    """`:memory:` SqliteAdapter with migrations applied at open() time.

    SqliteAdapter::open runs migrations to the latest version during
    construction (see include/starling/persistence/sqlite_adapter.hpp:11),
    so no extra setup is needed. `:memory:` keeps the test ephemeral and
    avoids any /tmp/*.db convention clash.
    """
    return _core.SqliteAdapter.open(":memory:")


def _seed_engram(adapter, *, tenant_id: str = "default") -> str:
    """Append a single user_input engram and return its id.

    BusFacade.append_evidence is the production-path way to land an engram
    row. We don't reach into raw SQL here — partly because `:memory:`
    can't be opened twice from stdlib sqlite3, partly because using the
    real path catches binding regressions for free.
    """
    bus = BusFacade(adapter)
    inp = for_user_input(
        tenant_id=tenant_id,
        adapter_name="test_basic_retrieve_receipt",
        adapter_version="1.0.0",
        source_item_id="seed-msg-1",
        source_version="1",
        payload_bytes=b"seed payload for retrieval receipt test",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
    )
    outcome = bus.append_evidence(inp)
    assert outcome["kind"] == "accepted", \
        f"engram seed must succeed, got {outcome!r}"
    return outcome["engram_ref"].id


def _seed_statement(adapter, engram_id: str, *, tenant_id: str = "default") -> str:
    """Bus.write a single ExtractedStatement and flip it CONSOLIDATED.

    The fields below mirror the §"basic_retrieve（P1 闭环）" SELECT shape:
      - subject_kind='cognizer', subject_id='bob', predicate='responsible_for'
      - holder_id='alice', tenant_id matches the fixture's adapter
      - polarity=POS, modality=BELIEVES, confidence=0.9
      - valid_from='2026-04-01', valid_to='2026-12-31' so the test's
        as_of='2026-04-15T00:00:00Z' falls inside the validity interval
    Returns the new statement's id.
    """
    s = _core.ExtractedStatement()
    s.holder_id          = "alice"
    s.holder_tenant_id   = tenant_id
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind       = "cognizer"
    s.subject_id         = "bob"
    s.predicate          = "responsible_for"
    s.object_kind        = "str"
    s.object_value       = "auth"
    s.canonical_object_hash = (
        "deadbeef01234567deadbeef01234567"
        "deadbeef01234567deadbeef01234567"
    )
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = _core.Polarity.POS
    s.confidence         = 0.9
    s.observed_at        = "2026-04-14T09:00:00Z"
    s.source_hash        = "abc123"
    s.valid_from         = "2026-04-01T00:00:00Z"
    s.valid_to           = "2026-12-31T00:00:00Z"
    s.perceived_by       = ["alice"]

    bus = _core.Bus(adapter)
    out = bus.write(s, engram_id, "span-1", None)
    assert out["kind"] == "accepted", f"Bus.write must accept, got {out!r}"
    stmt_id = out["stmt_id"]

    # Flip volatile -> consolidated so the basic_retrieve filter
    # (consolidation_state IN ('consolidated','archived')) accepts it.
    ok = mark_consolidated(adapter, stmt_id, tenant_id)
    assert ok is True, "mark_consolidated must transition VOLATILE -> CONSOLIDATED"
    return stmt_id


def test_minimum_p1_fields_present(adapter):
    """One consolidated, in-window, non-erased row -> SUFFICIENT receipt.

    Asserts every §"RetrievalReceipt（P1 最小字段加粗）" minimum field:
      - trace_id / query_id echo the caller's values
      - candidate_counts.fetched == 1, returned == 1
      - evidence_erased_count == 0
      - sufficiency_status == 'SUFFICIENT'
      - filters_applied lists all ten SQL filter entries with their
        bound values (including holder_perspective="any" when unconstrained)

    The filter-name strings are pinned because retrieval auditors use
    them to verify that what the SQL claimed to filter is what was
    actually applied at the row level.
    """
    engram_id = _seed_engram(adapter)
    _seed_statement(adapter, engram_id)

    result = basic_retrieve(
        adapter,
        tenant_id="default",
        holder="alice",
        subject="bob",
        predicate="responsible_for",
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
        trace_id="trace-A",
        query_id="query-A",
    )

    # Receipt envelope
    assert result.receipt.trace_id == "trace-A"
    assert result.receipt.query_id == "query-A"

    # Candidate counts: one row matched, one row returned, no drops
    assert result.receipt.candidate_counts.fetched   == 1
    assert result.receipt.candidate_counts.returned  == 1
    assert result.receipt.candidate_counts.dropped_by_review == 0
    assert result.receipt.candidate_counts.dropped_by_state == 0
    assert result.receipt.candidate_counts.dropped_by_time_anchor == 0
    assert result.receipt.candidate_counts.dropped_by_evidence_erasure == 0
    assert result.receipt.evidence_erased_count == 0
    assert result.receipt.sufficiency_status == "SUFFICIENT"

    # filters_applied: ten entries with stable names + bound values.
    # Names match basic_retriever.cpp; if either side drifts the
    # auditor-readable trace stops corresponding to the SQL.
    filters = {f.name: f.value for f in result.receipt.filters_applied}
    assert filters["tenant_id"]              == "default"
    assert filters["holder_id"]              == "alice"
    assert filters["holder_perspective"]     == "any"
    assert filters["subject_kind"]           == "cognizer"
    assert filters["subject_id"]             == "bob"
    assert filters["predicate"]              == "responsible_for"
    assert filters["consolidation_state"]    == "consolidated|archived"
    assert filters["review_status_exclude"]  == "rejected|pending_review"
    assert filters["evidence_erased"]        == "exclude"
    # as_of is canonicalized to ISO-8601 'Z' suffix at the Python boundary
    assert filters["as_of"] == "2026-04-15T00:00:00Z"

    # Single returned row mirrors the seeded statement
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.tenant_id == "default"
    assert row.holder_id == "alice"
    assert row.subject_kind == "cognizer"
    assert row.subject_id == "bob"
    assert row.predicate == "responsible_for"
    assert row.consolidation_state == "consolidated"


def test_sufficiency_missing_info_when_empty(adapter):
    """No rows match -> MISSING_INFO + zero counts.

    No engram, no statement. Confirms that sufficiency_status flips to
    MISSING_INFO when fetched == 0 (per basic_retriever.cpp:228-230) and
    that an empty result is not silently masked as ABSTAINED.
    """
    result = basic_retrieve(
        adapter,
        tenant_id="default",
        holder="alice",
        subject="bob",
        predicate="responsible_for",
        as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    assert result.rows == []
    assert result.receipt.sufficiency_status == "MISSING_INFO"
    assert result.receipt.candidate_counts.fetched  == 0
    assert result.receipt.candidate_counts.returned == 0
    assert result.receipt.evidence_erased_count == 0
