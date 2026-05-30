"""M0.8 pybind binding smoke tests.

Verifies that every M0.8 class is importable from _core, constructable from a
SqliteAdapter, and that its connection-free Python methods are callable without
error on a freshly opened in-memory database.
"""

import pytest
from starling import _core

NOW = "2026-05-27T10:00:00Z"


@pytest.fixture
def adapter():
    return _core.SqliteAdapter.open(":memory:")


# ── ReplayScheduler ───────────────────────────────────────────────────────────

class TestReplayScheduler:
    def test_class_exists(self):
        assert hasattr(_core, "ReplayScheduler")

    def test_construct(self, adapter):
        rs = _core.ReplayScheduler(adapter)
        assert rs is not None

    def test_enforce_oscillation_guard(self, adapter):
        rs = _core.ReplayScheduler(adapter)
        result = rs.enforce_oscillation_guard()
        assert isinstance(result, int)

    def test_sweep_volatile_ttl(self, adapter):
        rs = _core.ReplayScheduler(adapter)
        result = rs.sweep_volatile_ttl(NOW)
        assert isinstance(result, int)

    def test_run_decay_empty(self, adapter):
        rs = _core.ReplayScheduler(adapter)
        result = rs.run_decay([], NOW)
        assert isinstance(result, int)

    def test_tick_online_returns_stats(self, adapter):
        rs = _core.ReplayScheduler(adapter)
        stats = rs.tick_online(NOW)
        assert hasattr(stats, "sampled")

    def test_run_idle(self, adapter):
        rs = _core.ReplayScheduler(adapter)
        stats = rs.run_idle(NOW)
        assert hasattr(stats, "sampled")

    def test_run_sleep(self, adapter):
        rs = _core.ReplayScheduler(adapter)
        stats = rs.run_sleep(NOW)
        assert hasattr(stats, "sampled")


# ── ReconsolidationEngine ─────────────────────────────────────────────────────

class TestReconsolidationEngine:
    def test_class_exists(self):
        assert hasattr(_core, "ReconsolidationEngine")

    def test_construct(self, adapter):
        re = _core.ReconsolidationEngine(adapter)
        assert re is not None

    def test_close_due_windows(self, adapter):
        re = _core.ReconsolidationEngine(adapter)
        result = re.close_due_windows(NOW)
        assert isinstance(result, int)

    def test_tick_one_batch(self, adapter):
        re = _core.ReconsolidationEngine(adapter)
        stats = re.tick_one_batch(NOW)
        assert hasattr(stats, "events_processed")

    def test_reconsolidate_no_op(self, adapter):
        re = _core.ReconsolidationEngine(adapter)
        # no-op: stmt_id doesn't exist — must not raise
        re.reconsolidate("nonexistent-stmt", "test.event", "abc123", 1.0, NOW)


# ── ProjectionMaintainer ──────────────────────────────────────────────────────

class TestProjectionMaintainer:
    def test_class_exists(self):
        assert hasattr(_core, "ProjectionMaintainer")

    def test_construct(self, adapter):
        pm = _core.ProjectionMaintainer(adapter)
        assert pm is not None

    def test_tick_one_batch(self, adapter):
        pm = _core.ProjectionMaintainer(adapter)
        stats = pm.tick_one_batch(NOW)
        assert hasattr(stats, "events_processed")

    def test_rebuild_projection_returns_report(self, adapter):
        pm = _core.ProjectionMaintainer(adapter)
        report = pm.rebuild_projection("proj_holder_state_time", NOW)
        assert hasattr(report, "truncation_suspected")
        assert isinstance(report.truncation_suspected, bool)

    def test_rebuild_report_class_exists(self):
        assert hasattr(_core, "RebuildReport")

    def test_rebuild_projection_with_injected_count(self, adapter):
        pm = _core.ProjectionMaintainer(adapter)
        report = pm.rebuild_projection_with_injected_count(
            "proj_holder_state_time", 0, NOW
        )
        assert hasattr(report, "truncation_suspected")


