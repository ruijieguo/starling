"""Filter-predicate + evidence-erased coverage for `starling.retrieval.basic_retrieve`.

Pins two contracts at the Python layer:

1. Volatile statements are excluded.
   The SQL filter `consolidation_state IN ('consolidated','archived')` drops
   any row that hasn't been consolidated yet. We seed via Bus.write (which
   writes VOLATILE) and confirm basic_retrieve returns nothing.

2. Evidence-erased rows are filtered AND counted.
   Uses `starling.testing.mark_evidence_erased` to flip an engram's
   erased_at, then confirms the corresponding statement disappears from
   results AND that `evidence_erased_count` / `dropped_by_evidence_erasure`
   tick up by one.

REJECTED / PENDING_REVIEW review_status filtering is covered at the C++
layer (tests/cpp/test_basic_retriever_filter_predicates.cpp) — there is no
public Python helper to flip review_status, and inventing one for a single
test would duplicate coverage. The archived case is similarly covered in
C++; the Python value-add here is end-to-end coverage of mark_evidence_erased.

The CI static scan (scripts/ci_static_scan.py) bans starling.testing
imports from prod entrypoints; tests/python is in the allowed-roots list,
so the import here is intentional and safe.
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
from starling.testing import (  # NOLINT(starling-testing-isolation)
    mark_consolidated,
    mark_evidence_erased,
)


_AS_OF = datetime(2026, 4, 15, tzinfo=timezone.utc)


@pytest.fixture
def adapter():
    """`:memory:` SqliteAdapter — migrations applied at open() time.

    SqliteAdapter::open runs migrations to the latest version during
    construction (see include/starling/persistence/sqlite_adapter.hpp:11),
    so no extra setup is needed. `:memory:` keeps the test ephemeral and
    avoids any /tmp/*.db convention clash.

    Note: the evidence-erased test uses :memory: even though
    test_mark_evidence_erased.py uses a file path. Reason: that test reads
    back from a second stdlib sqlite3 connection to verify the audit row;
    here we only ever read through the same C++ adapter via basic_retrieve,
    so a single :memory: connection is fine.
    """
    return _core.SqliteAdapter.open(":memory:")


def _seed_engram(
    adapter,
    *,
    tenant_id: str = "default",
    source_item_id: str = "seed-msg-1",
    payload: bytes = b"seed payload",
) -> str:
    """Append a single user_input engram and return its id.

    Distinct `source_item_id` + `payload` combinations land distinct engram
    rows, which is what we need for the evidence-erased test (we want two
    statements anchored on two DIFFERENT engrams so erasing one doesn't
    cascade to the other).
    """
    bus = BusFacade(adapter)
    inp = for_user_input(
        tenant_id=tenant_id,
        adapter_name="test_basic_retrieve_filters",
        adapter_version="1.0.0",
        source_item_id=source_item_id,
        source_version="1",
        payload_bytes=payload,
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
    )
    outcome = bus.append_evidence(inp)
    assert outcome["kind"] == "accepted", \
        f"engram seed must succeed, got {outcome!r}"
    return outcome["engram_ref"].id


def _build_statement(
    *,
    holder_id: str = "alice",
    tenant_id: str = "default",
    subject_id: str = "bob",
    predicate: str = "responsible_for",
    object_value: str = "auth",
    canonical_object_hash: str = (
        "deadbeef01234567deadbeef01234567"
        "deadbeef01234567deadbeef01234567"
    ),
) -> "_core.ExtractedStatement":
    """Build an ExtractedStatement matching the seeded SELECT shape.

    Mirrors test_basic_retrieve_receipt.py's _seed_statement field set so
    the basic_retrieve filter (consolidation_state, review_status, valid
    window straddling 2026-04-15) accepts the row.
    """
    s = _core.ExtractedStatement()
    s.holder_id          = holder_id
    s.holder_tenant_id   = tenant_id
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind       = "cognizer"
    s.subject_id         = subject_id
    s.predicate          = predicate
    s.object_kind        = "str"
    s.object_value       = object_value
    s.canonical_object_hash = canonical_object_hash
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = _core.Polarity.POS
    s.confidence         = 0.9
    s.observed_at        = "2026-04-14T09:00:00Z"
    s.source_hash        = "abc123"
    s.valid_from         = "2026-04-01T00:00:00Z"
    s.valid_to           = "2026-12-31T00:00:00Z"
    s.perceived_by       = [holder_id]
    return s


def _retrieve(adapter, *, holder: str = "alice"):
    """Convenience: invoke basic_retrieve with the canonical fixture args."""
    return basic_retrieve(
        adapter,
        tenant_id="default",
        holder=holder,
        subject="bob",
        predicate="responsible_for",
        as_of=_AS_OF,
    )


# ----------------------------------------------------------- volatile filter

def test_volatile_excluded(adapter):
    """A row written via Bus.write but not consolidated must be excluded.

    Bus.write lands new statements as VOLATILE. The retrieval SELECT's
    `consolidation_state IN ('consolidated','archived')` predicate drops
    them. Without the mark_consolidated call below, basic_retrieve returns
    zero rows and reports MISSING_INFO.

    This is the negative complement to test_basic_retrieve_receipt.py's
    happy path (which DOES mark_consolidated and asserts the row appears).
    """
    engram_id = _seed_engram(adapter)
    stmt = _build_statement()
    bus = _core.Bus(adapter)
    out = bus.write(stmt, engram_id, "span-volatile", None)
    assert out["kind"] == "accepted", f"Bus.write must accept, got {out!r}"
    # Deliberately NOT calling mark_consolidated — the row stays VOLATILE.

    result = _retrieve(adapter)

    assert result.rows == [], \
        "volatile rows must be excluded by the consolidation_state filter"
    assert result.receipt.candidate_counts.fetched == 0
    assert result.receipt.candidate_counts.returned == 0
    assert result.receipt.evidence_erased_count == 0
    assert result.receipt.sufficiency_status == "MISSING_INFO"


# --------------------------------------------------- archived row inclusion
#
# Skipped at the Python layer: producing an archived row requires either a
# direct-contradiction or superseding write to trigger the §15.3.4 atomic
# SUPERSEDES path, which is non-trivial to set up cleanly here. The C++
# test tests/cpp/test_basic_retriever_filter_predicates.cpp covers the
# archived inclusion case directly. Documenting the skip explicitly so a
# future contributor knows the gap is intentional, not an oversight.


# -------------------------------------------------- evidence-erased filter

def test_evidence_erased_filtered_and_counted(adapter):
    """Erasing an engram drops the anchored statement AND increments counts.

    Setup:
      * Two distinct engrams (eng-A, eng-B) seeded via BusFacade. Distinct
        source_item_id + payload bytes ⇒ distinct engram rows.
      * Two statements written, each citing one of the engrams. They share
        holder_id+predicate but use different (subject_id,
        canonical_object_hash) tuples so the chunk-dup guard in
        statement_writer.cpp doesn't collapse them.
      * Both statements are flipped to CONSOLIDATED.

    Pre-erasure baseline:
      * basic_retrieve (with subject='bob' OR subject='carol') returns the
        corresponding row; evidence_erased_count == 0.

    Post-erasure check:
      * mark_evidence_erased(eng-A) -> True.
      * basic_retrieve(subject='bob') now returns NO rows: fetched=1
        (the SELECT still finds it), returned=0 (the post-filter drops it),
        evidence_erased_count=1, dropped_by_evidence_erasure=1, status
        MISSING_INFO.
      * basic_retrieve(subject='carol') is unchanged: fetched=1, returned=1,
        evidence_erased_count=0. This is the cross-engram independence
        check — erasing eng-A must NOT cascade to eng-B's statement.
    """
    # Two distinct engrams. Different source_item_id + payload guarantees
    # different content_hash and therefore different engram rows.
    engram_a = _seed_engram(
        adapter, source_item_id="msg-A", payload=b"alice says bob owns auth")
    engram_b = _seed_engram(
        adapter, source_item_id="msg-B", payload=b"alice says carol owns api")
    assert engram_a != engram_b, \
        "two distinct seeds must produce distinct engram ids"

    bus = _core.Bus(adapter)

    # Statement 1: subject='bob', anchored on engram_a
    stmt_bob = _build_statement(
        subject_id="bob",
        object_value="auth",
        canonical_object_hash="aa" * 32,
    )
    out_bob = bus.write(stmt_bob, engram_a, "span-bob", None)
    assert out_bob["kind"] == "accepted", f"Bus.write(bob) failed: {out_bob!r}"
    assert mark_consolidated(adapter, out_bob["stmt_id"], "default") is True

    # Statement 2: subject='carol', anchored on engram_b
    stmt_carol = _build_statement(
        subject_id="carol",
        object_value="api",
        canonical_object_hash="bb" * 32,
    )
    out_carol = bus.write(stmt_carol, engram_b, "span-carol", None)
    assert out_carol["kind"] == "accepted", f"Bus.write(carol) failed: {out_carol!r}"
    assert mark_consolidated(adapter, out_carol["stmt_id"], "default") is True

    # ---- Pre-erasure: both statements visible to their respective queries.
    pre_bob = _retrieve(adapter)  # subject='bob'
    assert len(pre_bob.rows) == 1, \
        f"bob's row must be retrievable pre-erasure, got {pre_bob.rows!r}"
    assert pre_bob.receipt.candidate_counts.fetched == 1
    assert pre_bob.receipt.candidate_counts.returned == 1
    assert pre_bob.receipt.candidate_counts.dropped_by_evidence_erasure == 0
    assert pre_bob.receipt.evidence_erased_count == 0
    assert pre_bob.receipt.sufficiency_status == "SUFFICIENT"

    pre_carol = basic_retrieve(
        adapter, tenant_id="default", holder="alice",
        subject="carol", predicate="responsible_for", as_of=_AS_OF,
    )
    assert len(pre_carol.rows) == 1, \
        f"carol's row must be retrievable pre-erasure, got {pre_carol.rows!r}"

    # ---- Erase engram_a only.
    erased = mark_evidence_erased(
        adapter, engram_a, "default", "2026-05-24T09:00:00Z")
    assert erased is True, \
        "mark_evidence_erased should report True for a previously-NULL row"

    # ---- Post-erasure: bob's row is filtered out + counted.
    post_bob = _retrieve(adapter)  # subject='bob'
    assert post_bob.rows == [], \
        "bob's statement must be filtered after its sole engram is erased"
    assert post_bob.receipt.candidate_counts.fetched == 1, \
        "SELECT should still find the row — the post-filter is what drops it"
    assert post_bob.receipt.candidate_counts.returned == 0
    assert post_bob.receipt.candidate_counts.dropped_by_evidence_erasure == 1, \
        "dropped_by_evidence_erasure must increment by exactly one"
    assert post_bob.receipt.evidence_erased_count == 1, \
        "evidence_erased_count must increment by exactly one"
    # No SUFFICIENT/MISSING_INFO assertion is strictly required, but
    # MISSING_INFO is the contract from basic_retriever.cpp:228-230 when
    # returned==0.
    assert post_bob.receipt.sufficiency_status == "MISSING_INFO"

    # ---- Cross-check: carol's row is unaffected.
    post_carol = basic_retrieve(
        adapter, tenant_id="default", holder="alice",
        subject="carol", predicate="responsible_for", as_of=_AS_OF,
    )
    assert len(post_carol.rows) == 1, \
        "erasing engram_a must NOT cascade to engram_b's statement"
    assert post_carol.receipt.candidate_counts.fetched == 1
    assert post_carol.receipt.candidate_counts.returned == 1
    assert post_carol.receipt.candidate_counts.dropped_by_evidence_erasure == 0
    assert post_carol.receipt.evidence_erased_count == 0
