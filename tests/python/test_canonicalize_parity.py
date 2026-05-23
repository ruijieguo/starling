"""C++ ↔ Python canonicalize must agree byte-for-byte on every supported input."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from starling.schema.value import canonicalize_object as py_canon
from starling._core import canonicalize_object_cpp as cpp_canon
from starling.schema.refs import CognizerRef, EntityRef, StatementRef


def _both(value):
    p = py_canon(value)
    c = cpp_canon(value)
    return p, c


@pytest.mark.parametrize("value", [
    True, False, 0, 1, -17, 1_000_000,
    0.0, -0.0, 1.5, -3.25,
    "hello", "  Hello   World  ", "café",
    datetime(2026, 5, 23, 12, 30, 45, tzinfo=timezone.utc),
    datetime(2026, 5, 23, 20, 30, 45, tzinfo=timezone(timedelta(hours=8))),
])
def test_python_cpp_parity_scalars(value):
    p, c = _both(value)
    assert p == c, f"parity mismatch on {value!r}: py={p} cpp={c}"


def test_parity_refs():
    u = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    for cls in (CognizerRef, EntityRef, StatementRef):
        p, c = _both(cls(u))
        assert p == c
