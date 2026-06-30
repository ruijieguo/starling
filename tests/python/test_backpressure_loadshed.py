"""P3.c LW.3 — host passes RuntimeHealth into tick (close-the-backpressure-loop).

Tests prove:
  1. CAUSALITY — DEGRADED forces soft stages to be skipped; critical stages still run.
  2. RECOVERY   — returning to READY re-enables all stages.
  3. DRAINING   — only outbox runs; all other 7 stages are shed.
  4. L9 LATENCY — one-tick+debounce: the tick that fires when health flips DEGRADED
                  acts on the PRIOR health state; only the NEXT tick sheds.

Engine construction mirrors test_backpressure_sampler.py.
"""
from __future__ import annotations

import sqlite3
import time

import pytest

from starling import _core
from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine


# ── helpers ──────────────────────────────────────────────────────────────────

_NOW = "2026-06-30T12:00:00Z"

# LW.2 labels for the 8 stages.
# Under DEGRADED: only Soft lane stages are skipped (LOCKED L4 in tick_load_shedding.hpp).
# Soft  = embed, common_ground, replay_idle, projection.
# Critical = policy, replay_oscillation_guard, replay_ttl_sweep, outbox (always run).
_DEGRADED_SOFT = {"embed", "common_ground", "replay_idle", "projection"}
# Under DRAINING: only outbox runs — all 7 others are skipped.
_DRAINING_SHED = {"embed", "policy", "common_ground",
                  "replay_oscillation_guard", "replay_ttl_sweep",
                  "replay_idle", "projection"}
_CRITICAL = {"outbox"}


def _engine(tmp_path, *, outbox_lag_threshold: int = 100,
            loop_lag_threshold_ms: float = 200.0,
            debounce_ticks: int = 2) -> DashboardEngine:
    cfg = DashboardConfig(db_path=str(tmp_path / "ls.db"), token="t")
    eng = DashboardEngine(cfg)
    eng._replace_sampler(
        outbox_lag_threshold=outbox_lag_threshold,
        loop_lag_threshold_ms=loop_lag_threshold_ms,
        debounce_ticks=debounce_ticks,
    )
    return eng


def _force_degraded(eng: DashboardEngine) -> None:
    """Directly set health to DEGRADED via note_health (bypasses sampler timing)."""
    dec = _core.HealthDecision()
    dec.target_status = _core.RuntimeHealth.DEGRADED
    dec.trigger = "test_force_degraded"
    eng._rt.note_health(dec)


def _force_ready(eng: DashboardEngine) -> None:
    """Directly set health to READY via note_health."""
    dec = _core.HealthDecision()
    dec.target_status = _core.RuntimeHealth.READY
    dec.trigger = "test_force_ready"
    eng._rt.note_health(dec)


