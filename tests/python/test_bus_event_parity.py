"""Pin the Python idempotency_key formula against pre-computed sha256 digests.

The digests below were produced by hashing the canonical material
``"\x1f".join(parts)`` with sha256 — same algorithm the C++ side uses.
The cross-language parity test that calls the C++ implementation lives
in ``tests/python/test_bus_binding_parity.py`` (added in Task 9).
"""

import hashlib
from datetime import datetime, timedelta, timezone

from starling.bus.bus_event import compute_idempotency_key, compute_window_bucket


def _expected(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def test_basic_digest():
    actual = compute_idempotency_key(
        event_type="statement.created",
        aggregate_id="holder-1",
        canonical_key="statement_id=abc",
        causation_root="",
        window_bucket="",
    )
    assert actual == _expected("statement.created", "holder-1", "statement_id=abc", "", "")


def test_separator_prevents_concatenation_collision():
    a = compute_idempotency_key(
        event_type="ab", aggregate_id="", canonical_key="", causation_root="", window_bucket="",
    )
    b = compute_idempotency_key(
        event_type="a", aggregate_id="b", canonical_key="", causation_root="", window_bucket="",
    )
    assert a != b


def test_window_bucket_converts_aware_datetimes_instead_of_replacing_tz():
    # Same wall-clock instant expressed in two timezones must produce the same
    # bucket. Regression test for an earlier .replace(tzinfo=…) bug that
    # silently shifted aware-non-UTC inputs.
    instant_utc = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)
    instant_naive_utc = datetime(2026, 5, 23, 12, 0, 0)
    tokyo = timezone(timedelta(hours=9))
    instant_tokyo = datetime(2026, 5, 23, 21, 0, 0, tzinfo=tokyo)

    bucket_utc = compute_window_bucket("pipeline_run.started", instant_utc)
    bucket_naive = compute_window_bucket("pipeline_run.started", instant_naive_utc)
    bucket_tokyo = compute_window_bucket("pipeline_run.started", instant_tokyo)

    assert bucket_utc == bucket_naive == bucket_tokyo


def _offset_hours(h: int) -> "timedelta":
    from datetime import timedelta
    return timedelta(hours=h)


def test_window_bucket_extraction_and_pipeline_event_families():
    # Pin the new bucket branches added in M0.4. floor(now/60s) for all 7;
    # statement.written returns "" (canonical_key=extraction_span_key path).
    instant = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)
    expected = str(int(instant.timestamp()) // 60)
    bucketed = (
        "extraction.failed",
        "extraction.retry_scheduled",
        "extraction.dead_lettered",
        "extraction.noop",
        "pipeline.run_started",
        "pipeline.run_completed",
        "pipeline.run_failed",
    )
    for et in bucketed:
        assert compute_window_bucket(et, instant) == expected, et

    assert compute_window_bucket("statement.written", instant) == ""
