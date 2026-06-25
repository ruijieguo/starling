"""forecast query — Phase 3 片 5 衰减预报:C++ forgetting_curve 只读投影 + 排序。

裸插 statements(可控 last_accessed/salience/state)→ 断言按 S(t) 升序(最可能被遗忘
在前)、候选有界 LIMIT、tenant-scoped、终态排除、active_grounded 镜像 commitment 保护。
S(t) 本身的 parity 在 test_forgetting_binding_parity.py;这里测查询编排。"""
import sqlite3
from pathlib import Path

from starling.dashboard import queries

_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, modality, "
    "polarity, confidence, observed_at, salience, affect_json, activation, "
    "last_accessed, provenance, created_at, updated_at, access_count, consolidation_state"
)


def _ins(conn, sid, *, tenant="default", salience=0.5, last_accessed="2026-04-10T10:00:00Z",
         access_count=0, state="consolidated", subj="X", modality="BELIEVES"):
    conn.execute(
        f"INSERT INTO statements ({_COLS}) VALUES ({','.join('?' * 23)})",
        (sid, tenant, "self", "first_person", "cognizer", subj, "rel",
         "str", "v", f"h{sid}", modality, "POS", 0.9, "2026-04-10T10:00:00Z",
         salience, "{}", 0.0, last_accessed, "user_input", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", access_count, state),
    )


def _fresh_db(db_path: str):
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r
    return sqlite3.connect(db_path)


def test_forecast_ranks_ascending_by_s_t(tmp_path):
    db = str(tmp_path / "fc.db")
    conn = _fresh_db(db)
    # 久未访问 + 低 salience → 低 S(t)(最可能遗忘);新近 + 高 salience + 高访问 → 高 S(t)。
    _ins(conn, "old", last_accessed="2025-01-01T00:00:00Z", salience=0.0)
    _ins(conn, "new", last_accessed="2026-06-20T00:00:00Z", salience=1.0, access_count=10)
    conn.commit()
    conn.close()
    out = queries.forecast(db, "default", now="2026-06-24T00:00:00Z")
    assert [r["id"] for r in out["rows"]] == ["old", "new"]   # 升序
    assert out["rows"][0]["s_t"] <= out["rows"][1]["s_t"]
    assert out["rows"][0]["forget_at"]                        # 有预计时点(ISO)
    assert out["threshold"] == 0.05


def test_forecast_bounded_limit(tmp_path):
    db = str(tmp_path / "fc.db")
    conn = _fresh_db(db)
    for i in range(5):
        _ins(conn, f"s{i}", last_accessed=f"2026-0{i + 1}-01T00:00:00Z")
    conn.commit()
    conn.close()
    out = queries.forecast(db, "default", now="2026-07-01T00:00:00Z", limit=3)
    assert len(out["rows"]) == 3 and out["candidate_limit"] == 3   # 候选有界,不全表


def test_forecast_excludes_terminal_and_other_tenant(tmp_path):
    db = str(tmp_path / "fc.db")
    conn = _fresh_db(db)
    _ins(conn, "vol", state="volatile")
    _ins(conn, "con", state="consolidated")
    _ins(conn, "arch", state="archived")                       # 终态 — 排除
    _ins(conn, "forg", state="forgotten")                      # 终态 — 排除
    _ins(conn, "alien", state="consolidated", tenant="other")  # 跨租户 — 排除
    conn.commit()
    conn.close()
    ids = {r["id"] for r in queries.forecast(db, "default", now="2026-07-01T00:00:00Z")["rows"]}
    assert ids == {"vol", "con"}


def test_forecast_active_grounded_from_commitment(tmp_path):
    db = str(tmp_path / "fc.db")
    conn = _fresh_db(db)
    _ins(conn, "prot", state="consolidated")
    _ins(conn, "free", state="consolidated")
    conn.execute("INSERT INTO commitments (tenant_id, stmt_id, state, created_at, updated_at) "
                 "VALUES ('default','c1','ACTIVE','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO commitment_protection (tenant_id, commitment_stmt_id, "
                 "protected_stmt_id) VALUES ('default','c1','prot')")
    conn.commit()
    conn.close()
    rows = {r["id"]: r for r in queries.forecast(db, "default", now="2026-07-01T00:00:00Z")["rows"]}
    assert rows["prot"]["active_grounded"] is True
    assert rows["free"]["active_grounded"] is False
    # 受 ACTIVE commitment 保护 → S0 更高 → 同输入下 S(t) 更高(更难忘)。
    assert rows["prot"]["s_t"] > rows["free"]["s_t"]
