"""Smoke test: the flat _core.RuntimeSupervisor binding (Phase 1 governance)."""
from __future__ import annotations

from starling import _core


def _all_present_cap(**overrides):
    base = dict(
        profile_name="local-store",
        c_plus_plus_core=True,
        cross_partition_transaction=True,
        transactional_outbox=True,
        consumer_checkpoint=True,
        tenant_isolation="storage_enforced",
        engram_per_record_key=True,
        engram_refcount=True,
        testing_helper_marker=True,
    )
    base.update(overrides)
    return _core.ProfileCapability(**base)


def test_supervisor_is_flat_on_core():
    # codex#5: bound flat as _core.RuntimeSupervisor, NOT _core.governance.*
    assert hasattr(_core, "RuntimeSupervisor")
    assert _core.kExConfig == 78


def test_supervisor_ready_when_all_present():
    sup = _core.RuntimeSupervisor(_all_present_cap(), False, lambda: True)
    assert sup.start() == _core.StartOutcome.kReady
    assert sup.health() == _core.RuntimeHealth.READY
    assert sup.exit_code() == 0
    assert sup.check_write() == _core.WriteGateDecision.kAccept


def test_supervisor_unready_when_capability_missing():
    sup = _core.RuntimeSupervisor(
        _all_present_cap(transactional_outbox=False), False, lambda: True)
    assert sup.start() == _core.StartOutcome.kUnready
    assert sup.exit_code() == _core.kExConfig
    assert "transactional_outbox" in list(sup.run_preflight().missing_capabilities)


def test_supervisor_embedded_waives_deferred_caps():
    sup = _core.RuntimeSupervisor(
        _all_present_cap(engram_per_record_key=False, testing_helper_marker=False),
        True, lambda: True)
    assert sup.start() == _core.StartOutcome.kReady


def test_required_capabilities_pure():
    assert len(_core.required_capabilities(False)) == 7
    assert len(_core.required_capabilities(True)) == 5
