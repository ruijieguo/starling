import sqlite3
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm

_STUB = '[]'


def _row_counts(db_path):
    # 直接查表证明「零写」(eng-review #4:recall()==[] 无法证明,remember 不 embed)。
    con = sqlite3.connect(str(db_path))
    try:
        n = {}
        for t in ("engrams", "statements", "bus_events"):
            try:
                n[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                n[t] = None   # 表不存在则跳过
        return n
    finally:
        con.close()


def _drained(tmp_path, name):
    db = tmp_path / name
    mem = Memory.open(db, llm=make_stub_llm(default_response=_STUB))
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    return mem, db


def test_remember_rejected_when_draining(tmp_path):
    mem, db = _drained(tmp_path, "wg.db")
    before = _row_counts(db)
    with pytest.raises(_core.WriteGateRejected):
        mem.remember("Alice likes tea")
    assert _row_counts(db) == before          # 门前抛 = 零新行


def test_forget_rejected_when_draining(tmp_path):
    mem, _ = _drained(tmp_path, "wg_forget.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.forget(["stmt-nonexistent"])


def test_approve_review_rejected_when_draining(tmp_path):
    mem, _ = _drained(tmp_path, "wg_appr.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.approve_review("stmt-nonexistent")


def test_converse_rejected_when_draining(tmp_path):
    mem, _ = _drained(tmp_path, "wg_conv.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.converse("hello")           # drain-at-start → 顶端 gate 抛
