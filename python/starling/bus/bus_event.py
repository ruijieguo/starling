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
    if event_type == "pipeline_run.started":
        utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
        return str(int(utc.timestamp()) // 60)
    return ""
