"""lifecycle query — Phase 3 片 4 生命周期:占用快照(精确)+ 事件派生流转(累计)。

裸插 statements(各 consolidation_state)+ bus_events(typed statement.* 事件),断言
occupancy 按状态精确分组、events 只数 statement.* 且按类型计数,且 tenant-scoped、空库降级。"""
import sqlite3
from pathlib import Path

from starling.dashboard import queries

_STMT_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, "
    "canonical_object_hash_version, modality, polarity, confidence, observed_at, "
    "salience, affect_json, activation, last_accessed, provenance, created_at, "
    "updated_at, consolidation_state"
)


def _stmt(conn, sid, tenant, state):
    conn.execute(
        f"INSERT INTO statements ({_STMT_COLS}) VALUES ({','.join('?' * 23)})",
        (sid, tenant, "self", "first_person", "cognizer", "Bob", "rel",
         "str", "v", f"h{sid}", "v1", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-10T10:00:00Z", "user_input", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", state),
    )


def _event(conn, eid, tenant, etype, seq):
    conn.execute(
        "INSERT INTO bus_events (event_id, tenant_id, event_type, primary_id, "
        "aggregate_id, outbox_sequence, idempotency_key, payload_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, tenant, etype, "s", "s", seq, eid, "{}", "2026-04-10T10:00:00Z"),
    )


def _seed(db_path: str):
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r
    conn = sqlite3.connect(db_path)
    for sid, state in [("a", "volatile"), ("b", "volatile"), ("c", "consolidated"),
                       ("d", "archived"), ("e", "forgotten")]:
        _stmt(conn, sid, "default", state)
    _stmt(conn, "x", "other", "volatile")          # other tenant — excluded
    evs = [("statement.written",), ("statement.written",), ("statement.written",),
           ("statement.consolidated",), ("statement.archived",),
           ("statement.derived",), ("statement.superseded",),
           ("belief.conflict",)]                    # non-statement.* — excluded by LIKE
    for i, (etype,) in enumerate(evs):
        _event(conn, f"e{i}", "default", etype, i + 1)
    _event(conn, "ex", "other", "statement.written", 100)   # other tenant — excluded
    conn.commit()
    conn.close()


def test_lifecycle_occupancy_snapshot(tmp_path):
    db = str(tmp_path / "lc.db")
    _seed(db)
    occ = queries.lifecycle(db, "default")["occupancy"]
    # 精确快照、tenant-scoped(other 的 x 不计)。
    assert occ == {"volatile": 2, "consolidated": 1, "archived": 1, "forgotten": 1}


def test_lifecycle_event_derived_transitions(tmp_path):
    db = str(tmp_path / "lc.db")
    _seed(db)
    ev = queries.lifecycle(db, "default")["events"]
    assert ev["statement.written"] == 3
    assert ev["statement.consolidated"] == 1
    assert ev["statement.archived"] == 1
    assert ev["statement.derived"] == 1 and ev["statement.superseded"] == 1
    assert "belief.conflict" not in ev          # 只数 statement.*
    assert sum(ev.values()) == 7                # other-tenant statement.written 未计入


def test_lifecycle_tenant_scoped_other(tmp_path):
    db = str(tmp_path / "lc.db")
    _seed(db)
    out = queries.lifecycle(db, "other")
    assert out["occupancy"] == {"volatile": 1}
    assert out["events"] == {"statement.written": 1}


def test_lifecycle_empty_degrades(tmp_path):
    db = str(tmp_path / "empty.db")
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(Path(db))
    r.start()
    del r
    out = queries.lifecycle(db, "default")
    assert out == {"occupancy": {}, "events": {}}
