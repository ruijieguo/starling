"""非 CRITICAL roll-up: CommonGround Grounding Acts 状态机端到端 (经 binding).

C++ 单测 tests/cpp/test_common_ground_writer.cpp 已逐 act 覆盖 (conn 直传)。
本 Python roll-up 验证 5 个动作 + grounded 状态机 + 24h 超时降级经 conn-free
binding (CommonGroundWriter(adapter)) 走通, 且每个动作写 grounding_acts 审计行。

状态机 (spec §5.4 / 09_tom §3-5):
  assert      → asserted_unack
  acknowledge → grounded (+ grounded_at)
  repair      → suspected_diverge
  withdraw    → recanted
  supersede   → superseded_by 置位
  sweep(24h)  → asserted_unack 超 24h 降 suspected_diverge
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _status(rt, cg_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        return c.execute(
            "SELECT status FROM common_ground WHERE id=?", (cg_id,)).fetchone()[0]


def _act_count(rt, cg_id, act):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        return c.execute(
            "SELECT COUNT(*) FROM grounding_acts WHERE common_ground_id=? AND act=?",
            (cg_id, act)).fetchone()[0]


def test_assert_then_acknowledge_grounds(rt):
    w = _core.CommonGroundWriter(rt.adapter)
    cg = w.assert_("default", "stmt-1", ["alice", "bob"], "2026-05-30T10:00:00Z")
    assert _status(rt, cg) == "asserted_unack"
    assert _act_count(rt, cg, "assert") == 1
    w.acknowledge(cg, "alice", "2026-05-30T10:01:00Z")
    assert _status(rt, cg) == "grounded"
    assert _act_count(rt, cg, "acknowledge") == 1
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        grounded_at = c.execute(
            "SELECT grounded_at FROM common_ground WHERE id=?", (cg,)).fetchone()[0]
    assert grounded_at == "2026-05-30T10:01:00Z"


def test_repair_diverges(rt):
    w = _core.CommonGroundWriter(rt.adapter)
    cg = w.assert_("default", "stmt-2", [], "2026-05-30T10:00:00Z")
    w.repair(cg, "bob", "2026-05-30T10:02:00Z")
    assert _status(rt, cg) == "suspected_diverge"
    assert _act_count(rt, cg, "repair") == 1


def test_withdraw_recants(rt):
    w = _core.CommonGroundWriter(rt.adapter)
    cg = w.assert_("default", "stmt-3", [], "2026-05-30T10:00:00Z")
    w.withdraw(cg, "alice", "2026-05-30T10:03:00Z")
    assert _status(rt, cg) == "recanted"
    assert _act_count(rt, cg, "withdraw") == 1


def test_supersede_sets_superseded_by(rt):
    w = _core.CommonGroundWriter(rt.adapter)
    cg = w.assert_("default", "stmt-4", [], "2026-05-30T10:00:00Z")
    w.supersede_ground(cg, "stmt-new", "2026-05-30T10:04:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        sup = c.execute(
            "SELECT superseded_by FROM common_ground WHERE id=?", (cg,)).fetchone()[0]
    assert sup == "stmt-new"
    assert _act_count(rt, cg, "supersede") == 1


def test_sweep_timeout_downgrades_only_stale(rt):
    w = _core.CommonGroundWriter(rt.adapter)
    old = w.assert_("default", "stmt-old", [], "2026-05-29T11:00:00Z")   # 25h ago
    fresh = w.assert_("default", "stmt-fresh", [], "2026-05-30T11:00:00Z")  # 1h ago
    n = w.sweep_timeout_downgrade("2026-05-30T12:00:00Z")
    assert n == 1
    assert _status(rt, old) == "suspected_diverge"
    assert _status(rt, fresh) == "asserted_unack"
