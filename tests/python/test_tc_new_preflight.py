"""TC-NEW-PREFLIGHT [CRITICAL] — system_design.md §15.3.4.

Covers all 4 fail-closed triggers plus the 6 post-conditions, gated through the
M0.0 Runtime supervisor. The Bus / EngramStore stubs used here freeze the
behavioral contract — M0.3 replaces them with real implementations.
"""
from __future__ import annotations

import pytest

from starling import _core
from starling.runtime import Runtime, RuntimeUnreadyError, EX_CONFIG


def _local_store_cap(**overrides):
    base = dict(
        profile_name="local-store",
        relational_backend="seekdb",
        vector_backend="seekdb",
        graph_backend="ladybugdb",
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


# ----- branch (a): missing idx_statement_id_tenant -----
# In M0.0 the index check is delegated to a callable; M0.2 replaces with real SQL.
def test_unready_when_idx_statement_id_tenant_missing():
    cap = _local_store_cap()
    rt = Runtime(
        capability=cap,
        idx_statement_id_tenant_present=lambda: False,
    )
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert rt.health() == _core.RuntimeHealth.UNREADY
    assert "idx_statement_id_tenant" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- branch (b): transactional_outbox = false -----
def test_unready_when_transactional_outbox_false():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert "transactional_outbox" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- branch (c): tenant_isolation = app_filter while profile expects storage_enforced -----
def test_unready_when_app_filter_violates_storage_enforced():
    cap = _local_store_cap(tenant_isolation="app_filter")
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert "tenant_isolation_storage_enforced" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- branch (d): cross_partition_transaction = false but profile claims local_store_atomic -----
def test_unready_when_cross_partition_false_for_local_store_atomic():
    cap = _local_store_cap(cross_partition_transaction=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError) as exc:
        rt.start()
    assert "cross_partition_transaction" in exc.value.missing_capabilities
    assert rt.exit_code == EX_CONFIG


# ----- post-conditions on UNREADY -----
def test_unready_emits_runtime_health_changed_event():
    cap = _local_store_cap(transactional_outbox=False)
    events = []
    rt = Runtime(capability=cap, on_health_change=lambda evt: events.append(evt))
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert len(events) == 1
    evt = events[0]
    assert evt["event"] == "runtime.health_changed"
    assert evt["state"] == "UNREADY"
    assert "transactional_outbox" in evt["missing_capabilities"]


def test_unready_does_not_start_workers():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert rt.foreground_workers_started is False
    assert rt.background_workers_started is False


def test_unready_bus_calls_return_precondition_failed():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert rt.bus.append_evidence({"engram": "stub"}) == "PRECONDITION_FAILED"
    assert rt.bus.write({"stmt": "stub"}) == "PRECONDITION_FAILED"


def test_unready_writes_no_engram_or_statement():
    cap = _local_store_cap(transactional_outbox=False)
    rt = Runtime(capability=cap)
    with pytest.raises(RuntimeUnreadyError):
        rt.start()
    assert rt.engram_store.appended_count == 0
    assert rt.bus.written_count == 0


def test_ready_when_all_capabilities_present():
    cap = _local_store_cap()
    events = []
    rt = Runtime(
        capability=cap,
        on_health_change=lambda evt: events.append(evt),
        idx_statement_id_tenant_present=lambda: True,
    )
    rt.start()
    assert rt.health() == _core.RuntimeHealth.READY
    assert rt.foreground_workers_started is True
    assert rt.background_workers_started is True
    assert events[-1]["state"] == "READY"
