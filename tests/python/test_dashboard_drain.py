"""Task 2.4 (P3.c1 P2-2a) — host drain wiring.

The C++ RuntimeSupervisor.begin_drain() (READY/DEGRADED -> DRAINING) is reached
from the host through an explicit passthrough chain (OV-5: the bare
engine._runtime._sup path is broken). These tests pin both the engine passthrough
(reaches the LIVE supervisor) and the FastAPI lifespan post-yield drain (D-P2-6).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine


def test_engine_begin_drain_reaches_live_supervisor(tmp_path):
    # OV-5: DashboardEngine.begin_drain() forwards to the LIVE supervisor held by
    # the engine's Runtime — proves the passthrough chain, not the broken module path.
    cfg = DashboardConfig(db_path=str(tmp_path / "drain.db"), token="t",
                          tick_interval_s=0)
    eng = DashboardEngine(cfg)
    try:
        assert eng._rt.health() == _core.RuntimeHealth.READY    # started READY
        eng.begin_drain()
        assert eng._rt.health() == _core.RuntimeHealth.DRAINING
        last = eng._rt._sup.last_event()                        # event logged
        assert last is not None
        assert last.current_status == _core.RuntimeHealth.DRAINING
        assert last.trigger == "admin_drain"                    # default wired end-to-end
    finally:
        eng.close()


def test_lifespan_shutdown_enters_drain(tmp_path):
    # D-P2-6: the lifespan post-yield shutdown half drives begin_drain(). The
    # `with TestClient(...)` context runs the lifespan startup on enter + shutdown
    # on exit (a bare TestClient(app) does NOT run the lifespan).
    cfg = DashboardConfig(db_path=str(tmp_path / "drain2.db"), token="t",
                          tick_interval_s=0)   # tick off — isolate the drain wiring
    eng = DashboardEngine(cfg)
    try:
        app = create_app(cfg, engine=eng)
        with TestClient(app):
            assert eng._rt.health() == _core.RuntimeHealth.READY    # not draining yet
        # context exit ran the post-yield begin_drain()
        assert eng._rt.health() == _core.RuntimeHealth.DRAINING
    finally:
        eng.close()
