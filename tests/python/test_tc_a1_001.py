"""TC-A1-001 [CRITICAL]: replay_count≥5 振荡防护强制 CONSOLIDATED+PENDING_REVIEW.

spec §6.2 振荡防护: stmt.replay_count >= MAX_CONSOLIDATION_ATTEMPTS=5 →
强制 consolidation_state=CONSOLIDATED + review_status=PENDING_REVIEW +
emit statement.consolidation_forced。防止 VOLATILE/REPLAYING 无限振荡。
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


def _seed(rt, stmt_id, replay_count, state="volatile"):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,replay_count,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", state, "approved", replay_count,
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def test_replay_count_5_forces_consolidated(rt):
    _seed(rt, "osc", replay_count=5, state="volatile")
    sched = _core.ReplayScheduler(rt.adapter)
    forced = sched.enforce_oscillation_guard()
    assert forced >= 1, "replay_count>=5 应被强制巩固"
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        row = c.execute(
            "SELECT consolidation_state, review_status FROM statements WHERE id='osc'"
        ).fetchone()
    assert row == ("consolidated", "pending_review"), \
        f"应强制 consolidated+pending_review, 实际 {row!r}"
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        n = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.consolidation_forced' "
            "AND primary_id='osc'").fetchone()[0]
    assert n == 1, "应 emit 1 条 statement.consolidation_forced"


def test_replay_count_under_5_not_forced(rt):
    _seed(rt, "ok", replay_count=4, state="volatile")
    _core.ReplayScheduler(rt.adapter).enforce_oscillation_guard()
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='ok'").fetchone()[0]
    assert state == "volatile", "replay_count<5 不应被强制"
