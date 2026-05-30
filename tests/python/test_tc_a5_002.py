"""TC-A5-002 [CRITICAL]: 仲裁自身失败 → 窗口仍 close, stmt 回 CONSOLIDATED 不卡死.

spec §7.2: fallback 任务自身失败的双层兜底。即使 aggregate/arbitrate 抛异常,
close_due_windows 必须把窗口标 closed 且把 stmt 状态恢复到 CONSOLIDATED
(不能永久卡在 replaying_reconsolidating)。

构造方式: 开窗后把 stmt 删除 (制造仲裁时的异常源), 验证 close_due_windows
不抛出且窗口最终 closed。
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


def _seed_consolidated(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def test_arbitration_failure_does_not_hang_window(rt):
    _seed_consolidated(rt, "fail")
    eng = _core.ReconsolidationEngine(rt.adapter)
    eng.reconsolidate("fail", "belief.conflict", "h1", 1.0, "2026-05-27T10:00:00Z")
    # 删除目标 stmt 制造仲裁异常源
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute("DELETE FROM statements WHERE id='fail'")
        c.commit()
    # close_due_windows 不应抛出 (双层兜底)
    eng.close_due_windows("2026-05-27T11:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        status = c.execute(
            "SELECT status FROM reconsolidation_windows WHERE stmt_id='fail'").fetchone()[0]
    assert status == "closed", "仲裁失败时窗口仍须 close, 不卡死"
