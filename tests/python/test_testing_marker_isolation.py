"""Runtime defense line for testing-helper isolation (M0.0 Task 6).

The dev/test build links `starling_testing_marker` into the Python `_core`
module; production binaries MUST NOT. These tests verify the marker symbol
is reachable in this build configuration. Task 8 will add the prod-side
preflight check that refuses READY when the marker is loaded under
`profile == "prod"`.
"""


def test_testing_marker_loaded_in_dev_build(core):
    # In M0.0, the dev/test build always links the marker target.
    assert core.testing.marker_loaded() is True


def test_testing_marker_via_python_helper():
    from starling.testing import marker_loaded
    assert marker_loaded() is True


def test_testing_package_all_locks_surface():
    """The testing helper subpackage exports exactly one symbol — locked surface."""
    import starling.testing
    assert starling.testing.__all__ == ["marker_loaded"]
