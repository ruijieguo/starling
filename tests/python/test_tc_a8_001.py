"""TC-A8-001 [CRITICAL]: local-store severe path 异步仲裁版.

spec §7.3 + §16.3-7/-9: Reconsolidation severe contradict 4 项原子提交
(新版 reconsolidation_derived + SUPERSEDES 边 + 旧版 ARCHIVED + 3 outbox 事件)。
与 P1 同步路径 TC-NEW-CONFLICT-SEVERE 互补共存 — 后者是 ConflictProbe 同事务
direct_contradiction, 本测试是 Reconsolidation 异步仲裁。

构造: 一个 CONSOLIDATED stmt 开窗口, 灌入高权重反对证据 (strength>0.7 → severe),
窗口 close → 验证 4 项原子提交。
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


def test_async_severe_four_item_atomic(rt):
    _seed_consolidated(rt, "old")
    eng = _core.ReconsolidationEngine(rt.adapter)
    # 显式开窗 + 多条高权重反对证据 → severe
    for i in range(5):
        eng.reconsolidate("old", "belief.conflict", f"h{i}", 1.0, "2026-05-27T10:00:00Z")
    eng.close_due_windows("2026-05-27T11:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        # 旧版 ARCHIVED
        old_state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='old'").fetchone()[0]
        # 新版 reconsolidation_derived CONSOLIDATED
        new = c.execute(
            "SELECT id FROM statements WHERE provenance='reconsolidation_derived' "
            "AND consolidation_state='consolidated'").fetchone()
        # SUPERSEDES 边
        edge = c.execute(
            "SELECT COUNT(*) FROM statement_edges WHERE dst_id='old' AND edge_kind='supersedes'"
        ).fetchone()[0]
        # 3 outbox 事件
        corrected = c.execute("SELECT COUNT(*) FROM bus_events WHERE event_type='statement.corrected'").fetchone()[0]
        archived = c.execute("SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' AND primary_id='old'").fetchone()[0]
        superseded = c.execute("SELECT COUNT(*) FROM bus_events WHERE event_type='statement.superseded'").fetchone()[0]
        # 新版不 emit statement.written
        new_written = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.written' "
            "AND primary_id=?", (new[0],)).fetchone()[0] if new else -1
    assert old_state == "archived", "旧版应 ARCHIVED"
    assert new is not None, "应有新版 reconsolidation_derived CONSOLIDATED"
    assert edge == 1, "应有 1 条 SUPERSEDES 边"
    assert corrected == 1 and archived == 1 and superseded == 1, "应 emit 3 outbox 事件"
    assert new_written == 0, "新版不应 emit statement.written (防重入 Replay)"
