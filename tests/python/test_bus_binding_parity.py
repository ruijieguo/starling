"""Verify the C++ and Python implementations of compute_idempotency_key
agree byte-for-byte across a representative input matrix.

The two implementations live in:
  - C++:    src/bus/bus_event.cpp           (bound as _core.compute_idempotency_key)
  - Python: python/starling/bus/bus_event.py

Drift here is a P0 outbox correctness regression: the same logical event
would hash to different idempotency_keys on different sides of the seam,
allowing duplicate delivery. The matrix below is the cartesian product of
3 event_types x 3 aggregate_ids x 3 canonical_keys x 2 causation_roots x
3 window_buckets = 162 cases — trimmed below to the 54-case acceptance
matrix specified in the M0.2 plan (3 x 3 x 3 x 2 x 1).
"""

import itertools

import pytest

from starling import _core
from starling.bus.bus_event import compute_idempotency_key as py_compute


_CASES = list(itertools.product(
    ["statement.created", "engram.appended", "system.delivery_failed"],  # 3
    ["holder-1", "holder-2", ""],                                        # 3
    ["k=1", "k=2", "k=very-long-canonical-key-with-lots-of-content"],    # 3
    ["", "evt-root-uuid"],                                               # 2
    [""],                                                                # 1: window_bucket
))                                                                       # = 54
assert len(_CASES) == 54, f"parity matrix changed shape: {len(_CASES)} cases"


@pytest.mark.parametrize(
    "event_type,aggregate_id,canonical_key,causation_root,window_bucket",
    _CASES,
)
def test_idempotency_key_parity(
    event_type, aggregate_id, canonical_key, causation_root, window_bucket
):
    py_key = py_compute(
        event_type=event_type,
        aggregate_id=aggregate_id,
        canonical_key=canonical_key,
        causation_root=causation_root,
        window_bucket=window_bucket,
    )
    cpp_key = _core.compute_idempotency_key(
        event_type, aggregate_id, canonical_key, causation_root, window_bucket,
    )
    assert py_key == cpp_key
    # Sanity: 64-char lowercase hex sha256.
    assert len(cpp_key) == 64
    assert all(c in "0123456789abcdef" for c in cpp_key)
