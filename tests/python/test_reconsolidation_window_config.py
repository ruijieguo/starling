"""非 CRITICAL roll-up: §16.3-4 再巩固窗口配置 (per-modality 超时) 端到端.

C++ 单测 tests/cpp/test_plastic_window.cpp 已覆盖 adaptive_timeout_minutes 的
modality 排序 / 高频 ≥3/hr→5min / clamp [5,360]。本 Python roll-up 验证 modality
→ close_deadline 的端到端接线 (statements.modality → reconsolidate() → 窗口
close_deadline) 经 binding 走通: COMMITS (长 360min) 的 deadline 远晚于
ASSUMES (短 5min)。
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


def _seed(rt, stmt_id, modality):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", modality, "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def _deadline(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        return c.execute(
            "SELECT close_deadline FROM reconsolidation_windows WHERE stmt_id=?",
            (stmt_id,)).fetchone()[0]


def test_per_modality_deadline_wired_through_binding(rt):
    _seed(rt, "commits_stmt", "commits")
    _seed(rt, "assumes_stmt", "assumes")
    eng = _core.ReconsolidationEngine(rt.adapter)
    now = "2026-05-27T10:00:00Z"
    eng.reconsolidate("commits_stmt", "belief.conflict", "h1", 0.3, now)
    eng.reconsolidate("assumes_stmt", "belief.conflict", "h2", 0.3, now)
    # COMMITS → now+360min = 16:00; ASSUMES → now+5min = 10:05
    assert _deadline(rt, "commits_stmt") == "2026-05-27T16:00:00Z"
    assert _deadline(rt, "assumes_stmt") == "2026-05-27T10:05:00Z"
    # 长 modality 的 deadline 严格晚于短 modality
    assert _deadline(rt, "commits_stmt") > _deadline(rt, "assumes_stmt")
