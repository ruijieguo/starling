"""
TC-MENTAL-BELIEVE — CRITICAL #8 (09_tom)

Tests the what_does_X_believe primitive, verifying correct filtering:
  1. Returns only statements held by X (not other holders).
  2. Filters by subject (about_y), subject_kind must be 'cognizer'.
  3. Excludes statements where subject_kind != 'cognizer' (entity etc.).
  4. Filters by valid_from / valid_to time window (as_of).
  5. Optional modality kwarg restricts returned statements.
  6. Excludes pending_review statements.

Seeding strategy: direct SQL INSERT into statements table.
No engram FK or bus dependency — read-side primitive tests.

Spec §13.1.
"""
from __future__ import annotations

import sqlite3

import pytest
from datetime import datetime, timezone

from starling import _core
from starling.tom import what_does_X_believe


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TENANT = "default"
AS_OF = datetime(2026, 5, 27, 12, 0, 0, tzinfo=timezone.utc)
BEFORE_AS_OF = "2026-05-26T00:00:00Z"
AFTER_AS_OF = "2026-05-28T00:00:00Z"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path):
    """Return (adapter, raw_conn) pointing to a fresh DB."""
    db_path = str(tmp_path / "mental_believe.db")
    adapter = _core.SqliteAdapter.open(db_path)
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA busy_timeout = 5000")
    yield adapter, raw
    raw.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_statement(
    raw: sqlite3.Connection,
    *,
    id: str,
    tenant: str,
    holder: str,
    subject_kind: str = "cognizer",
    subject_id: str,
    predicate: str = "knows",
    modality: str = "BELIEVES",
    consolidation_state: str = "consolidated",
    review_status: str = "approved",
    valid_from: str | None = None,
    valid_to: str | None = None,
    confidence: float = 0.9,
    canonical_hash: str | None = None,
) -> None:
    raw.execute(
        "INSERT INTO statements ("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate,"
        "  object_kind, object_value, canonical_object_hash, canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at, salience, affect_json, activation,"
        "  last_accessed, provenance, consolidation_state, review_status,"
        "  nesting_depth, created_at, updated_at,"
        "  valid_from, valid_to"
        ") VALUES ("
        "  ?, ?, ?, 'first_person',"
        "  ?, ?, ?,"
        "  'str', 'calculus', ?, 'v1',"
        "  ?, 'pos', ?, '2026-05-25T10:00:00Z', 0.5, '{}', 0.5,"
        "  '2026-05-25T10:00:00Z', 'test', ?, ?,"
        "  0, '2026-05-25T10:00:00Z', '2026-05-25T10:00:00Z',"
        "  ?, ?"
        ")",
        (
            id, tenant, holder,
            subject_kind, subject_id, predicate,
            canonical_hash or id,
            modality, confidence,
            consolidation_state, review_status,
            valid_from, valid_to,
        ),
    )
    raw.commit()


# ---------------------------------------------------------------------------
# TC-MENTAL-BELIEVE-01
# Returns only X's statements (not other holders)
# ---------------------------------------------------------------------------


def test_what_does_X_believe_returns_only_x_statements(db):
    """X=alice → only alice's statements returned, not bob's."""
    adapter, raw = db

    # alice + bob both hold beliefs about carol
    _insert_statement(raw, id="alice-carol-1", tenant=TENANT,
                      holder="alice", subject_id="carol")
    _insert_statement(raw, id="bob-carol-1", tenant=TENANT,
                      holder="bob", subject_id="carol")

    result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                 tenant_id=TENANT, as_of=AS_OF)

    assert len(result) == 1
    assert result[0].holder_id == "alice"
    assert result[0].id == "alice-carol-1"


# ---------------------------------------------------------------------------
# TC-MENTAL-BELIEVE-02
# Filters by subject (about_y)
# ---------------------------------------------------------------------------


def test_what_does_X_believe_filters_by_subject(db):
    """alice has beliefs about bob + carol; about_y='carol' returns only carol-subject."""
    adapter, raw = db

    _insert_statement(raw, id="alice-about-bob", tenant=TENANT,
                      holder="alice", subject_id="bob")
    _insert_statement(raw, id="alice-about-carol", tenant=TENANT,
                      holder="alice", subject_id="carol")

    result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                 tenant_id=TENANT, as_of=AS_OF)

    assert len(result) == 1
    assert result[0].subject_id == "carol"
    assert result[0].id == "alice-about-carol"


