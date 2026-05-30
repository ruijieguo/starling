"""TC-A6-002 [CRITICAL]: T8 outbox 串行 — 同 stmt 多 decay 不并发迁移.

spec §6.5: 同一 stmt_id 的 decay 事件不并发执行, 避免多次 state 迁移覆盖。
验证批量 decay 候选含重复 stmt_id 时, 只迁移一次。
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


def test_duplicate_decay_candidates_archive_once(rt):
    _seed_consolidated_old(rt, "dup")
    sched = _core.ReplayScheduler(rt.adapter)
    sched.run_decay(["dup", "dup"], "2026-05-27T00:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        n_arch = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' "
            "AND primary_id='dup'").fetchone()[0]
    assert n_arch == 1, "重复候选只应迁移 + emit 一次"
