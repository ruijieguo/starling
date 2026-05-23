"""Starling testing helpers — never import from production code paths."""
from starling._core import testing as _core_testing


def marker_loaded() -> bool:
    return _core_testing.marker_loaded()


def relax_preflight_for_m0_2() -> tuple[str, ...]:
    """Trim engram_per_record_key + testing_helper_marker from LOCAL_STORE_REQUIRED.

    Required by M0.2 acceptance only; M0.3 wires real KMS and removes the
    engram exclusion. The CI static scan (added in M0.0) refuses to merge
    prod entrypoints that import starling.testing — so this can never leak.

    Returns the original tuple so the caller can restore it in tearDown.
    """
    from starling import runtime as _r
    original = _r.LOCAL_STORE_REQUIRED
    _r.LOCAL_STORE_REQUIRED = tuple(
        c for c in original
        if c not in {"engram_per_record_key", "testing_helper_marker"}
    )
    return original


__all__ = ["marker_loaded", "relax_preflight_for_m0_2"]
