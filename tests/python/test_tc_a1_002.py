"""TC-A1-002 [CRITICAL]: VOLATILE >7天 不在 Affect Buffer → ARCHIVED.

spec §6.2 VOLATILE TTL 兜底: consolidation_state=VOLATILE 且写入距今 >
T_max_volatile=7天 且 not in Affect Buffer → 自动 ARCHIVED(volatile_ttl_exceeded)。
不依赖 Replay 调度, 由 TTL sweep 兜底。
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


def _seed(rt, stmt_id, created_at):
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
             created_at, 0.5, "{}", 0.0, created_at,
             "user_input", "volatile", "approved", created_at, created_at))
        c.commit()


def test_volatile_older_than_7d_archived(rt):
    _seed(rt, "old", created_at="2026-05-01T00:00:00Z")
    n = _core.ReplayScheduler(rt.adapter).sweep_volatile_ttl("2026-05-27T00:00:00Z")
    assert n >= 1
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='old'").fetchone()[0]
        ev = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' "
            "AND primary_id='old'").fetchone()[0]
    assert state == "archived"
    assert ev == 1


def test_volatile_within_7d_kept(rt):
    _seed(rt, "fresh", created_at="2026-05-25T00:00:00Z")
    _core.ReplayScheduler(rt.adapter).sweep_volatile_ttl("2026-05-27T00:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='fresh'").fetchone()[0]
    assert state == "volatile"
