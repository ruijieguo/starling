"""M0.2 milestone acceptance smoke — end-to-end SQLite + outbox + dispatcher.

Boots the SQLite-backed Runtime via `_build_local_store_sqlite_runtime`,
seeds a single event through the test-only `append_event_unsafe` shortcut,
drains the outbox once via the Python OutboxDispatcher mirror, and asserts
the four invariants that lock down the M0.2 acceptance contract:

  1. Capabilities surface correctly through SqliteAdapter.declare_capability:
     profile_name="local-store-sqlite", tenant_isolation="storage_enforced",
     transactional_outbox=True, consumer_checkpoint=True.
  2. After draining the outbox once (non-crash, normal ACCEPT path), the
     event's idempotency_key is recorded in idempotency_inbox AND
     consumer_checkpoint.last_delivered_sequence > 0.
  3. The schema_migrations table contains rows for versions 1 and 2 (initial
     schema + extraction_attempt_unique).
  4. The runtime reaches READY (with the M0.2 preflight relax) and the
     SQLite db file exists on disk at the path returned by adapter.db_path.

The crash-recovery / dead-letter / retry-amplification axes are exercised by
TC-NEW-OUTBOX-IDEMP (test_tc_new_outbox_idemp.py); this file is the
non-crash happy path that proves the wiring is right end-to-end.
"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from starling import _core, runtime
from starling.bus.outbox_dispatcher_py import (
    ConsumerDecision,
    DispatchOptions,
    OutboxDispatcherPy,
)
CONSUMER_ID = "default"
SMOKE_IDEMPOTENCY_KEY = "k-smoke-acceptance"


class M02AcceptanceSmokeTest(unittest.TestCase):
    """End-to-end happy-path smoke for the M0.2 SQLite + outbox stack."""

    def setUp(self) -> None:
        # TemporaryDirectory rather than tmp_path because we use unittest, and
        # we want explicit cleanup ordering: drop the runtime/adapter handle
        # first (closes the sqlite3* connection), then remove the directory.
        self._tmpdir = TemporaryDirectory(prefix="m0_2_smoke_")
        self.db_path = Path(self._tmpdir.name) / "starling.sqlite3"

        self.runtime = runtime._build_local_store_sqlite_runtime(self.db_path)

    def tearDown(self) -> None:
        # Drop the runtime (and the adapter it owns) before the tmpdir is
        # cleaned, so the SQLite handle releases the WAL files.
        self.runtime = None  # type: ignore[assignment]
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------ test

    def test_m0_2_acceptance_smoke(self) -> None:
        # ── invariant 4 (precondition): runtime starts READY ─────────────────
        # Boot order matters: capabilities are read off the live adapter,
        # then start() runs preflight (with relax) and flips state to READY.
        # If preflight fails we never reach the assertions below.
        self.runtime.start()
        self.assertEqual(self.runtime.health(), _core.RuntimeHealth.READY)
        self.assertTrue(self.runtime.foreground_workers_started)
        self.assertTrue(self.runtime.background_workers_started)

        adapter = self.runtime.adapter
        self.assertIsNotNone(adapter)

        # ── invariant 4: the db file exists on disk at adapter.db_path ───────
        # The pybind binding exposes db_path as a string property; verify the
        # file the C++ side actually opened matches our temp path and is on
        # disk (not just an in-memory sqlite ":memory:" handle).
        self.assertEqual(Path(adapter.db_path), self.db_path)
        self.assertTrue(self.db_path.is_file(), f"db missing at {self.db_path}")

        # ── invariant 1: capabilities surface ────────────────────────────────
        # ProfileCapability bridges the C++ profile-locked declaration to the
        # Python preflight; these four flags are the M0.2 contract floor.
        cap = adapter.declare_capability()
        self.assertEqual(cap.profile_name, "local-store-sqlite")
        self.assertEqual(cap.tenant_isolation, "storage_enforced")
        self.assertTrue(cap.transactional_outbox)
        self.assertTrue(cap.consumer_checkpoint)

        # ── invariant 3: schema_migrations contains v1 and v2 ────────────────
        # The migration runner stamps schema_migrations row-per-version; we
        # use a dedicated short-lived sqlite3 reader (open-and-close) to avoid
        # contending with the C++ side's WAL writer lock. v1 = initial schema
        # (0001_initial_schema.sql), v2 = extraction_attempt unique span
        # (0002_extraction_attempt_unique.sql).
        conn = sqlite3.connect(str(self.db_path))
        try:
            versions = {
                int(r[0])
                for r in conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            }
        finally:
            conn.close()
        self.assertIn(1, versions, f"missing migration v1; got {sorted(versions)}")
        self.assertIn(2, versions, f"missing migration v2; got {sorted(versions)}")

        # ── seed: append a single event via the test-only shortcut ───────────
        # append_event_unsafe wraps OutboxWriter in a self-contained txn and
        # is NOLINT-marked at the binding site — it exists precisely so this
        # smoke test can populate the outbox without standing up a real
        # producer pipeline. Acceptance scenarios are explicitly allowed to
        # use it (the CI scanner only blocks prod entrypoints).
        ev = _core.BusEvent()
        ev.tenant_id = "tenant-smoke"
        ev.event_type = "statement.created"
        ev.primary_id = "stmt-smoke-1"
        ev.aggregate_id = "agg-smoke"
        ev.idempotency_key = SMOKE_IDEMPOTENCY_KEY
        ev.payload_json = "{}"
        ev.version = "v1"
        adapter.append_event_unsafe(ev)  # NOLINT(starling-testing-isolation)
        self.assertGreater(
            ev.outbox_sequence, 0,
            "OutboxWriter should mutate the BusEvent's outbox_sequence in-place",
        )

        # ── drain: dispatch the outbox once on the happy ACCEPT path ─────────
        # The Python OutboxDispatcher mirror owns its own sqlite3 connection
        # so we close it before re-opening the DB for assertions below; this
        # also rules out any stale-cache reads of the just-committed inbox /
        # checkpoint rows.
        dispatcher = OutboxDispatcherPy(
            db_path=str(self.db_path),
            consumer=lambda _row: ConsumerDecision.ACCEPT,
            options=DispatchOptions(consumer_id=CONSUMER_ID, max_retries=5),
        )
        try:
            stats = dispatcher.run_once()
        finally:
            dispatcher.close()
        self.assertEqual(stats.delivered, 1, f"expected 1 delivered, got {stats}")
        self.assertEqual(stats.retried, 0)
        self.assertEqual(stats.dead_lettered, 0)
        self.assertEqual(stats.skipped_blocked, 0)

        # ── invariant 2: inbox + checkpoint advanced ─────────────────────────
        # Both rows are written in the same transaction as the
        # bus_events.dispatch_status='delivered' update inside _commit_delivered;
        # observing them committed proves the post-accept transaction landed.
        conn = sqlite3.connect(str(self.db_path))
        try:
            inbox_row = conn.execute(
                "SELECT idempotency_key FROM idempotency_inbox "
                "WHERE consumer_id=? AND idempotency_key=?",
                (CONSUMER_ID, SMOKE_IDEMPOTENCY_KEY),
            ).fetchone()
            self.assertIsNotNone(
                inbox_row,
                "idempotency_key not recorded in idempotency_inbox after ACCEPT",
            )

            checkpoint_row = conn.execute(
                "SELECT last_delivered_sequence FROM consumer_checkpoint "
                "WHERE consumer_id=?",
                (CONSUMER_ID,),
            ).fetchone()
            self.assertIsNotNone(checkpoint_row, "consumer_checkpoint row missing")
            self.assertEqual(
                int(checkpoint_row[0]), ev.outbox_sequence,
                f"checkpoint expected {ev.outbox_sequence}, got {checkpoint_row[0]}",
            )

            # Cross-check: bus_events row for our seeded event flipped to
            # 'delivered'. Catches a regression where the dispatcher writes
            # the inbox/checkpoint but forgets the bus_events status update.
            status_row = conn.execute(
                "SELECT dispatch_status FROM bus_events WHERE idempotency_key=?",
                (SMOKE_IDEMPOTENCY_KEY,),
            ).fetchone()
            self.assertEqual(
                status_row, ("delivered",),
                "bus_events.dispatch_status not flipped to delivered",
            )
        finally:
            conn.close()

    # ---------------------------------------------- spec Step 1 assertions

    def test_idx_statement_id_tenant_present(self) -> None:
        # idx_statement_id_tenant_present is a Callable[[], bool] field, not a
        # method. The field is wired in _build_local_store_sqlite_runtime to a
        # closure that probes sqlite_master for the idx_statement_id_tenant
        # index created by migration 0001_initial_schema.sql; if 0001 ran the
        # callable returns True. No start() needed — the migration runs at
        # construction time, well before preflight.
        self.assertTrue(self.runtime.idx_statement_id_tenant_present())

    def test_final_query_predicate_blocks_unguarded_select(self) -> None:
        # SqliteAdapter::check_final_query is the bool predicate variant;
        # returns False if guard predicates are missing, True if both
        # tenant_id and holder_scope appear in the SQL. Mirrors the C++
        # tests/cpp/test_sqlite_adapter.cpp expectations and the underlying
        # is_final_query_safe assertions in test_final_query_assertion.cpp.
        self.assertFalse(
            self.runtime.adapter.check_final_query("SELECT * FROM statements")
        )
        self.assertTrue(
            self.runtime.adapter.check_final_query(
                "SELECT * FROM statements WHERE tenant_id=? AND holder_scope=?"
            )
        )


if __name__ == "__main__":
    unittest.main()
