"""P3.c1 Phase 5 — backpressure sampler integration tests.

Tests HealthSampler/MetricsGatherer bindings and the DashboardEngine host wiring
(debounce + DRAINING suppress + tick-delay).  Engine construction mirrors
test_dashboard_engine.py.
"""
from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from starling import _core
from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine


# ── helpers ─────────────────────────────────────────────────────────────────

_NOW = "2026-06-30T00:00:00Z"


def _engine(tmp_path, *, outbox_lag_threshold: int = 100,
            loop_lag_threshold_ms: float = 200.0,
            debounce_ticks: int = 2) -> DashboardEngine:
    """Build an engine with an injected low-threshold HealthSamplerConfig."""
    cfg = DashboardConfig(db_path=str(tmp_path / "bp.db"), token="t")
    eng = DashboardEngine(cfg)
    # Inject a sampler + gatherer with the caller's thresholds.
    eng._replace_sampler(
        outbox_lag_threshold=outbox_lag_threshold,
        loop_lag_threshold_ms=loop_lag_threshold_ms,
        debounce_ticks=debounce_ticks,
    )
    return eng


def _seed_lag(db_path: str, lag: int) -> None:
    """Insert bus_events with outbox_sequence advancing by `lag`; leave the
    in_process consumer_checkpoint at 0 (absent → treated as 0).  This
    produces outbox_lag_sequence == lag in the gatherer query.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    for seq in range(1, lag + 1):
        conn.execute(
            "INSERT INTO bus_events"
            "(event_id,tenant_id,event_type,primary_id,aggregate_id,"
            " outbox_sequence,idempotency_key,payload_json,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (f"bp-evt-{seq}", "tenant-1", "test.event", "p-1", "agg-1",
             seq, f"idem-bp-{seq}", "{}", _NOW),
        )
    conn.commit()
    conn.close()


def _set_checkpoint(db_path: str, delivered_seq: int) -> None:
    """Upsert the in_process consumer checkpoint to delivered_seq (clears lag)."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        "INSERT INTO consumer_checkpoint(consumer_id,last_delivered_sequence,updated_at)"
        " VALUES('in_process',?,?)"
        " ON CONFLICT(consumer_id) DO UPDATE SET"
        "   last_delivered_sequence=excluded.last_delivered_sequence,"
        "   updated_at=excluded.updated_at",
        (delivered_seq, _NOW),
    )
    conn.commit()
    conn.close()


# ── Phase 5 binding smoke tests ──────────────────────────────────────────────

class TestHealthSamplerBinding:
    def test_numeric_metric_cfg_defaults(self):
        cfg = _core.NumericMetricCfg()
        assert cfg.enabled is False
        assert cfg.threshold == 0

    def test_float_metric_cfg_defaults(self):
        cfg = _core.FloatMetricCfg()
        assert cfg.enabled is False
        assert cfg.threshold == 0.0

    def test_erased_evidence_cfg_defaults(self):
        cfg = _core.ErasedEvidenceCfg()
        assert cfg.enabled is False

    def test_health_sampler_config_constructible(self):
        scfg = _core.HealthSamplerConfig()
        assert scfg.outbox_lag.enabled is False
        assert scfg.runtime_event_loop_lag_ms.enabled is False

    def test_health_sampler_ready_when_all_disabled(self):
        scfg = _core.HealthSamplerConfig()  # all disabled
        sampler = _core.HealthSampler(scfg)
        snap = _core.MetricsSnapshot()
        snap.outbox_lag_sequence = 9999  # over any threshold — but disabled
        decision = sampler.evaluate(snap)
        assert decision.target_status == _core.RuntimeHealth.READY
        assert decision.trigger == "backpressure_recovered"

    def test_health_sampler_degraded_when_outbox_lag_over(self):
        scfg = _core.HealthSamplerConfig()
        scfg.outbox_lag.enabled = True
        scfg.outbox_lag.threshold = 5
        sampler = _core.HealthSampler(scfg)
        snap = _core.MetricsSnapshot()
        snap.outbox_lag_sequence = 6  # > 5 → DEGRADED
        decision = sampler.evaluate(snap)
        assert decision.target_status == _core.RuntimeHealth.DEGRADED
        assert "outbox_lag" in decision.trigger

    def test_health_sampler_ready_at_threshold_boundary(self):
        scfg = _core.HealthSamplerConfig()
        scfg.outbox_lag.enabled = True
        scfg.outbox_lag.threshold = 5
        sampler = _core.HealthSampler(scfg)
        snap = _core.MetricsSnapshot()
        snap.outbox_lag_sequence = 5  # == threshold → NOT over (strict >)
        decision = sampler.evaluate(snap)
        assert decision.target_status == _core.RuntimeHealth.READY

    def test_health_sampler_float_metric_degraded(self):
        scfg = _core.HealthSamplerConfig()
        scfg.runtime_event_loop_lag_ms.enabled = True
        scfg.runtime_event_loop_lag_ms.threshold = 100.0
        sampler = _core.HealthSampler(scfg)
        snap = _core.MetricsSnapshot()
        snap.runtime_event_loop_lag_ms = 101.0
        decision = sampler.evaluate(snap)
        assert decision.target_status == _core.RuntimeHealth.DEGRADED
        assert "runtime_event_loop_lag_ms" in decision.trigger

    def test_metrics_gatherer_constructible(self):
        gatherer = _core.MetricsGatherer()
        assert gatherer is not None


