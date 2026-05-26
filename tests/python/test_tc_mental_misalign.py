"""
TC-MENTAL-MISALIGN — CRITICAL #9 (09_tom)

Tests the find_misalignment primitive. The C++ implementation keys on
(predicate, canonical_object_hash) to align beliefs between X and Y, then
classifies into three categories:
  - only_x_believes  : X has 'pos' polarity, Y does not
  - only_y_believes  : Y has 'pos' polarity, X does not
  - confidence_diverges : both have 'pos' for same key, |delta| > 0.3

IMPORTANT: confidence_diverges requires the SAME canonical_object_hash in
both X and Y's statements (same belief key), so the comparison is meaningful.
Statements with different canonical_object_hash values are compared for
only_x/only_y presence, not confidence.

Seeding strategy: direct SQL INSERT into statements table.
Spec §13.1.
"""
from __future__ import annotations

import sqlite3

import pytest
from datetime import datetime, timezone

from starling import _core
from starling.tom import find_misalignment


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TENANT = "default"
AS_OF = datetime(2026, 5, 27, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path):
    """Return (adapter, raw_conn) pointing to a fresh DB."""
    db_path = str(tmp_path / "mental_misalign.db")
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
    object_value: str = "calculus",
    modality: str = "BELIEVES",
    polarity: str = "pos",
    confidence: float = 0.9,
    consolidation_state: str = "consolidated",
    review_status: str = "approved",
    canonical_hash: str,
) -> None:
    raw.execute(
        "INSERT INTO statements ("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate,"
        "  object_kind, object_value, canonical_object_hash, canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at, salience, affect_json, activation,"
        "  last_accessed, provenance, consolidation_state, review_status,"
        "  nesting_depth, created_at, updated_at"
        ") VALUES ("
        "  ?, ?, ?, 'first_person',"
        "  ?, ?, ?,"
        "  'str', ?, ?, 'v1',"
        "  ?, ?, ?, '2026-05-25T10:00:00Z', 0.5, '{}', 0.5,"
        "  '2026-05-25T10:00:00Z', 'test', ?, ?,"
        "  0, '2026-05-25T10:00:00Z', '2026-05-25T10:00:00Z'"
        ")",
        (
            id, tenant, holder,
            subject_kind, subject_id, predicate,
            object_value, canonical_hash,
            modality, polarity, confidence,
            consolidation_state, review_status,
        ),
    )
    raw.commit()


# ---------------------------------------------------------------------------
# TC-MENTAL-MISALIGN-01
# alice believes something, bob has no statement → only_x_believes populated
# ---------------------------------------------------------------------------


def test_misalign_detects_only_x_believes(db):
    """Alice believes carol knows X; bob has no statement → only_x_believes has 1 entry."""
    adapter, raw = db

    _insert_statement(
        raw, id="alice-carol-1", tenant=TENANT,
        holder="alice", subject_id="carol", predicate="knows",
        canonical_hash="hash-carol-knows-calculus",
    )
    # bob has NO statement about carol

    result = find_misalignment(
        adapter,
        x="alice", y="bob",
        subject_kind="cognizer", subject_id="carol",
        tenant_id=TENANT, as_of=AS_OF,
    )

    only_x = list(result.only_x_believes)
    only_y = list(result.only_y_believes)

    assert len(only_x) == 1
    assert only_x[0].holder_id == "alice"
    assert len(only_y) == 0


# ---------------------------------------------------------------------------
# TC-MENTAL-MISALIGN-02
# bob believes something, alice has no statement → only_y_believes populated
# ---------------------------------------------------------------------------


def test_misalign_detects_only_y_believes(db):
    """Bob believes carol knows X; alice has no statement → only_y_believes has 1 entry."""
    adapter, raw = db

    _insert_statement(
        raw, id="bob-carol-1", tenant=TENANT,
        holder="bob", subject_id="carol", predicate="knows",
        canonical_hash="hash-carol-knows-calculus",
    )
    # alice has NO statement about carol

    result = find_misalignment(
        adapter,
        x="alice", y="bob",
        subject_kind="cognizer", subject_id="carol",
        tenant_id=TENANT, as_of=AS_OF,
    )

    only_x = list(result.only_x_believes)
    only_y = list(result.only_y_believes)

    assert len(only_y) == 1
    assert only_y[0].holder_id == "bob"
    assert len(only_x) == 0


# ---------------------------------------------------------------------------
# TC-MENTAL-MISALIGN-03
# Both believe same fact but large confidence delta → confidence_diverges
# ---------------------------------------------------------------------------


