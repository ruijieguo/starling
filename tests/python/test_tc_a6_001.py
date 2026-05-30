"""TC-A6-001 [CRITICAL]: decay_candidate per-stmt 串行投递 T5 race 消除.

spec §6.5 decay: emit statement.decay_candidate, Bus dispatcher per-stmt
顺序串行投递; 后到事件读到 state 已变 → 跳过。验证同一 stmt 的 decay
不会重复迁移 (CONSOLIDATED→ARCHIVED 仅一次)。
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


def _seed_consolidated_old(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "assumes", "pos", 0.9,
             "2025-01-01T00:00:00Z", 0.0, "{}", 0.0, "2025-01-01T00:00:00Z",
             "user_input", "consolidated", "approved",
             "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"))
        c.commit()


def test_decay_serial_idempotent(rt):
    _seed_consolidated_old(rt, "d1")
    sched = _core.ReplayScheduler(rt.adapter)
    sched.run_decay(["d1"], "2026-05-27T00:00:00Z")
    sched.run_decay(["d1"], "2026-05-27T00:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='d1'").fetchone()[0]
        n_arch = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' "
            "AND primary_id='d1'").fetchone()[0]
    assert state == "archived"
    assert n_arch == 1, "串行守护: archived 事件只应 emit 一次"
