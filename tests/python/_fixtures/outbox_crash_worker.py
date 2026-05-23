"""Subprocess fixture for TC-NEW-OUTBOX-IDEMP.

Driven by tests/python/test_tc_new_outbox_idemp.py. Each invocation:
  1. Opens the outbox SQLite DB (passed via --db).
  2. Constructs an OutboxDispatcherPy with a consumer that:
       - returns TRANSIENT_ERROR for the poison idempotency_key
       - else appends a JSONL line to the delivery log and returns ACCEPT
  3. Runs run_once() once, but the consumer self-kills via os._exit(137)
     after `--crash-after-n` ACCEPT decisions to simulate a SIGKILL between
     consumer-body and commit-delivered (i.e. the row is in_flight when the
     process dies). Crash recovery on the next run_once flips it back to
     pending.

Exit codes:
  0   — drained or run_once() completed normally without hitting the cap
  137 — simulated crash after `crash_after_n` accepts (orchestrator respawns)
  2   — argparse / unexpected error (test fails fast in this case)

The JSONL log is opened with line-buffering (`buffering=1`) so a SIGKILL
mid-batch still flushes the most recent delivery line to disk before the
process dies — this is what gives invariant 2 (delivery count bound) a
reliable signal across crashes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import IO


# Ensure the in-tree starling package is importable when this file is invoked
# directly via `python <path>` from a subprocess. pytest's rootdir injection
# does not apply to subprocess.run children. We resolve the repo root by
# walking up until we find python/starling.
_HERE = Path(__file__).resolve()
for _parent in _HERE.parents:
    if (_parent / "python" / "starling").is_dir():
        sys.path.insert(0, str(_parent / "python"))
        break

from starling.bus.outbox_dispatcher_py import (  # noqa: E402  — sys.path adjusted above
    BusEventRow,
    ConsumerDecision,
    DispatchOptions,
    OutboxDispatcherPy,
)


def _build_consumer(
    log_fp: IO[str],
    crash_after_n: int,
    poison_key: str,
):
    """Return a closure that mirrors the test's consumer body.

    State:
      - accept_count: number of ACCEPT decisions returned so far in this run
    """
    accept_count = {"n": 0}

    def consumer(ev: BusEventRow) -> ConsumerDecision:
        # Poison: never accept. The dispatcher will retry up to max_retries=5
        # then dead-letter. We don't write a JSONL line for transient/permanent
        # errors — that keeps the line count proportional to ACCEPT attempts,
        # which is what invariant 2 actually bounds.
        if ev.idempotency_key == poison_key:
            return ConsumerDecision.TRANSIENT_ERROR

        # Record the delivery attempt BEFORE incrementing accept_count so the
        # JSONL line is on disk if we crash on this iteration. line-buffered
        # write + flush guarantees the bytes are visible to the test on the
        # next process boot.
        log_fp.write(json.dumps({
            "event_id": ev.event_id,
            "outbox_sequence": ev.outbox_sequence,
            "idempotency_key": ev.idempotency_key,
            "primary_id": ev.primary_id,
            "attempts_before": ev.dispatch_attempts,
        }) + "\n")
        log_fp.flush()
        try:
            os.fsync(log_fp.fileno())
        except OSError:
            # fsync is best-effort here: the prior flush() already pushed the
            # bytes past the Python buffer, which is what invariant 2 needs to
            # observe across a SIGKILL. We don't need fsync's full disk-cache
            # guarantee in this test.
            pass

        accept_count["n"] += 1
        if accept_count["n"] >= crash_after_n:
            # Hard kill: bypass cleanup so the in-flight row stays in_flight
            # and crash recovery on the next run_once flips it back to pending.
            # 137 = 128 + SIGKILL(9), matches the convention test_*_idemp
            # treats as the "expected crash" rc.
            os._exit(137)

        return ConsumerDecision.ACCEPT

    return consumer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="SQLite DB path")
    parser.add_argument("--log", required=True, help="JSONL delivery log path")
    parser.add_argument(
        "--crash-after-n",
        type=int,
        required=True,
        help="Self-kill via os._exit(137) after this many ACCEPTs",
    )
    parser.add_argument(
        "--poison-key",
        required=True,
        help="Consumer returns TRANSIENT_ERROR for events with this "
        "idempotency_key (forces dead-letter after max_retries).",
    )
    args = parser.parse_args()

    # Open the JSONL log in append mode with line buffering so partial output
    # survives SIGKILL. The orchestrator reads this file across restarts.
    log_fp = open(args.log, "a", buffering=1, encoding="utf-8")
    try:
        consumer = _build_consumer(log_fp, args.crash_after_n, args.poison_key)
        dispatcher = OutboxDispatcherPy(
            db_path=args.db,
            consumer=consumer,
            options=DispatchOptions(),  # defaults: consumer_id=default, max_retries=5
        )
        try:
            dispatcher.run_once()
        finally:
            dispatcher.close()
    finally:
        log_fp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