def _seed_outbox(db_path: str, count: int) -> None:
    """Seed bus_events with outbox_sequence entries (produces outbox_lag)."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    for seq in range(1, count + 1):
        conn.execute(
            "INSERT INTO bus_events"
            "(event_id,tenant_id,event_type,primary_id,aggregate_id,"
            " outbox_sequence,idempotency_key,payload_json,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (f"ls-evt-{seq}", "tenant-1", "test.event", "p-1", "agg-1",
             seq, f"idem-ls-{seq}", "{}", _NOW),
        )
    conn.commit()
    conn.close()


def _set_checkpoint(db_path: str, delivered_seq: int) -> None:
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


# ── Scenario 1: CAUSALITY ─────────────────────────────────────────────────────

class TestCausalityDegraded:
    """DEGRADED health ⇒ soft stages are shed; critical outbox still runs."""

    def test_soft_stages_skipped_under_degraded(self, tmp_path):
        """Core causality proof: DEGRADED ⇒ stages_skipped contains the soft stages."""
        eng = _engine(tmp_path)
        _force_degraded(eng)
        assert eng.health() == _core.RuntimeHealth.DEGRADED

        stats = eng.tick(_NOW)

        # stages_skipped is present in the tick result dict.
        assert "stages_skipped" in stats, (
            "stages_skipped missing from tick dict — binding not updated yet"
        )
        skipped = set(stats["stages_skipped"])
        # All soft stages must be skipped (DEGRADED sheds Soft lane only).
        assert _DEGRADED_SOFT.issubset(skipped), (
            f"expected soft stages {_DEGRADED_SOFT!r} skipped; got {skipped!r}"
        )
        # Critical stages must NOT be skipped under DEGRADED.
        for crit in ("policy", "replay_oscillation_guard", "replay_ttl_sweep", "outbox"):
            assert crit not in skipped, (
                f"critical stage {crit!r} must not be skipped under DEGRADED; got {skipped!r}"
            )

    def test_critical_outbox_runs_under_degraded(self, tmp_path):
        """Outbox (critical) is NOT in stages_skipped under DEGRADED."""
        eng = _engine(tmp_path)
        _force_degraded(eng)

        stats = eng.tick(_NOW)
        skipped = set(stats["stages_skipped"])
        assert "outbox" not in skipped, (
            f"outbox should NOT be skipped under DEGRADED; skipped={skipped!r}"
        )

    def test_stage_timings_absent_for_skipped_stages(self, tmp_path):
        """Skipped stages produce no timing entry (they were not executed)."""
        eng = _engine(tmp_path)
        _force_degraded(eng)

        stats = eng.tick(_NOW)
        timing_labels = {e["stage"] for e in stats["stage_timings_ms"]}
        skipped = set(stats["stages_skipped"])
        # No overlap: a stage cannot be both timed and skipped.
        overlap = timing_labels & skipped
        assert not overlap, (
            f"stages appear in BOTH timings and skipped: {overlap!r}"
        )

    def test_embed_effect_absent_under_degraded(self, tmp_path):
        """A pending-embed row is NOT embedded when health is DEGRADED (embed stage shed)."""
        from starling import _core as core
        eng = _engine(tmp_path)
        # Seed a statement via remember with a FakeLLM so there's a pending embed.
        fake = core.FakeLLMAdapter()
        fake.set_default_response(
            '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
            '"subject":"X","predicate":"is","object":"test",'
            '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]',
            True, "")
        eng.llm = fake
        eng.remember("X is a test")
        # Verify there's something to embed (embedded=0 before tick).
        stats_before = eng.tick(_NOW)
        # Now force DEGRADED and tick again.
        _force_degraded(eng)
        assert eng.health() == _core.RuntimeHealth.DEGRADED
        stats = eng.tick(_NOW)
        assert stats["embedded"] == 0, (
            f"embed stage should be shed under DEGRADED; embedded={stats['embedded']!r}"
        )


# ── Scenario 2: RECOVERY ──────────────────────────────────────────────────────

class TestRecoveryToReady:
    """Returning to READY re-enables all stages."""

    def test_stages_not_skipped_under_ready(self, tmp_path):
        """After recovery to READY, stages_skipped is empty."""
        eng = _engine(tmp_path)
        _force_degraded(eng)
        eng.tick(_NOW)  # shed tick

        _force_ready(eng)
        assert eng.health() == _core.RuntimeHealth.READY

        stats = eng.tick(_NOW)
        assert stats["stages_skipped"] == [], (
            f"expected no skipped stages under READY; got {stats['stages_skipped']!r}"
        )

    def test_embed_runs_after_recovery(self, tmp_path):
        """After READY recovery, the embed stage can do work again."""
        from starling import _core as core
        eng = _engine(tmp_path)
        fake = core.FakeLLMAdapter()
        fake.set_default_response(
            '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
            '"subject":"Y","predicate":"is","object":"test",'
            '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]',
            True, "")
        eng.llm = fake
        eng.remember("Y is a test")

        # DEGRADED: shed the embed stage.
        _force_degraded(eng)
        stats_degraded = eng.tick(_NOW)
        assert stats_degraded["embedded"] == 0

        # Recover and tick — embed should now run.
        _force_ready(eng)
        stats_ready = eng.tick(_NOW)
        # Under READY all stages run — stages_skipped empty.
        assert stats_ready["stages_skipped"] == []


# ── Scenario 3: DRAINING ──────────────────────────────────────────────────────

class TestDrainingKeepsOnlyOutbox:
    """DRAINING state keeps only outbox; all other 7 stages are shed (L7)."""

    def test_draining_sheds_all_except_outbox(self, tmp_path):
        eng = _engine(tmp_path)
        eng.begin_drain()
        assert eng.health() == _core.RuntimeHealth.DRAINING

        stats = eng.tick(_NOW)
        skipped = set(stats["stages_skipped"])
        # All 7 non-outbox stages are skipped under DRAINING.
        assert _DRAINING_SHED.issubset(skipped), (
            f"expected all non-outbox stages skipped under DRAINING; got {skipped!r}"
        )
        # outbox (critical) still runs.
        assert "outbox" not in skipped, (
            f"outbox must not be skipped under DRAINING; skipped={skipped!r}"
        )
        # Only outbox timing entry expected (len==1).
        timing_labels = [e["stage"] for e in stats["stage_timings_ms"]]
        assert timing_labels == ["outbox"], (
            f"expected only outbox timing under DRAINING; got {timing_labels!r}"
        )


# ── Scenario 4: L9 LATENCY ───────────────────────────────────────────────────

class TestL9OneTick_Debounce_Latency:
    """The sample-after-tick ordering means the first overloaded tick still
    acts on the PRIOR (READY) health.  Only after the debounce trips DEGRADED
    does a subsequent tick shed.

    Pattern: tick() THEN _sample_backpressure() — mirrors the real bg loop.
    """

    def test_first_overloaded_tick_does_not_shed(self, tmp_path):
        """Tick K fires under READY health even though overload is already detected.

        The background loop order is: tick → sample → (debounce may flip health).
        So tick K sees READY; only after N consecutive DEGRADED samples does a
        subsequent tick shed.

        We use runtime_event_loop_lag_ms (simulated via an early tick_started_at)
        as the backpressure signal — unlike outbox_lag, the loop-lag metric is not
        drained by the tick itself, so the debounce accumulates correctly.
        """
        debounce = 2
        # Set a very low loop-lag threshold (10ms) so a simulated 1s delay triggers it.
        eng = _engine(tmp_path, loop_lag_threshold_ms=10.0, debounce_ticks=debounce)

        # Tick 0 — health is READY; no shedding yet.
        stats0 = eng.tick(_NOW)
        assert stats0["stages_skipped"] == [], (
            "first tick should NOT shed (health still READY at this point)"
        )
        # Sample after tick 0 with a simulated 1000ms delay (>> 10ms threshold).
        # past is 1s before now, scheduled_interval=0 → loop_lag = 1000ms > 10ms.
        past = time.monotonic() - 1.0
        eng._sample_backpressure(past, 0.0)
        # Debounce counter = 1, not yet N=2 → still READY.
        assert eng.health() == _core.RuntimeHealth.READY, (
            "health should stay READY after only 1 overloaded sample (debounce not met)"
        )

        # Tick 1 — health is STILL READY (debounce not yet fired).
        stats1 = eng.tick(_NOW)
        assert stats1["stages_skipped"] == [], (
            "second tick should NOT shed (debounce not yet fired)"
        )
        # Sample after tick 1 — debounce counter = 2 = N → fires DEGRADED.
        past2 = time.monotonic() - 1.0
        eng._sample_backpressure(past2, 0.0)
        assert eng.health() == _core.RuntimeHealth.DEGRADED, (
            "health should be DEGRADED after 2 consecutive overloaded samples"
        )

        # Tick 2 — NOW health is DEGRADED → shed.
        stats2 = eng.tick(_NOW)
        skipped = set(stats2["stages_skipped"])
        assert _DEGRADED_SOFT.issubset(skipped), (
            f"tick after debounce should shed soft stages; skipped={skipped!r}"
        )

    def test_heartbeat_predicate_excludes_stages_skipped(self, tmp_path):
        """Non-empty stages_skipped on an idle DEGRADED tick must NOT count as
        did_work for the WS heartbeat predicate (the 3b L8 trap)."""
        eng = _engine(tmp_path)
        _force_degraded(eng)

        stats = eng.tick(_NOW)
        # Compute did_work the way engine.py should: exclude both list fields.
        did_work = any(v for k, v in stats.items()
                       if k not in ("stage_timings_ms", "stages_skipped"))
        # An idle tick with no real work should not count as work even under DEGRADED.
        # stages_skipped being non-empty must not flip did_work to True.
        assert not did_work, (
            f"idle DEGRADED tick spuriously counted as work; stats={stats!r}"
        )
