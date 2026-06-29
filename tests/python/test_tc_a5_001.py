"""TC-A5-001 [CRITICAL]: 可塑窗口 close_deadline 到 → 强制 close + 仲裁.

spec §7: 窗口超时 (close_deadline <= now) → close_due_windows 强制关闭并仲裁。
验证一个开了的窗口在 deadline 过后被 close_due_windows 仲裁 (status→closed)。
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


def test_expired_window_closed_and_arbitrated(rt):
    _seed_consolidated(rt, "w1")
    eng = _core.ReconsolidationEngine(rt.adapter)
    eng.reconsolidate("w1", "belief.conflict", "h1", 1.0, "2026-05-27T10:00:00Z")
    closed = eng.close_due_windows("2026-05-27T11:00:00Z")
    assert closed >= 1, "超时窗口应被强制 close"
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        status = c.execute(
            "SELECT status FROM reconsolidation_windows WHERE stmt_id='w1'").fetchone()[0]
    assert status == "closed"


def test_unexpired_window_not_closed(rt):
    _seed_consolidated(rt, "w2")
    eng = _core.ReconsolidationEngine(rt.adapter)
    eng.reconsolidate("w2", "belief.conflict", "h1", 1.0, "2026-05-27T10:00:00Z")
    eng.close_due_windows("2026-05-27T10:05:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        status = c.execute(
            "SELECT status FROM reconsolidation_windows WHERE stmt_id='w2'").fetchone()[0]
    assert status == "open"