# ── CommonGroundWriter ────────────────────────────────────────────────────────

class TestCommonGroundWriter:
    def test_class_exists(self):
        assert hasattr(_core, "CommonGroundWriter")

    def test_construct(self, adapter):
        cgw = _core.CommonGroundWriter(adapter)
        assert cgw is not None

    def test_sweep_timeout_downgrade(self, adapter):
        cgw = _core.CommonGroundWriter(adapter)
        result = cgw.sweep_timeout_downgrade(NOW)
        assert isinstance(result, int)

    def test_assert_and_acknowledge(self, adapter):
        cgw = _core.CommonGroundWriter(adapter)
        cg_id = cgw.assert_(
            "default", "stmt-001", ["alice", "bob"], NOW
        )
        assert isinstance(cg_id, str)
        cgw.acknowledge(cg_id, "alice", NOW)

    def test_assert_and_repair(self, adapter):
        cgw = _core.CommonGroundWriter(adapter)
        cg_id = cgw.assert_("default", "stmt-002", ["alice"], NOW)
        cgw.repair(cg_id, "alice", NOW)

    def test_assert_and_withdraw(self, adapter):
        cgw = _core.CommonGroundWriter(adapter)
        cg_id = cgw.assert_("default", "stmt-003", ["alice"], NOW)
        cgw.withdraw(cg_id, "alice", NOW)


# ── PersonaContainer + AnchorStatement ───────────────────────────────────────

class TestPersonaContainer:
    def test_class_exists(self):
        assert hasattr(_core, "PersonaContainer")

    def test_anchor_statement_class_exists(self):
        assert hasattr(_core, "AnchorStatement")

    def test_construct(self, adapter):
        pc = _core.PersonaContainer(adapter)
        assert pc is not None

    def test_rebuild_empty_sources(self, adapter):
        pc = _core.PersonaContainer(adapter)
        pc.rebuild("default", "holder-001", [])

    def test_rebuild_with_anchors(self, adapter):
        pc = _core.PersonaContainer(adapter)
        a = _core.AnchorStatement(
            stmt_id="s1",
            anchor_type="self_model_anchor",
            dimension="traits",
            value="curious",
            confidence=0.9,
        )
        pc.rebuild("default", "holder-001", [a])

    def test_concurrent_rebuild_error_exists(self):
        assert hasattr(_core, "ConcurrentRebuildError")


# ── CommonGroundContainer ─────────────────────────────────────────────────────

class TestCommonGroundContainer:
    def test_class_exists(self):
        assert hasattr(_core, "CommonGroundContainer")

    def test_construct(self, adapter):
        cgc = _core.CommonGroundContainer(adapter)
        assert cgc is not None

    def test_rebuild_no_op(self, adapter):
        cgc = _core.CommonGroundContainer(adapter)
        cgc.rebuild("default", "cg-ref-001")


# ── Python subpackage re-exports ──────────────────────────────────────────────

class TestSubpackageImports:
    def test_replay_subpackage(self):
        from starling.replay import ReplayScheduler, ReplayStats
        assert ReplayScheduler is _core.ReplayScheduler
        assert ReplayStats is _core.ReplayStats

    def test_reconsolidation_subpackage(self):
        from starling.reconsolidation import ReconsolidationEngine, EngineStats
        assert ReconsolidationEngine is _core.ReconsolidationEngine
        assert EngineStats is _core.EngineStats

    def test_neocortex_subpackage(self):
        from starling.neocortex import (
            PersonaContainer, CommonGroundContainer,
            AnchorStatement, ConcurrentRebuildError,
        )
        assert PersonaContainer is _core.PersonaContainer

    def test_projection_subpackage(self):
        from starling.projection import ProjectionMaintainer, RebuildReport, MaintainerStats
        assert ProjectionMaintainer is _core.ProjectionMaintainer
        assert RebuildReport is _core.RebuildReport
