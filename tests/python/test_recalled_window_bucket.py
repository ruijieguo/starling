from datetime import datetime, timezone

from starling.bus.bus_event import compute_window_bucket


def _t(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def test_buckets_by_2_seconds():
    t0 = _t(1_000_000_000)
    t1 = _t(1_000_000_001)
    t2 = _t(1_000_000_002)
    assert compute_window_bucket("statement.recalled", t0) == \
           compute_window_bucket("statement.recalled", t1)
    assert compute_window_bucket("statement.recalled", t0) != \
           compute_window_bucket("statement.recalled", t2)


def test_expected_string_value():
    assert compute_window_bucket("statement.recalled", _t(1_000_000_000)) == "500000000"
