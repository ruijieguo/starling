"""/api/cascade_preview — 片 6 inform-only 级联预览(只读下溯 derived_from 后代)。

反向 provenance:给一条语句,列出「派生自它」的后代(遗忘它会波及谁)。bare-SQL 造
derived_from 图,断言直接/传递后代、环不爆栈、租户隔离、深度截断、缺失→None。纯只读,
不改记忆;实际遗忘仍是 /api/forget 单条逻辑删除(后代不被自动级联删除)。
"""
import sqlite3
from pathlib import Path

from starling.dashboard import queries

# NOT-NULL-no-default 列全给值(同 test_dashboard_provenance 的插法)。
_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, modality, "
    "polarity, confidence, observed_at, salience, affect_json, activation, "
    "last_accessed, provenance, created_at, updated_at, "
    "evidence_json, derived_from_json, supersedes_id, consolidation_state"
)


def _fresh_db(db_path: str):
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r  # release the writer handle before raw seeding
    return sqlite3.connect(db_path)


def _ins(conn, sid, *, tenant="default", derived="[]", state="consolidated"):
    conn.execute(
        f"INSERT INTO statements ({_COLS}) VALUES ({','.join('?' * 25)})",
        (sid, tenant, "self", "first_person", "cognizer", "X", "rel",
         "str", "v", f"h{sid}", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-10T10:00:00Z", "replay_derived",
         "2026-04-10T10:00:00Z", "2026-04-10T10:00:00Z", "[]", derived, None, state),
    )


def test_direct_and_transitive_descendants(tmp_path):
    db = str(tmp_path / "c.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    _ins(conn, "B", derived='["A"]')   # B derived from A (depth 1)
    _ins(conn, "C", derived='["A"]')   # C derived from A (depth 1)
    _ins(conn, "D", derived='["B"]')   # D derived from B (depth 2, transitive)
    _ins(conn, "Z")                    # unrelated
    conn.commit()
    conn.close()
    out = queries.cascade_preview(db, "default", "A")
    assert {a["id"] for a in out["affected"]} == {"B", "C", "D"}
    assert out["affected_count"] == 3
    assert {a["id"]: a["depth"] for a in out["affected"]}["D"] == 2
    assert out["truncated"] is False


def test_cycle_does_not_loop(tmp_path):
    db = str(tmp_path / "cyc.db")
    conn = _fresh_db(db)
    _ins(conn, "A", derived='["B"]')   # A ← B
    _ins(conn, "B", derived='["A"]')   # B ← A (cycle)
    conn.commit()
    conn.close()
    out = queries.cascade_preview(db, "default", "A")
    assert {a["id"] for a in out["affected"]} == {"B"}  # B once, no infinite loop


def test_tenant_isolation(tmp_path):
    db = str(tmp_path / "t.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    _ins(conn, "B", tenant="other", derived='["A"]')  # other-tenant child excluded
    conn.commit()
    conn.close()
    assert queries.cascade_preview(db, "default", "A")["affected"] == []


def test_no_descendants(tmp_path):
    db = str(tmp_path / "n.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    conn.commit()
    conn.close()
    assert queries.cascade_preview(db, "default", "A") == {
        "stmt_id": "A", "affected": [], "affected_count": 0, "truncated": False}


def test_missing_or_cross_tenant_root_is_none(tmp_path):
    db = str(tmp_path / "m.db")
    conn = _fresh_db(db)
    _ins(conn, "A", tenant="other")
    conn.commit()
    conn.close()
    assert queries.cascade_preview(db, "default", "A") is None      # cross-tenant root
    assert queries.cascade_preview(db, "default", "nope") is None   # missing root


def test_max_depth_truncates(tmp_path):
    db = str(tmp_path / "d.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    _ins(conn, "B", derived='["A"]')
    _ins(conn, "C", derived='["B"]')
    conn.commit()
    conn.close()
    out = queries.cascade_preview(db, "default", "A", max_depth=1)
    assert {a["id"] for a in out["affected"]} == {"B"}  # C is beyond depth 1
    assert out["truncated"] is True


def test_malformed_sibling_does_not_poison_walk(tmp_path):
    # A single row with garbage derived_from_json must NOT abort the scan — A's real
    # subtree must still surface. Regression for the SQL-json_each(EXISTS) blocker that
    # raised on the first bad row and silently degraded to "0 affected" (false green).
    db = str(tmp_path / "bad.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    _ins(conn, "B", derived='["A"]')
    _ins(conn, "C", derived='["B"]')
    _ins(conn, "GARBAGE", derived="{not valid json")  # unrelated + malformed
    conn.commit()
    conn.close()
    out = queries.cascade_preview(db, "default", "A")
    assert {a["id"] for a in out["affected"]} == {"B", "C"}  # not silently zeroed


def test_truncated_false_when_subtree_fits_at_boundary(tmp_path):
    # A→B→C fits exactly at max_depth=2 → all captured, truncated MUST be False (the
    # frontend renders truncated as "N+", so a false positive overcounts the blast radius).
    db = str(tmp_path / "fit.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    _ins(conn, "B", derived='["A"]')
    _ins(conn, "C", derived='["B"]')
    conn.commit()
    conn.close()
    out = queries.cascade_preview(db, "default", "A", max_depth=2)
    assert {a["id"] for a in out["affected"]} == {"B", "C"}
    assert out["truncated"] is False


def test_node_cap_truncates(tmp_path):
    db = str(tmp_path / "cap.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    for i in range(5):
        _ins(conn, f"K{i}", derived='["A"]')
    conn.commit()
    conn.close()
    out = queries.cascade_preview(db, "default", "A", max_nodes=3)
    assert out["affected_count"] == 3      # capped
    assert out["truncated"] is True


def test_empty_null_and_duplicate_parents_tolerated(tmp_path):
    db = str(tmp_path / "edge.db")
    conn = _fresh_db(db)
    _ins(conn, "A")
    _ins(conn, "B", derived='["A","A"]')   # duplicate parent → B listed once
    _ins(conn, "C", derived="[]")          # no parents (unrelated)
    conn.commit()
    conn.close()
    out = queries.cascade_preview(db, "default", "A")
    assert {a["id"] for a in out["affected"]} == {"B"}
