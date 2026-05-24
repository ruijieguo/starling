"""Tests for the dev-only `starling.testing.mark_evidence_erased` helper (M0.6 Task 5).

The helper flips an engram row's erased_at from NULL to an ISO-8601 timestamp
and writes a 'testing.mark_evidence_erased' audit event in the same
transaction. Idempotent: returns False on already-erased or missing rows, and
emits no audit event in that case so a re-call never trips
UNIQUE(idempotency_key) on bus_events.

Used by the M0.6 13_retrieval.md evidence-erased negative test, which drives
BasicRetriever and asserts that statements anchored solely on erased engrams
disappear from results.

The CI static scan (scripts/ci_static_scan.py) bans starling.testing imports
from prod entrypoints — this test lives under tests/python/ which is in the
allowed-roots list, so the import here is intentional and safe.
"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from starling import _core
from starling.testing import mark_evidence_erased  # NOLINT(starling-testing-isolation)


# Minimal column subset for the engrams table (migrations 0001 + 0003).
# Anything not listed takes its DEFAULT — the testing helper only cares about
# (id, tenant_id, erased_at), so the rest is filler.
_INSERT_SQL = (
    "INSERT INTO engrams("
    "id, tenant_id, content_hash, source_kind, ingest_policy,"
    "ingest_mode, privacy_class, retention_mode, refcount,"
    "created_at, erased_at"
    ") VALUES (?, ?, 'h', 'user_input', 'store',"
    "          'whole_record', 'public', 'audit_retain', 1,"
    "          '2026-04-15T00:00:00Z', NULL)"
)


def _seed_engram(
    db_path: Path,
    *,
    engram_id: str = "e-test-1",
    tenant_id: str = "default",
) -> None:
    """Insert a single engram row with erased_at=NULL.

    Uses stdlib sqlite3 against the same db file the C++ adapter opened. WAL
    mode (set by SqliteAdapter::open) makes this concurrent-safe for sequential
    read/write from a separate Python connection.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(_INSERT_SQL, (engram_id, tenant_id))
        conn.commit()
    finally:
        conn.close()


