"""
TC-PERSPECTIVE-RUNTIME — CRITICAL #7 (09_tom)

Tests ToMEngine.perspective_take, verifying that the Context it returns:
  1. Context.visible_engram_ids == KnowledgeFrontier.visible_engrams_at result
     (same set, just packaged in Context).
  2. Context.target_beliefs contains only alice's consolidated/archived,
     approved statements (holder_id filter + consolidation/review filters).
  3. Context.cg is always an empty list (P2.a stub).

Seeding strategy: direct SQL INSERT into cognizer_frontier_facts for
frontier rows; direct SQL INSERT into statements for belief rows.
No engram FK or bus dependency — these are read-side tests.

Spec §13.1, §7.2.
"""
from __future__ import annotations

import sqlite3

import pytest

from starling import _core
from starling.cognizer import CognizerHub, KnowledgeFrontier
from starling.tom import ToMEngine


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TENANT = "default"
AS_OF = "2026-05-27T12:00:00Z"
BEFORE_AS_OF = "2026-05-26T00:00:00Z"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path):
    """Return (adapter, raw_conn, engine, frontier) all pointing to the same DB."""
    db_path = str(tmp_path / "perspective_runtime.db")
    adapter = _core.SqliteAdapter.open(db_path)
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA busy_timeout = 5000")
    hub = CognizerHub(adapter)
    frontier = KnowledgeFrontier(adapter)
    engine = ToMEngine(adapter, hub, frontier)
    yield adapter, raw, engine, frontier
    raw.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_frontier_fact(
    raw: sqlite3.Connection,
    *,
    id: str,
    tenant: str,
    cognizer: str,
    fact_kind: str,
    source_engram_id: str | None,
    asserted_at: str,
) -> None:
    raw.execute(
        "INSERT INTO cognizer_frontier_facts "
        "(id, tenant_id, cognizer_id, statement_id, source_engram_id, "
        "fact_kind, asserted_at, metadata_json) "
        "VALUES (?, ?, ?, NULL, ?, ?, ?, '{}')",
        (id, tenant, cognizer, source_engram_id, fact_kind, asserted_at),
    )
    raw.commit()


def _insert_statement(
    raw: sqlite3.Connection,
    *,
    id: str,
    tenant: str,
    holder: str,
    subject_id: str,
    predicate: str = "knows",
    modality: str = "BELIEVES",
    consolidation_state: str = "consolidated",
    review_status: str = "approved",
    valid_from: str | None = None,
    valid_to: str | None = None,
    subject_kind: str = "cognizer",
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
# TC-PERSPECTIVE-RUNTIME-01
# Visible engrams in Context == frontier.visible_engrams_at result
# ---------------------------------------------------------------------------


def test_perspective_take_returns_visible_engrams_from_frontier(db):
    """Context.visible_engram_ids equals KnowledgeFrontier.visible_engrams_at."""
    adapter, raw, engine, frontier = db

    # Seed two explicit_told frontier facts (source_engram_id populated)
    for i, eid in enumerate(["engram-A", "engram-B"], 1):
        _insert_frontier_fact(
            raw,
            id=f"ff-{i}",
            tenant=TENANT,
            cognizer="alice",
            fact_kind="explicit_told",
            source_engram_id=eid,
            asserted_at=BEFORE_AS_OF,
        )

    # Ground truth from frontier
    frontier_visible = set(frontier.visible_engrams_at(TENANT, "alice", AS_OF))

    # Context wraps the same result
    ctx = engine.perspective_take("alice", TENANT, AS_OF)
    context_visible = set(ctx.visible_engram_ids)

    assert context_visible == frontier_visible
    assert context_visible == {"engram-A", "engram-B"}


# ---------------------------------------------------------------------------
# TC-PERSPECTIVE-RUNTIME-02
# target_beliefs includes only the holder's statements
# ---------------------------------------------------------------------------


def test_perspective_take_target_beliefs_filters_by_holder(db):
    """Context.target_beliefs contains only alice's statements, not bob's."""
    adapter, raw, engine, frontier = db

    _insert_statement(raw, id="alice-stmt-1", tenant=TENANT, holder="alice",
                      subject_id="carol")
    _insert_statement(raw, id="bob-stmt-1", tenant=TENANT, holder="bob",
                      subject_id="carol")

    ctx = engine.perspective_take("alice", TENANT, AS_OF)
    beliefs = list(ctx.target_beliefs)

    assert len(beliefs) == 1
    assert beliefs[0].holder_id == "alice"
    assert beliefs[0].id == "alice-stmt-1"


# ---------------------------------------------------------------------------
# TC-PERSPECTIVE-RUNTIME-03
# Volatile statements excluded from target_beliefs
# ---------------------------------------------------------------------------


def test_perspective_take_filters_consolidation_state(db):
    """Volatile statements are excluded; consolidated + archived are included."""
    adapter, raw, engine, frontier = db

    _insert_statement(raw, id="s-consolidated", tenant=TENANT, holder="alice",
                      subject_id="bob", consolidation_state="consolidated")
    _insert_statement(raw, id="s-archived", tenant=TENANT, holder="alice",
                      subject_id="bob", consolidation_state="archived")
    _insert_statement(raw, id="s-volatile", tenant=TENANT, holder="alice",
                      subject_id="bob", consolidation_state="volatile")

    ctx = engine.perspective_take("alice", TENANT, AS_OF)
    belief_ids = {b.id for b in ctx.target_beliefs}

    assert "s-consolidated" in belief_ids
    assert "s-archived" in belief_ids
    assert "s-volatile" not in belief_ids


# ---------------------------------------------------------------------------
# TC-PERSPECTIVE-RUNTIME-04
# pending_review statements excluded from target_beliefs
# ---------------------------------------------------------------------------


def test_perspective_take_filters_review_status(db):
    """Statements with review_status='pending_review' are excluded."""
    adapter, raw, engine, frontier = db

    _insert_statement(raw, id="s-approved", tenant=TENANT, holder="alice",
                      subject_id="bob", review_status="approved")
    _insert_statement(raw, id="s-pending", tenant=TENANT, holder="alice",
                      subject_id="bob", review_status="pending_review")
    # rejected should also be excluded
    _insert_statement(raw, id="s-rejected", tenant=TENANT, holder="alice",
                      subject_id="bob", review_status="rejected")

    ctx = engine.perspective_take("alice", TENANT, AS_OF)
    belief_ids = {b.id for b in ctx.target_beliefs}

    assert "s-approved" in belief_ids
    assert "s-pending" not in belief_ids
    assert "s-rejected" not in belief_ids


# ---------------------------------------------------------------------------
# TC-PERSPECTIVE-RUNTIME-05
# cg is always empty list in P2.a
# ---------------------------------------------------------------------------


def test_perspective_take_cg_always_empty_in_p2a(db):
    """Context.cg is an empty list in P2.a (common ground stub)."""
    adapter, raw, engine, frontier = db

    # Seed frontier + beliefs to ensure the stub holds even with real data
    _insert_frontier_fact(
        raw,
        id="ff-cg-test",
        tenant=TENANT,
        cognizer="alice",
        fact_kind="explicit_told",
        source_engram_id="engram-X",
        asserted_at=BEFORE_AS_OF,
    )
    _insert_statement(raw, id="s-cg", tenant=TENANT, holder="alice",
                      subject_id="bob")

    ctx = engine.perspective_take("alice", TENANT, AS_OF)

    assert list(ctx.cg) == []