class TestMetricsGathererBinding:
    def test_gather_via_adapter_empty_db(self, tmp_path):
        from starling import _core as core
        adapter = core.SqliteAdapter.open(str(tmp_path / "mg.db"))
        gatherer = core.MetricsGatherer()
        snap = gatherer.gather(adapter)
        assert snap.outbox_lag_sequence == 0

    def test_gather_via_adapter_with_seeded_lag(self, tmp_path):
        db = str(tmp_path / "mg2.db")
        from starling import _core as core
        adapter = core.SqliteAdapter.open(db)
        # Seed lag outside the adapter's connection so we can re-open cleanly.
        # The adapter already ran migrations so the schema is ready.
        _seed_lag(db, 3)          # sequences 1,2,3 — no checkpoint → lag=3
        gatherer = core.MetricsGatherer()
        snap = gatherer.gather(adapter)
        assert snap.outbox_lag_sequence == 3


# ── Engine host-wiring tests ──────────────────────────────────────────────────

class TestEngineDebounceTransition:
    def test_seeded_lag_degrades_after_debounce(self, tmp_path):
        """N consecutive over-threshold ticks → DEGRADED (trigger names outbox_lag)."""
        eng = _engine(tmp_path, outbox_lag_threshold=2, debounce_ticks=2)
        # Seed enough lag to exceed threshold=2 → gatherer sees lag≥3.
        _seed_lag(eng._db_path, 5)
        # First tick: debounce counter = 1, not yet at N=2 → stays READY.
        eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.READY
        # Second tick: debounce counter = 2 = N → fires.
        eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.DEGRADED
        last = eng._rt.last_event()
        assert last is not None
        assert "outbox_lag" in last.trigger
        snap = last.metrics_snapshot
        assert snap.outbox_lag_sequence >= 3

    def test_recovery_to_ready_after_debounce(self, tmp_path):
        """After DEGRADED: clear lag, N ticks → READY (trigger=backpressure_recovered)."""
        eng = _engine(tmp_path, outbox_lag_threshold=2, debounce_ticks=2)
        _seed_lag(eng._db_path, 5)
        # Drive to DEGRADED.
        for _ in range(2):
            eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.DEGRADED
        # Fully advance checkpoint → lag=0.
        _set_checkpoint(eng._db_path, 5)
        # Two READY verdicts → debounce fires → READY.
        for _ in range(2):
            eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.READY
        last = eng._rt.last_event()
        assert last.trigger == "backpressure_recovered"

    def test_debounce_no_flap_single_tick(self, tmp_path):
        """A single over-threshold tick (< debounce_ticks=2) does NOT transition."""
        eng = _engine(tmp_path, outbox_lag_threshold=2, debounce_ticks=2)
        _seed_lag(eng._db_path, 5)
        eng._sample_backpressure(time.monotonic(), 60.0)   # 1 out of 2 required
        assert eng.health() == _core.RuntimeHealth.READY

    def test_debounce_resets_on_verdict_change(self, tmp_path):
        """If the verdict alternates (DEGRADED/READY/DEGRADED), debounce resets —
        must see N consecutive same verdicts to fire."""
        eng = _engine(tmp_path, outbox_lag_threshold=2, debounce_ticks=3)
        _seed_lag(eng._db_path, 5)
        # 2 DEGRADED verdicts (not yet 3).
        eng._sample_backpressure(time.monotonic(), 60.0)
        eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.READY  # not yet
        # Advance checkpoint → next verdict READY → resets debounce run.
        _set_checkpoint(eng._db_path, 5)
        eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.READY  # still READY (reset)
        # Seed more lag: insert events with seq > 5 (above the checkpoint).
        conn = sqlite3.connect(eng._db_path)
        conn.execute("PRAGMA busy_timeout=5000")
        for seq in range(6, 12):
            conn.execute(
                "INSERT INTO bus_events"
                "(event_id,tenant_id,event_type,primary_id,aggregate_id,"
                " outbox_sequence,idempotency_key,payload_json,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (f"bp2-{seq}", "tenant-1", "test.event", "p-1", "agg-1",
                 seq, f"idem2-{seq}", "{}", _NOW),
            )
        conn.commit()
        conn.close()
        # 3 consecutive DEGRADED verdicts (lag=6, threshold=2) → fires.
        for _ in range(3):
            eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.DEGRADED


