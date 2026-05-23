"""Pure-Python re-implementation of OutboxDispatcher::run_once (M0.2 / §3.10).

This is a TEST-ONLY mirror of `src/bus/outbox_dispatcher.cpp`. It exists so
TC-NEW-OUTBOX-IDEMP can drive the dispatcher from a subprocess that we are
free to SIGKILL mid-batch — the C++ binding does not expose a sqlite3* handle
that survives a Python subprocess restart, so the worker must own its own
sqlite3 connection.

Invariant: this file mirrors the C++ run_once() statement-for-statement. Any
behavior change in the C++ side (transaction shape, blocked_aggregates rule,
dead-letter recursion guard, retry exhaustion test) MUST be ported here, and
vice versa. The acceptance test (test_tc_new_outbox_idemp.py) is the parity
contract — divergence shows up as a CRITICAL test failure.

Notes on faithfulness:
  - We call datetime.now(timezone.utc) inline at each timestamp site to match
    C++ system_clock::now() — same calendar semantics, no module-level
    indirection.
  - dispatch_attempts is incremented by +1 per attempt (C++ does
    `attempts[i] + 1`), not per crash; a crash that flips a row back from
    in_flight to pending leaves dispatch_attempts unchanged, matching C++.
  - The dead-letter path emits `system.delivery_failed` with
    dispatch_status='delivered' via the same outbox INSERT path used for
    normal events, so the schema-level UNIQUE constraint on idempotency_key
    is shared with regular pending rows. The recursion guard is the
    'delivered' status, not a separate table.
"""
from __future__ import annotations

import enum
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable


