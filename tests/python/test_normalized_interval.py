import pytest
from starling.bus.normalized_interval import (
    NormalizedInterval, UNKNOWN_INTERVAL, normalize_interval,
)

PARITY_CANONICAL_BYTES = "2026-01-01T00:00:00Z/2026-12-31T23:59:59Z"


def test_both_absent_returns_unknown():
    ni = normalize_interval(None, None, None)
    assert ni.is_unknown
    assert ni.canonical_bytes() == "UNKNOWN"


def test_valid_from_only_open_ended():
    ni = normalize_interval("2026-01-01T00:00:00Z", None, None)
    assert not ni.is_unknown
    assert ni.from_ == "2026-01-01T00:00:00Z"
    assert ni.to_is_open
    assert ni.canonical_bytes() == "2026-01-01T00:00:00Z/OPEN"


def test_valid_from_and_to_closed_open():
    ni = normalize_interval("2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z", None)
    assert not ni.is_unknown
    assert ni.from_ == "2026-01-01T00:00:00Z"
    assert ni.to == "2026-06-01T00:00:00Z"
    assert not ni.to_is_open
    assert ni.canonical_bytes() == "2026-01-01T00:00:00Z/2026-06-01T00:00:00Z"


def test_event_time_fallback_open_ended():
    ni = normalize_interval(None, None, "2026-03-15T08:00:00Z")
    assert not ni.is_unknown
    assert ni.from_ == "2026-03-15T08:00:00Z"
    assert ni.to_is_open
    assert ni.canonical_bytes() == "2026-03-15T08:00:00Z/OPEN"


def test_valid_from_takes_priority_over_event_time():
    ni = normalize_interval("2026-01-01T00:00:00Z", None, "2026-03-15T08:00:00Z")
    assert ni.from_ == "2026-01-01T00:00:00Z"
    assert ni.to_is_open


def test_valid_to_ignored_when_valid_from_absent():
    ni = normalize_interval(None, "2026-06-01T00:00:00Z", None)
    assert ni.is_unknown
    assert ni.canonical_bytes() == "UNKNOWN"


def test_parity_canonical_bytes():
    ni = normalize_interval("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z", None)
    assert ni.canonical_bytes() == PARITY_CANONICAL_BYTES


def test_unknown_interval_sentinel_identity():
    ni = normalize_interval(None, None, None)
    assert ni == UNKNOWN_INTERVAL