class TestEngineDrainingSuppression:
    def test_draining_suppresses_sampler(self, tmp_path):
        """Engine in DRAINING: high lag tick must NOT flip to DEGRADED (L7)."""
        eng = _engine(tmp_path, outbox_lag_threshold=2, debounce_ticks=1)
        # Enter DRAINING.
        eng.begin_drain()
        assert eng.health() == _core.RuntimeHealth.DRAINING
        # Seed high lag.
        _seed_lag(eng._db_path, 50)
        # Multiple sampler ticks — all suppressed.
        for _ in range(5):
            eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.DRAINING

    def test_unready_suppresses_sampler(self, tmp_path):
        """Engine in UNREADY (forced via note_health): sampler is suppressed."""
        eng = _engine(tmp_path, outbox_lag_threshold=2, debounce_ticks=1)
        # Force UNREADY via note_health.
        dec = _core.HealthDecision()
        dec.target_status = _core.RuntimeHealth.UNREADY
        dec.trigger = "test_force_unready"
        eng._rt._sup.note_health(dec)
        assert eng.health() == _core.RuntimeHealth.UNREADY
        _seed_lag(eng._db_path, 50)
        for _ in range(3):
            eng._sample_backpressure(time.monotonic(), 60.0)
        assert eng.health() == _core.RuntimeHealth.UNREADY


class TestEngineTickDelayMetric:
    def test_loop_lag_set_from_tick_delay(self, tmp_path):
        """Simulate a large tick delay → runtime_event_loop_lag_ms in snapshot."""
        eng = _engine(tmp_path, loop_lag_threshold_ms=50.0, debounce_ticks=1)
        # The sampler is PURE — we check that the metric is wired correctly by
        # triggering a DEGRADED via loop lag alone (no outbox lag).
        # Pass a very early tick_started_at to simulate a 1000ms delay.
        past = time.monotonic() - 1.0   # 1000ms ago
        eng._sample_backpressure(past, 0.0)   # delay = 1000ms >> threshold 50ms
        assert eng.health() == _core.RuntimeHealth.DEGRADED
        last = eng._rt.last_event()
        assert "runtime_event_loop_lag_ms" in last.trigger
        assert last.metrics_snapshot.runtime_event_loop_lag_ms > 50.0


class TestEngineGatherFailure:
    def test_gather_failure_leaves_health_unchanged(self, tmp_path):
        """If gatherer.gather() raises, health stays READY (no spurious transition).

        pybind11 C++ objects are read-only so we cannot monkeypatch their methods.
        Instead, inject a Python stub gatherer that raises on gather().
        """
        eng = _engine(tmp_path, outbox_lag_threshold=2, debounce_ticks=1)

        class _FailingGatherer:
            def gather(self, _adapter):
                raise RuntimeError("simulated DB error")

        # Replace the C++ gatherer with a Python stub that always fails.
        eng._gatherer = _FailingGatherer()
        _seed_lag(eng._db_path, 50)  # would be over-threshold, but gather fails first
        eng._sample_backpressure(time.monotonic(), 60.0)
        # Health unchanged (still READY after failed gather).
        assert eng.health() == _core.RuntimeHealth.READY


class TestEngineRuntimePassthrough:
    def test_note_health_passthrough_on_runtime(self, tmp_path):
        """Runtime.note_health passthrough wires correctly to the C++ supervisor."""
        cfg = DashboardConfig(db_path=str(tmp_path / "nh.db"), token="t")
        eng = DashboardEngine(cfg)
        dec = _core.HealthDecision()
        dec.target_status = _core.RuntimeHealth.DEGRADED
        dec.trigger = "test_passthrough"
        eng._rt.note_health(dec)
        assert eng.health() == _core.RuntimeHealth.DEGRADED
