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


def test_supervisor_event_log_records_start_transition():
    # Task 2.3: start() records exactly one transition event, readable via the
    # bound events()/last_event() snapshot surface.
    sup = _core.RuntimeSupervisor(_all_present_cap(), False, lambda: True)
    sup.start()
    evts = sup.events()
    assert isinstance(evts, list)
    assert len(evts) == 1
    last = sup.last_event()
    assert last is not None
    assert last.previous_status == _core.RuntimeHealth.UNREADY
    assert last.current_status == _core.RuntimeHealth.READY
    assert last.trigger == "preflight_passed"
    assert list(last.missing_capabilities) == []


def test_supervisor_last_event_none_before_any_transition():
    # last_event() is None on a fresh supervisor (no transitions yet); the
    # std::optional<RuntimeHealthEvent> binding maps nullopt -> None.
    sup = _core.RuntimeSupervisor(_all_present_cap(), False, lambda: True)
    assert sup.last_event() is None
    assert sup.events() == []


def test_supervisor_begin_drain_default_trigger():
    # OV-8: begin_drain() defaults trigger='admin_drain'; READY -> DRAINING.
    sup = _core.RuntimeSupervisor(_all_present_cap(), False, lambda: True)
    sup.start()
    sup.begin_drain()
    assert sup.health() == _core.RuntimeHealth.DRAINING
    last = sup.last_event()
    assert last.current_status == _core.RuntimeHealth.DRAINING
    assert last.trigger == "admin_drain"


def test_supervisor_note_health_applies_decision():
    # note_health(HealthDecision) drives a legal transition (READY -> DEGRADED).
    sup = _core.RuntimeSupervisor(_all_present_cap(), False, lambda: True)
    sup.start()
    dec = _core.HealthDecision()
    dec.target_status = _core.RuntimeHealth.DEGRADED
    dec.trigger = "sampler_backpressure"
    sup.note_health(dec)
    assert sup.health() == _core.RuntimeHealth.DEGRADED
    assert sup.last_event().trigger == "sampler_backpressure"


def test_metrics_snapshot_defaults_zeroed():
    # MetricsSnapshot is constructible with 0/sentinel defaults (Phase 5 fills real values).
    ms = _core.MetricsSnapshot()
    assert ms.outbox_lag_sequence == 0
    assert ms.subscriber_failure_rate == 0.0
    assert ms.extraction_queue_depth == 0
    assert ms.projection_lag_seconds == 0.0
    assert ms.runtime_event_loop_lag_ms == 0.0
    assert ms.vector_delete_lag == 0
    assert ms.erased_evidence_visible_count == 0


def test_runtime_health_event_snapshot_is_value_copy():
    # OV-2: events() returns deep value copies — mutating the supervisor after
    # taking a snapshot does NOT change the already-returned event list.
    sup = _core.RuntimeSupervisor(_all_present_cap(), False, lambda: True)
    sup.start()         # event 0: -> READY
    snapshot = sup.events()
    sup.begin_drain()   # adds event 1: -> DRAINING
    assert len(snapshot) == 1                                  # earlier snapshot unaffected
    assert snapshot[0].current_status == _core.RuntimeHealth.READY
    assert len(sup.events()) == 2                              # a fresh snapshot sees both
