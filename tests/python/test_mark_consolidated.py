"""Tests for the dev-only `starling.testing.mark_consolidated` helper (M0.5 Task 9).

The helper flips a Statement row's consolidation_state from 'volatile' to
'consolidated' and writes a 'testing.mark_consolidated' audit event in the
same transaction. Idempotent: returns False on already-consolidated, missing,
or any non-volatile row, and emits no audit event in that case so a re-call
never trips UNIQUE(idempotency_key) on bus_events.

Used by TC-NEW-CONFLICT-SEVERE (M0.5 Task 10) to seed S_old in the CONSOLIDATED
state before driving Bus::write through the §15.3.4 atomic SUPERSEDES path.

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
from starling.testing import mark_consolidated  # NOLINT(starling-testing-isolation)


# Column list mirrors test_bus_write_supersedes.cpp:insert_row — the 26
# columns the schema needs explicitly populated. Anything else takes its
# DEFAULT from migration 0001.
_INSERT_SQL = (
    "INSERT INTO statements("
    "id,tenant_id,holder_id,holder_perspective,"
    "subject_kind,subject_id,predicate,object_kind,object_value,"
    "canonical_object_hash,canonical_object_hash_version,modality,"
    "polarity,confidence,observed_at,salience,affect_json,activation,"
    "last_accessed,provenance,consolidation_state,review_status,"
    "valid_from,valid_to,created_at,updated_at"
    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


def _seed_volatile_statement(
    db_path: Path,
    *,
    stmt_id: str = "stmt-test-1",
    tenant_id: str = "default",
    state: str = "volatile",
) -> None:
    """Insert a single statement row with the given consolidation_state.

    Uses stdlib sqlite3 against the same db file the C++ adapter opened. WAL
    mode (set by SqliteAdapter::open) makes this concurrent-safe for
    sequential read/write from a separate Python connection.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            _INSERT_SQL,
            (
                stmt_id, tenant_id, "cog-self", "first_person",
                "cognizer", "cog-bob", "responsible_for", "str", "auth",
                "deadbeef01234567deadbeef01234567deadbeef01234567deadbeef01234567",
                "v1", "believes",
                "pos", 0.9, "2026-05-24T09:00:00Z", 0.5, "{}", 1.0,
                "2026-05-24T09:00:00Z", "user_input", state, "approved",
                None, None,
                "2026-05-24T09:00:00Z", "2026-05-24T09:00:00Z",
            ),
        )
        conn.commit()
    finally:
        conn.close()


