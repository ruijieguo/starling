"""P3.c write-gate follow-up (#8): host-gate the two dashboard admin writes that
bypass the C++ core gate — `_reembed` (raw sqlite DELETE statement_vectors +
tick_one_batch, on config save) and `run_replay` (ReplayScheduler, manual trigger).
Both reuse PR #45's adapter hook (`self._rt.adapter.write_admitted()`), reject on
DRAINING/UNREADY, and stay behavior-neutral in READY.
"""
from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine


def _engine(tmp_path, name):
    cfg = DashboardConfig(db_path=str(tmp_path / name), token="t", tick_interval_s=0)
    return DashboardEngine(cfg)


def test_run_replay_allowed_ready_rejected_draining(tmp_path):
    eng = _engine(tmp_path, "rr.db")
    try:
        assert eng._rt.health() == _core.RuntimeHealth.READY
        r_ready = eng.run_replay("idle")                 # READY → real replay runs
        assert "rejected" not in r_ready
        assert "sampled" in r_ready                       # normal 13-key result shape

        eng.begin_drain()
        assert eng._rt.health() == _core.RuntimeHealth.DRAINING
        r_drain = eng.run_replay("idle")                 # DRAINING → host-gated
        assert r_drain == {"mode": "idle", "rejected": "draining"}
        assert "sampled" not in r_drain                   # ReplayScheduler did NOT run
    finally:
        eng.close()


def test_reembed_allowed_ready_rejected_draining(tmp_path):
    eng = _engine(tmp_path, "re.db")
    try:
        assert eng._rt.health() == _core.RuntimeHealth.READY
        ready = eng._reembed()                            # READY → runs (not drain-gated);
        assert ready is None or "draining" not in ready   # None or an embedding warning, never drain

        eng.begin_drain()
        assert eng._rt.health() == _core.RuntimeHealth.DRAINING
        msg = eng._reembed()                              # host-gated before raw DELETE
        assert msg is not None and "draining" in msg
    finally:
        eng.close()