def test_misalign_detects_confidence_divergence(db):
    """alice.confidence=0.95, bob.confidence=0.50 (delta=0.45 > 0.3) → 1 divergent pair."""
    adapter, raw = db

    # Both must use SAME canonical_hash + predicate for the belief key to match
    _insert_statement(
        raw, id="alice-carol-1", tenant=TENANT,
        holder="alice", subject_id="carol", predicate="knows",
        canonical_hash="hash-shared-key",
        confidence=0.95,
    )
    _insert_statement(
        raw, id="bob-carol-1", tenant=TENANT,
        holder="bob", subject_id="carol", predicate="knows",
        canonical_hash="hash-shared-key",
        confidence=0.50,
    )

    result = find_misalignment(
        adapter,
        x="alice", y="bob",
        subject_kind="cognizer", subject_id="carol",
        tenant_id=TENANT, as_of=AS_OF,
    )

    diverges = list(result.confidence_diverges)
    assert len(diverges) == 1

    # The pair is (x_statement, y_statement) — alice first, bob second
    alice_stmt, bob_stmt = diverges[0]
    assert alice_stmt.holder_id == "alice"
    assert bob_stmt.holder_id == "bob"
    assert abs(alice_stmt.confidence - bob_stmt.confidence) > 0.3

    # With same (predicate, canonical_hash), both believe it — not in only_x/only_y
    assert len(list(result.only_x_believes)) == 0
    assert len(list(result.only_y_believes)) == 0


# ---------------------------------------------------------------------------
# TC-MENTAL-MISALIGN-04
# Small confidence delta → NOT in confidence_diverges
# ---------------------------------------------------------------------------


def test_misalign_ignores_small_confidence_differences(db):
    """alice.confidence=0.90, bob.confidence=0.85 (delta=0.05 ≤ 0.3) → empty diverges."""
    adapter, raw = db

    _insert_statement(
        raw, id="alice-carol-1", tenant=TENANT,
        holder="alice", subject_id="carol", predicate="knows",
        canonical_hash="hash-shared-key",
        confidence=0.90,
    )
    _insert_statement(
        raw, id="bob-carol-1", tenant=TENANT,
        holder="bob", subject_id="carol", predicate="knows",
        canonical_hash="hash-shared-key",
        confidence=0.85,
    )

    result = find_misalignment(
        adapter,
        x="alice", y="bob",
        subject_kind="cognizer", subject_id="carol",
        tenant_id=TENANT, as_of=AS_OF,
    )

    assert len(list(result.confidence_diverges)) == 0
    # Both believe it with same key → neither appears in only_x/only_y
    assert len(list(result.only_x_believes)) == 0
    assert len(list(result.only_y_believes)) == 0


# ---------------------------------------------------------------------------
# TC-MENTAL-MISALIGN-05
# Completely disjoint predicates/hashes → each predicate in only_x or only_y
# ---------------------------------------------------------------------------


def test_misalign_both_empty_when_no_overlap_and_no_unique(db):
    """alice + bob have completely disjoint beliefs (different predicates).

    Each predicate appears in only_x_believes (alice's) or only_y_believes
    (bob's) respectively. confidence_diverges is empty (no matching keys).
    """
    adapter, raw = db

    # alice believes carol 'can_fly' (unique to alice)
    _insert_statement(
        raw, id="alice-carol-canfly", tenant=TENANT,
        holder="alice", subject_id="carol", predicate="can_fly",
        object_value="yes", canonical_hash="hash-alice-canfly",
        confidence=0.8,
    )
    # bob believes carol 'is_mortal' (unique to bob)
    _insert_statement(
        raw, id="bob-carol-mortal", tenant=TENANT,
        holder="bob", subject_id="carol", predicate="is_mortal",
        object_value="yes", canonical_hash="hash-bob-mortal",
        confidence=0.95,
    )

    result = find_misalignment(
        adapter,
        x="alice", y="bob",
        subject_kind="cognizer", subject_id="carol",
        tenant_id=TENANT, as_of=AS_OF,
    )

    only_x = list(result.only_x_believes)
    only_y = list(result.only_y_believes)
    diverges = list(result.confidence_diverges)

    # Alice's disjoint belief appears in only_x
    assert len(only_x) == 1
    assert only_x[0].predicate == "can_fly"

    # Bob's disjoint belief appears in only_y
    assert len(only_y) == 1
    assert only_y[0].predicate == "is_mortal"

    # No shared belief keys → no confidence divergence
    assert len(diverges) == 0
