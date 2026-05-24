"""BusEvent envelope (§3.10) — Python parity with src/bus/bus_event.cpp.

The idempotency_key formula MUST stay byte-identical to the C++ side. The
parity test (tests/python/test_bus_event_parity.py) calls into the pybind
binding and compares against this implementation.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

_SEP = "\x1f"


@dataclass(frozen=True, slots=True, kw_only=True)
class BusEvent:
    event_id: str
    tenant_id: str
    event_type: str
    primary_id: str
    aggregate_id: str
    outbox_sequence: int
    causation_chain: tuple[str, ...]
    idempotency_key: str
    payload_json: str
    created_at: datetime
    version: str = "v1"


def compute_idempotency_key(
    *,
    event_type: str,
    aggregate_id: str,
    canonical_key: str,
    causation_root: str,
    window_bucket: str,
) -> str:
    parts = (event_type, aggregate_id, canonical_key, causation_root, window_bucket)
    raw = _SEP.join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compute_window_bucket(event_type: str, now: datetime) -> str:
    # Naive datetimes are treated as UTC (matching C++ system_clock semantics on
    # macOS/Linux); aware datetimes are converted to UTC, NOT tz-stamped — that
    # would silently shift the bucket for non-UTC inputs.
    if event_type in (
        "pipeline_run.started",
        "evidence.no_store_audit",
        "evidence.idempotent_hit",
        "extraction.failed",
        "extraction.retry_scheduled",
        "extraction.dead_lettered",
        "extraction.noop",
        "pipeline.run_started",
        "pipeline.run_completed",
        "pipeline.run_failed",
    ):
        utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
        return str(int(utc.timestamp()) // 60)
    if event_type == "belief.conflict":
        # 10-second debounce window per 05_bus.md §4.
        utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
        return str(int(utc.timestamp()) // 10)
    if event_type == "statement.recalled":
        # 2-second debounce window per
        # docs/design/subsystems_design/13_retrieval.md
        # §"statement.recalled emit 契约".
        utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
        return str(int(utc.timestamp()) // 2)
    if event_type in ("statement.archived", "statement.superseded"):
        # Per-primary_id is unique on archive/supersede; empty bucket prevents
        # accidental coalescence with a re-emit window.
        return ""
    return ""
