"""#39 片6 承诺手动流转 — engine→MemoryCore→_core.CommitmentEngine 连通 + ACTIVE 守卫 + 409 语义。

fulfill/withdraw 的 ACTIVE 原子守卫(只动 ACTIVE、幂等、不覆盖已结算)在 ctest
CommitmentEngine.{FulfillOnlyActsOnActiveAndIsIdempotent,ManualTransitionNeverOverwritesTerminal}
钉死。这里测 Python 连通:engine 回 {acted,state} 正确形、走 self._lock、写实际落库(经
queries.open_ro 另开只读连接回读 → 证明已 commit);非 ACTIVE → acted False(路由据此回 409)。
真 DashboardEngine;commitments 行用一次性 runtime 建表后直插播种。
"""
import sqlite3
from pathlib import Path

from starling.dashboard import DashboardConfig, queries
from starling.dashboard.engine import DashboardEngine


def _prep_db(db, stmt_id, *, state="ACTIVE", tenant="default"):
    """Build the schema via a throwaway runtime (released before seeding), then
    seed one commitment row directly — same handle-release discipline the cascade
    test uses, so the DashboardEngine opens a clean, already-seeded DB."""
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    runtime = rt._build_local_store_sqlite_runtime(Path(db))
    runtime.start()
    del runtime  # release the writer handle before raw seeding + before the engine opens
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO commitments(tenant_id, stmt_id, state, broken_count, deadline, "
            "created_at, updated_at) VALUES(?,?,?,0,?,?,?)",
            (tenant, stmt_id, state, "2026-06-30T12:00:00Z",
             "2026-06-24T10:00:00Z", "2026-06-24T10:00:00Z"))
        conn.commit()
    finally:
        conn.close()


def _state(db, stmt_id, tenant="default"):
    with queries.open_ro(db) as conn:
        row = conn.execute("SELECT state FROM commitments WHERE tenant_id=? AND stmt_id=?",
                           (tenant, stmt_id)).fetchone()
    return row[0] if row else None


def test_fulfill_active_commitment(tmp_path):
    db = str(tmp_path / "ct.db")
    _prep_db(db, "c1")
    eng = DashboardEngine(DashboardConfig(db_path=db, token=""))
    assert eng.fulfill_commitment("c1") == {"acted": True, "state": "FULFILLED"}
    assert _state(db, "c1") == "FULFILLED"   # actually committed (read via separate ro conn)


def test_withdraw_active_commitment(tmp_path):
    db = str(tmp_path / "ct.db")
    _prep_db(db, "c1")
    eng = DashboardEngine(DashboardConfig(db_path=db, token=""))
    assert eng.withdraw_commitment("c1") == {"acted": True, "state": "WITHDRAWN"}
    assert _state(db, "c1") == "WITHDRAWN"


def test_non_active_is_noop_acted_false(tmp_path):
    # 路由据 acted=False 回 409。已结算承诺不被强写覆盖(核心 ACTIVE 守卫)。
    db = str(tmp_path / "ct.db")
    _prep_db(db, "c1", state="WITHDRAWN")
    eng = DashboardEngine(DashboardConfig(db_path=db, token=""))
    assert eng.fulfill_commitment("c1") == {"acted": False, "state": "FULFILLED"}
    assert _state(db, "c1") == "WITHDRAWN"   # NOT force-overwritten to FULFILLED


def test_missing_commitment_is_safe_acted_false(tmp_path):
    db = str(tmp_path / "ct.db")
    _prep_db(db, "c1")                       # only c1 exists
    eng = DashboardEngine(DashboardConfig(db_path=db, token=""))
    assert eng.withdraw_commitment("nope") == {"acted": False, "state": "WITHDRAWN"}


def test_fulfill_is_idempotent(tmp_path):
    db = str(tmp_path / "ct.db")
    _prep_db(db, "c1")
    eng = DashboardEngine(DashboardConfig(db_path=db, token=""))
    assert eng.fulfill_commitment("c1")["acted"] is True    # ACTIVE → FULFILLED
    assert eng.fulfill_commitment("c1")["acted"] is False   # already FULFILLED → no-op
    assert _state(db, "c1") == "FULFILLED"