def _iso8601_utc(dt: datetime) -> str:
    """Whole-second UTC ISO-8601 with trailing 'Z' (matches C++ iso8601_utc)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class ConsumerDecision(enum.Enum):
    """Mirror of starling::bus::ConsumerDecision (uppercase Python idiom)."""

    ACCEPT = "ACCEPT"
    TRANSIENT_ERROR = "TRANSIENT_ERROR"
    PERMANENT_ERROR = "PERMANENT_ERROR"


@dataclass
class BusEventRow:
    """Mutable row mirror of starling::bus::BusEvent.

    Distinct from the immutable Python dataclass in starling.bus.bus_event;
    that one is for envelope construction at the producer side. The
    dispatcher reads rows out of bus_events and we want the simplest possible
    accessor here, not the production envelope.
    """

    event_id: str
    tenant_id: str
    event_type: str
    primary_id: str
    aggregate_id: str
    outbox_sequence: int
    idempotency_key: str
    payload_json: str
    created_at: str
    version: str
    dispatch_attempts: int


@dataclass
class DispatchOptions:
    consumer_id: str = "default"
    max_retries: int = 5
    max_events_per_run: int = 1000
    inbox_ttl: timedelta = field(default_factory=lambda: timedelta(days=7))


@dataclass
class DispatchStats:
    delivered: int = 0
    retried: int = 0
    dead_lettered: int = 0
    skipped_blocked: int = 0


Consumer = Callable[[BusEventRow], ConsumerDecision]


class OutboxDispatcherPy:
    """Pure-Python OutboxDispatcher.run_once for crash-recovery testing.

    Each instance owns a sqlite3 connection. Transactions are managed manually
    (BEGIN IMMEDIATE / COMMIT / ROLLBACK) to mirror C++ TransactionGuard.
    """

    def __init__(
        self,
        db_path: str,
        consumer: Consumer,
        options: DispatchOptions | None = None,
    ) -> None:
        self._db_path = db_path
        self._consumer = consumer
        self._opts = options or DispatchOptions()
        # isolation_level=None puts us in "autocommit" mode where we drive
        # transactions explicitly with BEGIN/COMMIT — that matches the C++
        # TransactionGuard semantics. timeout=5.0 absorbs WAL contention if
        # multiple workers ever overlap (they shouldn't in the test, but it's
        # cheap insurance).
        self._conn = sqlite3.connect(db_path, isolation_level=None, timeout=5.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------ public

    def run_once(self) -> DispatchStats:
        stats = DispatchStats()
        c = self._conn

        # Crash recovery: any row stuck in 'in_flight' from a previous worker
        # that died after the UPDATE-to-in_flight but before the consumer
        # outcome was written. Reset back to 'pending' so the SELECT below
        # picks them up. C++ does the same UPDATE before the SELECT.
        c.execute(
            "UPDATE bus_events SET dispatch_status='pending' "
            "WHERE dispatch_status='in_flight'"
        )

        # Snapshot pending events by ascending outbox_sequence.
        # NOTE: causation_chain_json is intentionally omitted from this SELECT
        # (and from BusEventRow) — the dispatcher never reads it on the read
        # path; downstream consumers re-query the row when they need the
        # chain. Mirrors the C++ comment at src/bus/outbox_dispatcher.cpp:77-78.
        rows = c.execute(
            "SELECT event_id,tenant_id,event_type,primary_id,aggregate_id,"
            "outbox_sequence,idempotency_key,payload_json,created_at,"
            "version,dispatch_attempts "
            "FROM bus_events WHERE dispatch_status='pending' "
            "ORDER BY outbox_sequence ASC LIMIT ?",
            (self._opts.max_events_per_run,),
        ).fetchall()

        pending: list[BusEventRow] = [
            BusEventRow(
                event_id=r[0],
                tenant_id=r[1] or "",
                event_type=r[2] or "",
                primary_id=r[3] or "",
                aggregate_id=r[4] or "",
                outbox_sequence=r[5],
                idempotency_key=r[6] or "",
                payload_json=r[7] or "",
                created_at=r[8] or "",
                version=r[9] or "",
                dispatch_attempts=r[10] or 0,
            )
            for r in rows
        ]

        blocked_aggregates: set[str] = set()

        for ev in pending:
            if ev.aggregate_id in blocked_aggregates:
                stats.skipped_blocked += 1
                continue

            # Mark in_flight in its own transaction so a crash mid-consumer
            # leaves a recoverable trail. The next run_once flips this back
            # to 'pending' before its SELECT.
            self._mark_in_flight(ev)

            decision = ConsumerDecision.TRANSIENT_ERROR
            err: str = ""
            try:
                decision = self._consumer(ev)
            except Exception as exc:  # noqa: BLE001 — mirror C++ catch-all
                err = str(exc) or exc.__class__.__name__

            new_attempts = ev.dispatch_attempts + 1

            if decision == ConsumerDecision.ACCEPT:
                self._commit_delivered(ev, new_attempts)
                stats.delivered += 1
                continue

            exhausted = (
                decision == ConsumerDecision.PERMANENT_ERROR
                or new_attempts >= self._opts.max_retries
            )

            if not exhausted:
                self._commit_retry(ev, new_attempts, err)
                stats.retried += 1
                blocked_aggregates.add(ev.aggregate_id)
                continue

            self._commit_dead_letter(ev, new_attempts, err)
            stats.dead_lettered += 1
            blocked_aggregates.add(ev.aggregate_id)

        return stats

    # ----------------------------------------------------------- internal txns

    def _mark_in_flight(self, ev: BusEventRow) -> None:
        c = self._conn
        ts = _iso8601_utc(datetime.now(timezone.utc))
        c.execute("BEGIN IMMEDIATE")
        try:
            c.execute(
                "UPDATE bus_events SET dispatch_status='in_flight', "
                "last_attempt_at=? WHERE event_id=? AND dispatch_status='pending'",
                (ts, ev.event_id),
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def _commit_delivered(self, ev: BusEventRow, new_attempts: int) -> None:
        c = self._conn
        now = datetime.now(timezone.utc)
        ts = _iso8601_utc(now)
        c.execute("BEGIN IMMEDIATE")
        try:
            # IdempotencyInbox.record_if_new — INSERT OR IGNORE, observed via
            # changes() but not branched on (C++ comment: "both branches
            # commit delivered here").
            c.execute(
                "INSERT OR IGNORE INTO idempotency_inbox("
                "consumer_id,idempotency_key,received_at,expires_at) "
                "VALUES(?,?,?,?)",
                (
                    self._opts.consumer_id,
                    ev.idempotency_key,
                    ts,
                    _iso8601_utc(now + self._opts.inbox_ttl),
                ),
            )
            c.execute(
                "UPDATE bus_events SET dispatch_status='delivered',"
                "dispatch_attempts=?, last_attempt_at=? WHERE event_id=?",
                (new_attempts, ts, ev.event_id),
            )
            # ConsumerCheckpoint.advance — UPSERT with MAX guard.
            c.execute(
                "INSERT INTO consumer_checkpoint("
                "consumer_id,last_delivered_sequence,updated_at) "
                "VALUES(?,?,?) "
                "ON CONFLICT(consumer_id) DO UPDATE SET "
                "  last_delivered_sequence=MAX("
                "    consumer_checkpoint.last_delivered_sequence,"
                "    excluded.last_delivered_sequence),"
                "  updated_at=excluded.updated_at",
                (self._opts.consumer_id, ev.outbox_sequence, ts),
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def _commit_retry(
        self, ev: BusEventRow, new_attempts: int, err: str
    ) -> None:
        c = self._conn
        ts = _iso8601_utc(datetime.now(timezone.utc))
        error_text = err or "transient_error"
        c.execute("BEGIN IMMEDIATE")
        try:
            c.execute(
                "UPDATE bus_events SET dispatch_status='pending',"
                "dispatch_attempts=?, last_attempt_at=?, last_error=? "
                "WHERE event_id=?",
                (new_attempts, ts, error_text, ev.event_id),
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def _commit_dead_letter(
        self, ev: BusEventRow, new_attempts: int, err: str
    ) -> None:
        c = self._conn
        ts = _iso8601_utc(datetime.now(timezone.utc))
        error_text = err or "permanent_error"
        c.execute("BEGIN IMMEDIATE")
        try:
            c.execute(
                "UPDATE bus_events SET dispatch_status='dead_letter',"
                "dispatch_attempts=?, last_attempt_at=?, last_error=? "
                "WHERE event_id=?",
                (new_attempts, ts, error_text, ev.event_id),
            )
            # Recursion guard: emit system.delivery_failed with
            # dispatch_status='delivered' so the dispatcher never picks it up.
            # Mirrors OutboxWriter::append_already_delivered. We claim a
            # sequence from outbox_sequence_counter exactly the way C++ does
            # so the new row interleaves correctly.
            failure_seq = self._claim_next_sequence()
            failure_event_id = str(uuid.uuid4())
            failure_idem = ev.idempotency_key + ":delivery_failed"
            # C++ has the "event_id is UUID-like, no escaping needed" excuse
            # but random_event_id in this port admits it's not a real UUID and
            # M0.4 will replace it — Python uses json.dumps defensively.
            failure_payload = json.dumps({"failed_event_id": ev.event_id})
            failure_chain = json.dumps([ev.event_id])
            c.execute(
                "INSERT INTO bus_events("
                "event_id,tenant_id,event_type,primary_id,aggregate_id,"
                "outbox_sequence,causation_chain_json,idempotency_key,"
                "payload_json,created_at,version,dispatch_status) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    failure_event_id,
                    ev.tenant_id,
                    "system.delivery_failed",
                    ev.event_id,            # primary_id := failed event id
                    ev.aggregate_id,
                    failure_seq,
                    failure_chain,
                    failure_idem,
                    failure_payload,
                    ts,
                    "v1",
                    "delivered",            # recursion guard
                ),
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def _claim_next_sequence(self) -> int:
        c = self._conn
        row = c.execute(
            "SELECT next_value FROM outbox_sequence_counter WHERE id=1"
        ).fetchone()
        if row is None:
            raise RuntimeError(
                "outbox_sequence_counter row id=1 missing "
                "(migration 0001 should have seeded it)"
            )
        claimed = int(row[0])
        c.execute(
            "UPDATE outbox_sequence_counter SET next_value=next_value+1 "
            "WHERE id=1"
        )
        return claimed


__all__ = [
    "BusEventRow",
    "ConsumerDecision",
    "DispatchOptions",
    "DispatchStats",
    "OutboxDispatcherPy",
]
