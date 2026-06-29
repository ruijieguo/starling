"""GET /api/runtime_health — P3.c1 Phase 2 (2b) read-only route.

Unlike the SQL-backed inspect routes, this reaches the LIVE in-memory supervisor
through the engine, so the test injects a real DashboardEngine (tick off).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine


@pytest.fixture
def client(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "rh.db"), token="",
                          tick_interval_s=0)
    eng = DashboardEngine(cfg)            # starts READY (embedded preflight passes)
    return TestClient(create_app(cfg, engine=eng)), eng


def test_runtime_health_reports_ready(client):
    c, _eng = client
    r = c.get("/api/runtime_health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "READY"
    assert isinstance(body["events"], list)
    assert body["events"], "start() records a transition event"
    last = body["events"][-1]
    assert last["current_status"] == "READY"
    assert last["previous_status"] == "UNREADY"
    assert last["trigger"] == "preflight_passed"
    assert last["missing_capabilities"] == []
    # MetricsSnapshot mapped to a plain dict, all 7 fields present, 0 in Phase 2.
    ms = last["metrics_snapshot"]
    assert set(ms) == {
        "outbox_lag_sequence", "subscriber_failure_rate", "extraction_queue_depth",
        "projection_lag_seconds", "runtime_event_loop_lag_ms", "vector_delete_lag",
        "erased_evidence_visible_count"}
    assert ms["outbox_lag_sequence"] == 0


def test_runtime_health_reflects_drain(client):
    c, eng = client
    eng.begin_drain()
    body = c.get("/api/runtime_health").json()
    assert body["status"] == "DRAINING"
    assert body["events"][-1]["current_status"] == "DRAINING"
    assert body["events"][-1]["trigger"] == "admin_drain"


def test_runtime_health_503_when_no_engine(tmp_path):
    # engine=None + _engine_or_none is non-lazy (returns app.state.engine as-is)
    # + tick_interval_s=0 (lifespan never builds an engine) → the route MUST 503.
    # Health/events are in-memory; no live engine = nothing to read.
    cfg = DashboardConfig(db_path=str(tmp_path / "rh2.db"), token="",
                          tick_interval_s=0)
    c = TestClient(create_app(cfg))       # engine=None
    r = c.get("/api/runtime_health")
    assert r.status_code == 503