class MarkConsolidatedTest(unittest.TestCase):
    """Unit-level coverage for testing.mark_consolidated."""

    def setUp(self) -> None:
        # File-backed SQLite so we can read with stdlib sqlite3 between the
        # C++ adapter's writes — same pattern as test_m0_2_acceptance_smoke.
        # The C++ adapter is dropped before tmpdir cleanup in tearDown so
        # SQLite releases the WAL files cleanly.
        self._tmpdir = TemporaryDirectory(prefix="m0_5_mark_consolidated_")
        self.db_path = Path(self._tmpdir.name) / "starling.sqlite3"
        self.adapter = _core.SqliteAdapter.open(str(self.db_path))

    def tearDown(self) -> None:
        # Drop the adapter (releases the C++ Connection's sqlite3*) BEFORE
        # the tmpdir is cleaned, otherwise WAL files linger and the cleanup
        # races on Linux. macOS tolerates either order.
        self.adapter = None  # type: ignore[assignment]
        self._tmpdir.cleanup()

    # ------------------------------------------------------------- happy path

    def test_volatile_transitions_to_consolidated(self) -> None:
        """A row in 'volatile' state flips to 'consolidated' and returns True."""
        _seed_volatile_statement(self.db_path, stmt_id="s1", tenant_id="default")

        result = mark_consolidated(self.adapter, "s1", "default")
        self.assertTrue(result, "expected True when flipping a volatile row")

        # Verify state landed via stdlib sqlite3 (independent connection ⇒
        # rules out any in-memory cache effect).
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT consolidation_state FROM statements "
                "WHERE id=? AND tenant_id=?",
                ("s1", "default"),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("consolidated",))

    # ------------------------------------------------------------- idempotency

    def test_idempotent_returns_false_on_second_call(self) -> None:
        """Calling twice on the same row: first True, second False; state stays consolidated.

        The audit event is written ONLY on the True call, so the second call
        never trips UNIQUE(idempotency_key) on bus_events. A regression that
        emitted the audit row on every call would surface as a SqliteError
        thrown out of the binding.
        """
        _seed_volatile_statement(self.db_path, stmt_id="s2", tenant_id="default")

        first = mark_consolidated(self.adapter, "s2", "default")
        second = mark_consolidated(self.adapter, "s2", "default")

        self.assertTrue(first, "first call should report True")
        self.assertFalse(
            second,
            "second call must return False — row already consolidated",
        )

        # State remained 'consolidated' (didn't roll back, didn't double-flip).
        conn = sqlite3.connect(str(self.db_path))
        try:
            state = conn.execute(
                "SELECT consolidation_state FROM statements "
                "WHERE id=? AND tenant_id=?",
                ("s2", "default"),
            ).fetchone()
            # Exactly one audit row landed across both calls.
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM bus_events "
                "WHERE event_type=? AND primary_id=?",
                ("testing.mark_consolidated", "s2"),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(state, ("consolidated",))
        self.assertEqual(
            audit_count, 1,
            "audit event must be written exactly once across idempotent re-calls",
        )

    # ----------------------------------------------------------- audit event

    def test_emits_audit_event_exactly_once(self) -> None:
        """A successful flip writes one audit row with the expected envelope.

        Tests Task 9's contract: event_type == 'testing.mark_consolidated',
        primary_id == aggregate_id == stmt_id, tenant_id propagated, payload
        names the helper. outbox_sequence > 0 confirms OutboxWriter::append
        actually claimed a sequence number (i.e. ran inside the transaction).
        """
        _seed_volatile_statement(self.db_path, stmt_id="s3", tenant_id="t-audit")

        self.assertTrue(mark_consolidated(self.adapter, "s3", "t-audit"))

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT event_type, primary_id, aggregate_id, tenant_id, "
                "       outbox_sequence, payload_json "
                "FROM bus_events WHERE primary_id=?",
                ("s3",),
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(len(rows), 1, f"expected 1 audit row, got {rows!r}")
        event_type, primary_id, aggregate_id, tenant_id, seq, payload = rows[0]
        self.assertEqual(event_type, "testing.mark_consolidated")
        self.assertEqual(primary_id, "s3")
        self.assertEqual(aggregate_id, "s3")
        self.assertEqual(tenant_id, "t-audit")
        self.assertGreater(int(seq), 0, "outbox_sequence must be claimed")
        # Payload contains stmt_id + helper marker. Substring assertions
        # (rather than parsed JSON equality) tolerate future field additions.
        self.assertIn('"stmt_id":"s3"', payload)
        self.assertIn('"tenant_id":"t-audit"', payload)
        self.assertIn('"helper":"starling.testing.mark_consolidated"', payload)

    # ---------------------------------------------------------- missing row

    def test_missing_row_returns_false(self) -> None:
        """No matching row: returns False and writes no audit event.

        Validates the (id, tenant_id, state='volatile') WHERE guard handles
        the missing-row case the same way it handles the wrong-state case,
        and that the (empty) transaction commits cleanly.
        """
        # Note: no _seed_volatile_statement call — the row genuinely doesn't
        # exist. mark_consolidated should commit the empty transaction and
        # return False without raising.
        result = mark_consolidated(self.adapter, "ghost", "default")
        self.assertFalse(result)

        conn = sqlite3.connect(str(self.db_path))
        try:
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM bus_events WHERE event_type=?",
                ("testing.mark_consolidated",),
            ).fetchone()[0]
            stmt_count = conn.execute(
                "SELECT COUNT(*) FROM statements WHERE id=?", ("ghost",),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(audit_count, 0, "no audit event for a no-op call")
        self.assertEqual(stmt_count, 0, "no row should have been created")

    # ---------------------------------------------------------- wrong state

    def test_already_consolidated_row_returns_false(self) -> None:
        """A row already in 'consolidated' state (seeded directly) returns False.

        Defense-in-depth: covers the case where some other code path
        (Bus::write hardening, future migration backfill) consolidates a row
        out from under a test-setup helper that expected to do it itself.
        The helper is a no-op rather than throwing, matching the
        idempotent-second-call contract.
        """
        _seed_volatile_statement(
            self.db_path, stmt_id="s4", tenant_id="default",
            state="consolidated",
        )

        result = mark_consolidated(self.adapter, "s4", "default")
        self.assertFalse(result)

        conn = sqlite3.connect(str(self.db_path))
        try:
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM bus_events "
                "WHERE event_type=? AND primary_id=?",
                ("testing.mark_consolidated", "s4"),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(audit_count, 0)


if __name__ == "__main__":
    unittest.main()
