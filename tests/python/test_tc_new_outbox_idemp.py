"""TC-NEW-OUTBOX-IDEMP [CRITICAL] — outbox dispatcher crash recovery + idempotency + dead-letter.

Covers M0.2 / §16.2-8 / §3.10 from docs/design/system_design.md §15.3.4.

Setup: 100 events seeded into bus_events with dispatch_status='pending', one
of which has idempotency_key='k-poison' that the consumer always returns
TRANSIENT_ERROR for. A subprocess worker drains the outbox via a pure-Python
re-implementation of OutboxDispatcher.run_once(), but kills itself after N
accepted deliveries to simulate a crash mid-batch. We respawn until the
outbox drains (or we hit a wallclock budget) and then assert four invariants
that lock down the M0.2 acceptance contract:

  1. Every non-poison event's idempotency_key landed in inbox exactly once
     (inbox dedup observed across crash boundary, no double-business-effect).
  2. Total delivery-log lines <= 2 * NUM_EVENTS (bounded retry amplification:
     a row may be tried at most max_retries+1 times, but in practice we cap
     by crashing the worker only AFTER an accept, so the upper bound is
     dominated by the poison row's max_retries=5 plus all 99 normal events).
  3. The poison event's row has dispatch_status='dead_letter' after retry
     exhaustion.
  4. A system.delivery_failed row exists with dispatch_status='delivered'
     (proving the dead-letter recursion guard via append_already_delivered).
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from starling import _core
from starling.bus.bus_event import (
    compute_idempotency_key,
    compute_window_bucket,
)
from starling.testing import relax_preflight_for_m0_2  # NOLINT(starling-testing-isolation)


NUM_EVENTS = 100
POISON_KEY = "k-poison"
TENANT = "tenant-A"
HOLDER_AGG = "agg-A"  # Use a single aggregate so per-aggregate ordering is exercised.
WORKER_FIXTURE = (
    Path(__file__).parent / "_fixtures" / "outbox_crash_worker.py"
)
# Fail-fast budget: at machine speed each worker run drains a few events
# before crashing and a fresh process boot is ~150ms; even the worst-case
# (every event needs a fresh worker) finishes in well under 30s. CI budget
# is generous to absorb cold-cache pyc compilation on first run.
DRAIN_WALLCLOCK_BUDGET_S = 60.0
# Hard ceiling on respawn count — independent of the wallclock budget so a
# pathological "every run delivers 0 events" loop terminates with a useful
# failure message instead of timing out. NUM_EVENTS * 3 is generous: the
# worst plausible case is one accept-then-crash per worker (NUM_EVENTS runs)
# plus poison-retry slop.
MAX_WORKER_RUNS = NUM_EVENTS * 3


class TcNewOutboxIdempTest(unittest.TestCase):
    """End-to-end crash-recovery acceptance for the outbox dispatcher."""

    def setUp(self) -> None:
        # M0.2 preflight relax: drop engram_per_record_key (M0.3 lands KMS) and
        # testing_helper_marker (only loaded by the test target). The original
        # tuple is restored in tearDown so other tests in the same process see
        # the production-shaped LOCAL_STORE_REQUIRED.
        self._original_required = relax_preflight_for_m0_2()

        # tmp_path-equivalent for a unittest.TestCase; we manage cleanup
        # explicitly so subprocess workers can re-open the same file.
        self._tmpdir = tempfile.mkdtemp(prefix="tc_outbox_idemp_")
        self.db_path = Path(self._tmpdir) / "outbox.sqlite3"
        self.log_path = Path(self._tmpdir) / "deliveries.jsonl"

    def tearDown(self) -> None:
        # Restore production capability tuple — relax_preflight_for_m0_2 mutates
        # the module-level global, so failure to restore would leak into other
        # tests in this process. If relax_preflight_for_m0_2's mutation target
        # ever changes, this restore is wrong — keep them in lockstep.
        from starling import runtime as _r
        _r.LOCAL_STORE_REQUIRED = self._original_required

        # No ignore_errors: subprocess.run is synchronous so all workers are
        # reaped before tearDown; a real cleanup failure here is a leaked fd
        # or stray child worth surfacing as a test error.
        shutil.rmtree(self._tmpdir)

    # ------------------------------------------------------------------ helpers

    def _seed_events(self) -> str:
        """Write NUM_EVENTS pending events into the outbox via the test-only
        binding. Returns the idempotency_key of the poison event so the test
        can re-derive it deterministically.
        """
        adapter = _core.SqliteAdapter.open(str(self.db_path))
        poison_idem = ""
        # Lock the test's key derivation to the canonical helper: derive the
        # bucket via compute_window_bucket() so any future refactor of the
        # bucket formula is exercised here, not silently bypassed by a
        # hardcoded literal. For "statement.created" the helper returns "" by
        # design (only "pipeline_run.started" emits a non-empty bucket), which
        # is the property we rely on for purely (event_type, aggregate_id,
        # canonical_key, causation_root)-derived keys.
        empty_bucket = compute_window_bucket(
            "statement.created", datetime.now(timezone.utc)
        )
        for i in range(NUM_EVENTS):
            ev = _core.BusEvent()
            ev.tenant_id = TENANT
            ev.event_type = "statement.created"
            ev.primary_id = f"stmt-{i:03d}"
            ev.aggregate_id = HOLDER_AGG
            ev.causation_chain = []
            if i == NUM_EVENTS // 2:  # mid-batch poison
                ev.idempotency_key = POISON_KEY
                poison_idem = POISON_KEY
            else:
                ev.idempotency_key = compute_idempotency_key(
                    event_type="statement.created",
                    aggregate_id=HOLDER_AGG,
                    canonical_key=f"statement_id=stmt-{i:03d}",
                    causation_root="",
                    window_bucket=empty_bucket,
                )
            ev.payload_json = json.dumps({"i": i})
            ev.version = "v1"
            adapter.append_event_unsafe(ev)  # NOLINT(starling-testing-isolation)
        # Drop adapter handle before subprocesses open the same DB.
        del adapter
        return poison_idem

    def _pending_count(self) -> int:
        with sqlite3.connect(str(self.db_path)) as c:
            row = c.execute(
                "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='pending'"
            ).fetchone()
            return int(row[0])

    def _spawn_worker(self, crash_after_n: int) -> int:
        """Run the worker subprocess once. Returns its exit code."""
        proc = subprocess.run(
            [
                sys.executable,
                str(WORKER_FIXTURE),
                "--db", str(self.db_path),
                "--log", str(self.log_path),
                "--crash-after-n", str(crash_after_n),
                "--poison-key", POISON_KEY,
            ],
            capture_output=True,
            text=True,
            timeout=30.0,
        )
        # Helpful debug if the subprocess crashes for a real reason (not the
        # simulated 137). stderr surfaces tracebacks; stdout is unused.
        if proc.returncode not in (0, 137):
            self.fail(
                f"worker exited unexpectedly: rc={proc.returncode}\n"
                f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
            )
        return proc.returncode

    # -------------------------------------------------------------------- test

    def test_crash_recovery_idempotency_dead_letter(self) -> None:
        # Seed and confirm 100 pending rows landed.
        self._seed_events()
        self.assertEqual(self._pending_count(), NUM_EVENTS)

        # Drain loop. Each iteration either crashes the worker after a
        # configurable number of accepted deliveries (forcing crash recovery)
        # or completes normally (rc=0) after which we declare drained.
        # crash_after_n cycles 3, 7, 11, ... so different windows of the
        # outbox are interrupted across runs — this exercises the recovery
        # path at varied positions instead of always crashing at the same
        # boundary.
        crash_schedule = [3, 7, 11, 17, 23]
        deadline = time.monotonic() + DRAIN_WALLCLOCK_BUDGET_S
        runs = 0
        while True:
            if time.monotonic() > deadline:
                self.fail(
                    f"drain budget exceeded after {runs} runs; "
                    f"pending={self._pending_count()}"
                )
            if runs >= MAX_WORKER_RUNS:
                self.fail(f"hit MAX_WORKER_RUNS={MAX_WORKER_RUNS}")
            crash_after_n = crash_schedule[runs % len(crash_schedule)]
            rc = self._spawn_worker(crash_after_n)
            runs += 1
            # Drained iff: nothing pending AND the previous run did not crash
            # (rc==0 means the worker reached end-of-pending naturally).
            if rc == 0 and self._pending_count() == 0:
                break
            # If rc==137, we crashed mid-drain; loop to spawn another worker.
            # If rc==0 but pending > 0, we delivered everything we could before
            # the consumer marked the rest as TRANSIENT (e.g. all that's left
            # is the poison row mid-retry); also continue.

        # ── invariant 1: inbox dedup ───────────────────────────────────────
        # Every non-poison event's idempotency_key appears in idempotency_inbox
        # exactly once. The poison event never reaches accept, so it never
        # records into the inbox — count == NUM_EVENTS - 1.
        with sqlite3.connect(str(self.db_path)) as c:
            inbox_total = c.execute(
                "SELECT COUNT(*) FROM idempotency_inbox WHERE consumer_id='default'"
            ).fetchone()[0]
            self.assertEqual(
                inbox_total,
                NUM_EVENTS - 1,
                f"inbox should contain exactly {NUM_EVENTS - 1} non-poison keys; "
                f"got {inbox_total}",
            )
            # No idempotency_key appears twice (the unique PK guarantees this
            # at the storage layer; the explicit check makes the assertion
            # readable in failure output).
            dup_rows = c.execute(
                "SELECT idempotency_key, COUNT(*) AS n "
                "FROM idempotency_inbox GROUP BY idempotency_key HAVING n > 1"
            ).fetchall()
            self.assertEqual(dup_rows, [], f"duplicate inbox rows: {dup_rows}")

        # ── invariant 2: bounded retry amplification ───────────────────────
        # Each delivery (accept OR retry of the poison) writes one JSONL line
        # before any crash. Upper bound: 99 accepts + (max_retries=5) poison
        # tries + a small slop for retried events that crashed between
        # consumer-call and commit (they get re-attempted on the next run,
        # but the re-attempt is a fresh delivery-log line).
        log_lines = self.log_path.read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(
            len(log_lines),
            2 * NUM_EVENTS,
            f"delivery log has {len(log_lines)} lines (> 2*{NUM_EVENTS})",
        )

        # ── invariant 3: poison ended up dead-lettered ─────────────────────
        with sqlite3.connect(str(self.db_path)) as c:
            poison_rows = c.execute(
                "SELECT dispatch_status, dispatch_attempts FROM bus_events "
                "WHERE idempotency_key=?",
                (POISON_KEY,),
            ).fetchall()
            self.assertEqual(
                len(poison_rows), 1,
                f"poison row count != 1: {poison_rows}",
            )
            poison_status, poison_attempts = poison_rows[0]
            self.assertEqual(
                poison_status, "dead_letter",
                f"poison final status was {poison_status!r}, "
                f"attempts={poison_attempts}",
            )

        # ── invariant 4: system.delivery_failed emitted with delivered status
        # The dispatcher emits this via OutboxWriter.append_already_delivered,
        # which writes the row with dispatch_status='delivered' so the
        # dispatcher itself never picks it up (recursion guard).
        with sqlite3.connect(str(self.db_path)) as c:
            failed_events = c.execute(
                "SELECT event_id, dispatch_status, primary_id, idempotency_key "
                "FROM bus_events WHERE event_type='system.delivery_failed'"
            ).fetchall()
            self.assertEqual(
                len(failed_events), 1,
                f"expected exactly one system.delivery_failed row, "
                f"got {failed_events}",
            )
            _evt_id, df_status, df_primary, df_idem = failed_events[0]
            self.assertEqual(df_status, "delivered")
            # The primary_id of the failure event is the failed event's id;
            # the idempotency_key suffix encodes the recursion-guard pattern.
            self.assertTrue(
                df_idem.endswith(":delivery_failed"),
                f"failure row idempotency_key did not encode recursion guard: "
                f"{df_idem!r}",
            )


if __name__ == "__main__":
    unittest.main()
