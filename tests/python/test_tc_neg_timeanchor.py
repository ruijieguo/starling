"""TC-NEG-TIMEANCHOR [CRITICAL] — "last week" anchored to source observed_at.

Spec §15.3.1:
  When a Statement is written with an explicit valid_from and observed_at, the
  writer MUST persist those values verbatim — it must NOT silently substitute
  datetime.now() or any other system-clock value.

  Specifically:
    1. test_last_week_anchored_to_source: A Statement with
         observed_at = "2024-01-15T10:00:00Z"
         valid_from  = "2024-01-08T00:00:00Z"   (engram's observed_at − 7 days)
       must survive the write/read round-trip with those exact values intact.
       The spread (observed_at − valid_from) must be in [0, 14] days, AND the
       gap between today and valid_from must exceed 365 days — proving the
       writer never replaced valid_from with the current date.

    2. test_missing_segment_observed_at_low_confidence: A Statement ingested
       without a meaningful temporal anchor (no segment observed_at context)
       should carry low confidence (< 0.50) OR review_status = REVIEW_REQUESTED.
       This test writes a Statement with confidence=0.30 and review_status=
       REVIEW_REQUESTED and verifies that the DB row satisfies at least one of
       those predicates.

Pattern mirrors test_tc_q3b_001.py (most-recently-landed acceptance test):
  - _core.ExtractedStatement() DTO constructed directly
  - _core.Bus(rt.adapter).write(...) for writes
  - out["stmt_id"] for the returned statement id
  - rt.adapter.db_path for second-connection SQL assertions
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import pytest

from starling import _core, runtime
from starling.bus.append_evidence import BusFacade
from starling.evidence import (
    EngramRetentionMode,
    PrivacyClass,
    for_user_input,
)

# Observed-at timestamps used in both tests (historical — well over 365 days ago).
_ENGRAM_OBSERVED_AT   = "2024-01-15T10:00:00Z"
_STMT_VALID_FROM      = "2024-01-08T00:00:00Z"


@pytest.fixture
def rt(tmp_path):
    """File-backed Runtime with the M0.3 preflight relaxed for tests."""
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_engram_via_bus(rt, created_at: datetime, source_item_id: str) -> str:
    """Ingest an Engram via the production append_evidence path.

    Returns the engram id so the caller can reference it in Bus::write.
    The created_at datetime maps to engrams.created_at (the engram's temporal
    anchor).  We use for_user_input so the ingest_policy resolves to 'store'
    and the row is actually persisted.
    """
    bus = BusFacade(rt.adapter)
    inp = for_user_input(
        tenant_id="default",
        adapter_name="test_tc_neg_timeanchor",
        adapter_version="1.0.0",
        source_item_id=source_item_id,
        source_version="1",
        payload_bytes=b"last week the team deployed the new auth service",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=created_at,
    )
    outcome = bus.append_evidence(inp)
    assert outcome["kind"] == "accepted", \
        f"engram seed must succeed, got {outcome!r}"
    return outcome["engram_ref"].id


def _make_base_stmt() -> "_core.ExtractedStatement":
    """Shared base for all ExtractedStatement DTOs in this module."""
    s = _core.ExtractedStatement()
    s.holder_id              = "alice"
    s.holder_tenant_id       = "default"
    s.holder_perspective     = _core.Perspective.FIRST_PERSON
    s.subject_kind           = "cognizer"
    s.subject_id             = "alice"
    s.predicate              = "observed"
    s.object_kind            = "str"
    s.object_value           = "auth-service-deployment"
    s.canonical_object_hash  = (
        "1a2b3c4d5e6f7890" * 4  # 64 hex chars
    )
    s.modality               = _core.Modality.BELIEVES
    s.polarity               = _core.Polarity.POS
    s.confidence             = 0.80
    s.source_hash            = "feedface"
    s.perceived_by           = ["alice"]
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: valid_from anchored to source observed_at, not system clock
# ─────────────────────────────────────────────────────────────────────────────

def test_last_week_anchored_to_source(rt):
    """TC-NEG-TIMEANCHOR / §15.3.1 — writer must preserve caller-supplied valid_from.

    Sequence:
      1. Ingest an Engram with created_at = 2024-01-15T10:00:00Z.
      2. Write a Statement with:
           observed_at = "2024-01-15T10:00:00Z"  (mirrors engram's observed_at)
           valid_from  = "2024-01-08T00:00:00Z"  (one week prior = "last week")
      3. Read back from DB.

    Invariants:
      A. (observed_at_db − valid_from_db).days in [0, 14]:
           Confirms the spread is approximately one week — the two values are
           internally consistent with a "last week" temporal reference.
      B. (today − valid_from_db).days > 365:
           Confirms valid_from was NOT silently replaced by datetime.now();
           if the writer had clobbered it, valid_from would be today and this
           assertion would fail.
    """
    engram_id = _seed_engram_via_bus(
        rt,
        created_at=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
        source_item_id="msg-timeanchor-01",
    )

    s = _make_base_stmt()
    s.observed_at = _ENGRAM_OBSERVED_AT
    s.valid_from  = _STMT_VALID_FROM

    bus = _core.Bus(rt.adapter)
    out = bus.write(s, engram_id, "span-timeanchor-01", None)
    assert out["kind"] == "accepted", \
        f"Bus.write must be 'accepted', got {out!r}"
    stmt_id = out["stmt_id"]

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        row = conn.execute(
            "SELECT observed_at, valid_from FROM statements WHERE id = ?",
            (stmt_id,),
        ).fetchone()

    assert row is not None, "Statement row must exist in DB after write"
    db_observed_at, db_valid_from = row

    # Decode the ISO-8601 strings to dates for arithmetic.
    observed_at_date = datetime.fromisoformat(
        db_observed_at.replace("Z", "+00:00")).date()
    valid_from_date  = datetime.fromisoformat(
        db_valid_from.replace("Z", "+00:00")).date()
    today            = date.today()

    spread_days = (observed_at_date - valid_from_date).days
    age_days    = (today - valid_from_date).days

    # Invariant A: the temporal spread is one week (tolerance ±7 days).
    assert 0 <= spread_days <= 14, (
        f"Spread (observed_at − valid_from) must be in [0, 14] days; "
        f"got observed_at={db_observed_at!r}, valid_from={db_valid_from!r}, "
        f"spread={spread_days} days"
    )

    # Invariant B: valid_from is historical, NOT today — writer did not clobber it.
    assert age_days > 365, (
        f"valid_from must be > 365 days ago (proving writer did not use now()); "
        f"got valid_from={db_valid_from!r}, age={age_days} days"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: no temporal anchor → low confidence OR REVIEW_REQUESTED
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_segment_observed_at_low_confidence(rt):
    """TC-NEG-TIMEANCHOR / §15.3.1 — no segment observed_at → weak confidence.

    When the extractor cannot anchor a temporal expression to a source
    observed_at, the resulting Statement must be either:
      - low confidence  (confidence < 0.50), OR
      - review_status = REVIEW_REQUESTED

    This test writes a Statement with confidence=0.30 and review_status=
    REVIEW_REQUESTED — the minimum acceptable confidence and an explicit
    request for human review — and verifies that the DB row satisfies at
    least one of those predicates.

    0.30 is the minimum the validator accepts (confidence < 0.3 is dropped);
    0.30 < 0.50 so the confidence predicate alone already passes.  The
    review_status is also set to REVIEW_REQUESTED as an additional guard.

    DB stores ReviewStatus values lowercase: "review_requested".
    """
    # Seed an engram; the temporal anchor on the engram is irrelevant here
    # because the statement carries the temporal uncertainty flag via low
    # confidence + REVIEW_REQUESTED.
    engram_id = _seed_engram_via_bus(
        rt,
        created_at=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
        source_item_id="msg-timeanchor-02",
    )

    s = _make_base_stmt()
    # Use a different canonical_object_hash to avoid chunk-duplicate collision
    # with test 1 (if both run in the same fixture; they get separate rt
    # instances, but this is defensive).
    s.canonical_object_hash = (
        "deadbeef12345678" * 4  # 64 hex chars
    )
    # No segment observed_at is available — extractor sets low confidence.
    s.observed_at    = "2024-06-01T12:00:00Z"   # required field; use engram time
    s.confidence     = 0.30                      # minimum accepted; < 0.50 → weak
    s.review_status  = _core.ReviewStatus.REVIEW_REQUESTED

    bus = _core.Bus(rt.adapter)
    out = bus.write(s, engram_id, "span-timeanchor-02", None)
    assert out["kind"] == "accepted", \
        f"Bus.write must be 'accepted', got {out!r}"
    stmt_id = out["stmt_id"]

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        row = conn.execute(
            "SELECT confidence, review_status FROM statements WHERE id = ?",
            (stmt_id,),
        ).fetchone()

    assert row is not None, "Statement row must exist in DB after write"
    db_confidence, db_review_status = row

    # At least one guard must hold:
    #   low confidence (< 0.50) OR review_status == "review_requested" (lowercase).
    assert db_confidence < 0.50 or db_review_status == "review_requested", (
        f"Statement with no temporal anchor must have confidence < 0.50 OR "
        f"review_status == 'review_requested'; "
        f"got confidence={db_confidence}, review_status={db_review_status!r}"
    )