class MarkEvidenceErasedTest(unittest.TestCase):
    """Unit-level coverage for testing.mark_evidence_erased."""

    def setUp(self) -> None:
        # File-backed SQLite so we can read with stdlib sqlite3 between the
        # C++ adapter's writes — same pattern as test_mark_consolidated.py.
        # The C++ adapter is dropped before tmpdir cleanup in tearDown so
        # SQLite releases the WAL files cleanly.
        self._tmpdir = TemporaryDirectory(prefix="m0_6_mark_evidence_erased_")
        self.db_path = Path(self._tmpdir.name) / "starling.sqlite3"
        self.adapter = _core.SqliteAdapter.open(str(self.db_path))

    def tearDown(self) -> None:
        # Drop the adapter (releases the C++ Connection's sqlite3*) BEFORE
        # the tmpdir is cleaned, otherwise WAL files linger and the cleanup
        # races on Linux. macOS tolerates either order.
        self.adapter = None  # type: ignore[assignment]
        self._tmpdir.cleanup()

    # ------------------------------------------------------------- happy path

    def test_null_transitions_to_iso_timestamp(self) -> None:
        """A row with erased_at=NULL flips to the supplied timestamp; returns True."""
        _seed_engram(self.db_path, engram_id="e1", tenant_id="default")

        result = mark_evidence_erased(
            self.adapter, "e1", "default", "2026-05-24T09:00:00Z")
        self.assertTrue(result, "expected True when flipping a NULL row")

        # Verify state landed via stdlib sqlite3 (independent connection ⇒
        # rules out any in-memory cache effect).
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT erased_at FROM engrams WHERE id=? AND tenant_id=?",
                ("e1", "default"),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("2026-05-24T09:00:00Z",))

    # ------------------------------------------------------------- idempotency

    def test_idempotent_returns_false_on_second_call(self) -> None:
        """Calling twice on the same row: first True, second False; erased_at unchanged.

        The audit event is written ONLY on the True call, so the second call
        never trips UNIQUE(idempotency_key) on bus_events. A regression that
        emitted the audit row on every call would surface as a SqliteError
        thrown out of the binding. The second call also passes a DIFFERENT
        timestamp — the first one must win and stick.
        """
        _seed_engram(self.db_path, engram_id="e2", tenant_id="default")

        first = mark_evidence_erased(
            self.adapter, "e2", "default", "2026-05-24T09:00:00Z")
        second = mark_evidence_erased(
            self.adapter, "e2", "default", "2026-05-24T10:00:00Z")

        self.assertTrue(first, "first call should report True")
        self.assertFalse(
            second,
            "second call must return False — engram already erased",
        )

        # erased_at remained at the FIRST call's timestamp (not overwritten by
        # the second). One audit row across both calls.
        conn = sqlite3.connect(str(self.db_path))
        try:
            erased_at = conn.execute(
                "SELECT erased_at FROM engrams WHERE id=? AND tenant_id=?",
                ("e2", "default"),
            ).fetchone()
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM bus_events "
                "WHERE event_type=? AND primary_id=?",
                ("testing.mark_evidence_erased", "e2"),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(erased_at, ("2026-05-24T09:00:00Z",))
        self.assertEqual(
            audit_count, 1,
            "audit event must be written exactly once across idempotent re-calls",
        )

    # ----------------------------------------------------------- audit event

    def test_emits_audit_event_exactly_once(self) -> None:
        """A successful flip writes one audit row with the expected envelope.

        Tests the §15.3.5 contract: event_type == 'testing.mark_evidence_erased',
        primary_id == aggregate_id == engram_id, tenant_id propagated, payload
        names the helper. outbox_sequence > 0 confirms OutboxWriter::append
        actually claimed a sequence number (i.e. ran inside the transaction).
        """
        _seed_engram(self.db_path, engram_id="e3", tenant_id="t-audit")

        self.assertTrue(mark_evidence_erased(
            self.adapter, "e3", "t-audit", "2026-05-24T09:00:00Z"))

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT event_type, primary_id, aggregate_id, tenant_id, "
                "       outbox_sequence, payload_json, created_at "
                "FROM bus_events WHERE primary_id=?",
                ("e3",),
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(len(rows), 1, f"expected 1 audit row, got {rows!r}")
        event_type, primary_id, aggregate_id, tenant_id, seq, payload, created_at = rows[0]
        self.assertEqual(event_type, "testing.mark_evidence_erased")
        self.assertEqual(primary_id, "e3")
        self.assertEqual(aggregate_id, "e3")
        self.assertEqual(tenant_id, "t-audit")
        self.assertIsNotNone(seq, "outbox_sequence must be set, not NULL")
        self.assertGreater(seq, 0, "outbox_sequence must be claimed")
        # created_at is propagated from the caller-supplied erased_at so audit
        # consumers can correlate the event with the row's erased_at without
        # parsing payload_json. A regression that drops the assignment in
        # mark_evidence_erased would surface here as OutboxWriter::append's
        # wall-clock fallback (a different ISO timestamp).
        self.assertEqual(created_at, "2026-05-24T09:00:00Z")
        # Substring assertions tolerate future field additions.
        self.assertIn('"engram_id":"e3"', payload)
        self.assertIn('"tenant_id":"t-audit"', payload)
        self.assertIn('"erased_at":"2026-05-24T09:00:00Z"', payload)
        self.assertIn('"helper":"starling.testing.mark_evidence_erased"', payload)

    # ---------------------------------------------------------- missing row

    def test_missing_row_returns_false(self) -> None:
        """No matching row: returns False and writes no audit event.

        Validates the (id, tenant_id, erased_at IS NULL) WHERE guard handles
        the missing-row case the same way it handles the already-erased case,
        and that the (empty) transaction commits cleanly.
        """
        # Note: no _seed_engram call — the row genuinely doesn't exist.
        result = mark_evidence_erased(
            self.adapter, "ghost", "default", "2026-05-24T09:00:00Z")
        self.assertFalse(result)

        conn = sqlite3.connect(str(self.db_path))
        try:
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM bus_events WHERE event_type=?",
                ("testing.mark_evidence_erased",),
            ).fetchone()[0]
            engram_count = conn.execute(
                "SELECT COUNT(*) FROM engrams WHERE id=?", ("ghost",),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(audit_count, 0, "no audit event for a no-op call")
        self.assertEqual(engram_count, 0, "no row should have been created")


if __name__ == "__main__":
    unittest.main()
