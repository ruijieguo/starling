"""Bus envelope + outbox/inbox dedup primitives (M0.2)."""

from starling.bus.bus_event import BusEvent, compute_idempotency_key, compute_window_bucket

__all__ = ["BusEvent", "compute_idempotency_key", "compute_window_bucket"]
