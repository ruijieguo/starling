"""TC-PROJECTION-REPAIR [CRITICAL]: rebuild 抽取 < ground truth → 不替换.

spec §16.3-3/-6: Projection repair safety/guard。构造 rebuild 抽取条数低于
主表 ground truth 的场景, 验证系统 emit projection.rebuild_failed(
truncation_suspected) 且 active projection 不被替换。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime


@pytest.fixture
def rt(tmp_path):
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_statement(rt, stmt_id):
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


def test_truncation_suspected_keeps_active(rt):
    # seed 3 statements + 先正常物化一次 proj_holder_state_time
    for i in range(3):
        _seed_statement(rt, f"s{i}")
    pm = _core.ProjectionMaintainer(rt.adapter)
    pm.rebuild_projection("proj_holder_state_time", "2026-05-27T10:00:00Z")  # active=3
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        before = c.execute("SELECT COUNT(*) FROM proj_holder_state_time").fetchone()[0]
    assert before == 3

    # 注入 truncation: 用测试钩子让下一次 rebuild 只抽 2 条 (< ground truth 3)
    report = pm.rebuild_projection_with_injected_count(
        "proj_holder_state_time", injected_rebuilt=2, now_iso="2026-05-27T11:00:00Z")
    assert report.truncation_suspected is True

    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        # active projection 仍是 3 (未被截断的 2 替换)
        after = c.execute("SELECT COUNT(*) FROM proj_holder_state_time").fetchone()[0]
        status = c.execute(
            "SELECT status FROM projection_rebuild_state WHERE projection_name='proj_holder_state_time'"
        ).fetchone()[0]
        ev = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='projection.rebuild_failed'"
        ).fetchone()[0]
    assert after == 3, "truncation_suspected 时 active projection 不被替换"
    assert status == "truncation_suspected"
    assert ev == 1, "应 emit projection.rebuild_failed"