# ---------------------------------------------------------------------------
# TC-MENTAL-BELIEVE-03
# subject_kind='cognizer' only — entity-subject statements excluded
# ---------------------------------------------------------------------------


def test_what_does_X_believe_subject_kind_cognizer_only(db):
    """Statements with subject_kind='entity' are excluded (only cognizer subjects returned)."""
    adapter, raw = db

    # Same subject_id 'carol', but entity kind
    _insert_statement(raw, id="alice-entity-carol", tenant=TENANT,
                      holder="alice", subject_id="carol", subject_kind="entity")
    # cognizer kind — should be included
    _insert_statement(raw, id="alice-cognizer-carol", tenant=TENANT,
                      holder="alice", subject_id="carol", subject_kind="cognizer")

    result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                 tenant_id=TENANT, as_of=AS_OF)

    result_ids = {r.id for r in result}
    assert "alice-cognizer-carol" in result_ids
    assert "alice-entity-carol" not in result_ids


# ---------------------------------------------------------------------------
# TC-MENTAL-BELIEVE-04
# as_of time window: statement with valid_from > as_of is excluded
# ---------------------------------------------------------------------------


def test_what_does_X_believe_as_of_filters_time_window(db):
    """Statement with valid_from after as_of is excluded from results."""
    adapter, raw = db

    # valid_from in the past (before as_of) → included
    _insert_statement(raw, id="s-active", tenant=TENANT,
                      holder="alice", subject_id="carol",
                      valid_from=BEFORE_AS_OF, valid_to=None)
    # valid_from in the future (after as_of) → excluded
    _insert_statement(raw, id="s-future", tenant=TENANT,
                      holder="alice", subject_id="carol",
                      canonical_hash="hash-future",
                      valid_from=AFTER_AS_OF, valid_to=None)

    result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                 tenant_id=TENANT, as_of=AS_OF)

    result_ids = {r.id for r in result}
    assert "s-active" in result_ids
    assert "s-future" not in result_ids


# ---------------------------------------------------------------------------
# TC-MENTAL-BELIEVE-05
# modality filter kwarg restricts returned statements
# ---------------------------------------------------------------------------


def test_what_does_X_believe_modality_filter(db):
    """modality='BELIEVES' returns only BELIEVES statements; KNOWS excluded."""
    adapter, raw = db

    _insert_statement(raw, id="s-believes", tenant=TENANT,
                      holder="alice", subject_id="carol", modality="BELIEVES")
    _insert_statement(raw, id="s-knows", tenant=TENANT,
                      holder="alice", subject_id="carol", modality="KNOWS",
                      canonical_hash="hash-knows")

    # Without filter: both returned
    all_result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                     tenant_id=TENANT, as_of=AS_OF)
    assert len(all_result) == 2

    # With BELIEVES filter
    believes_result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                          tenant_id=TENANT, as_of=AS_OF,
                                          modality="BELIEVES")
    assert len(believes_result) == 1
    assert believes_result[0].modality == "BELIEVES"

    # With KNOWS filter
    knows_result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                       tenant_id=TENANT, as_of=AS_OF,
                                       modality="KNOWS")
    assert len(knows_result) == 1
    assert knows_result[0].modality == "KNOWS"


# ---------------------------------------------------------------------------
# TC-MENTAL-BELIEVE-06
# pending_review statements excluded
# ---------------------------------------------------------------------------


def test_what_does_X_believe_excludes_pending_review(db):
    """Statements with review_status='pending_review' or 'rejected' are excluded."""
    adapter, raw = db

    _insert_statement(raw, id="s-approved", tenant=TENANT,
                      holder="alice", subject_id="carol",
                      review_status="approved")
    _insert_statement(raw, id="s-pending", tenant=TENANT,
                      holder="alice", subject_id="carol",
                      canonical_hash="hash-pending",
                      review_status="pending_review")
    _insert_statement(raw, id="s-rejected", tenant=TENANT,
                      holder="alice", subject_id="carol",
                      canonical_hash="hash-rejected",
                      review_status="rejected")

    result = what_does_X_believe(adapter, x="alice", about_y="carol",
                                 tenant_id=TENANT, as_of=AS_OF)

    result_ids = {r.id for r in result}
    assert "s-approved" in result_ids
    assert "s-pending" not in result_ids
    assert "s-rejected" not in result_ids
