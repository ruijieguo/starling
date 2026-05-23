def test_runtime_health_enum_exposed(core):
    assert int(core.RuntimeHealth.UNREADY) == 0
    assert int(core.RuntimeHealth.READY) == 1
    assert int(core.RuntimeHealth.DEGRADED) == 2
    assert int(core.RuntimeHealth.DRAINING) == 3
