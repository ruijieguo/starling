"""端到端:DRAINING 拒全部 7 前台写(完整 quiesce,查表证零写);DEGRADED 仍放行。"""
import sqlite3
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm

_BELIEF = ('[{"holder":"self","holder_perspective":"FIRST_PERSON",'
           '"subject":"cog-self","predicate":"likes","object":"tea",'
           '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]')


def _mem(tmp_path, name):
    db = tmp_path / name
    return Memory.open(db, llm=make_stub_llm(default_response=_BELIEF)), db


def _total_rows(db):
    con = sqlite3.connect(str(db))
    try:
        total = 0
        for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            total += con.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
        return total
    finally:
        con.close()


def test_draining_rejects_all_foreground_writes(tmp_path):
    mem, db = _mem(tmp_path, "quiesce.db")
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    core = mem._core
    before = _total_rows(db)
    for call in (
        lambda: mem.remember("Alice likes tea"),
        lambda: core.converse("hello"),
        lambda: core.forget(["s-x"]),
        lambda: core.approve_review("s-x"),
        lambda: core.request_reconsolidation("s-x", request_id="r-1"),
        lambda: core.fulfill_commitment("s-x"),
        lambda: core.withdraw_commitment("s-x"),
    ):
        with pytest.raises(_core.WriteGateRejected):
            call()
    assert _total_rows(db) == before        # 门前抛 = 全库零新行


def test_degraded_still_allows_remember(tmp_path):
    """DEGRADED 只 shed 后台 Soft stage,不拒前台写。"""
    mem, _ = _mem(tmp_path, "degraded.db")
    d = _core.HealthDecision()               # 无 degraded_decision 自由函数;手构 HealthDecision
    d.target_status = _core.RuntimeHealth.DEGRADED   # bind_14_governance.cpp:70 def_readwrite
    d.trigger = "test_backpressure"
    mem._rt.note_health(d)
    assert mem._rt.health() == _core.RuntimeHealth.DEGRADED
    r = mem.remember("Alice likes tea")      # DEGRADED 下写成功(不抛)
    assert r.engram_ref                       # 有 engram → 写落库
    # eng-review #3: remember 不 embed;recall 需先 tick 才能召回。
    # DEGRADED 下 embed 阶段为软阶段被 shed(test_backpressure_loadshed.py 已验证),
    # 须先恢复 READY 再 tick,embed 才会运行,recall 才能命中向量。
    ready = _core.HealthDecision()
    ready.target_status = _core.RuntimeHealth.READY
    ready.trigger = "test_recovery"
    mem._rt.note_health(ready)
    mem.tick("2026-06-01T10:00:00Z")          # READY 下 embed 运行 → 向量写入
    assert mem.recall("tea")                  # tick 后可召回 → 真落库 + 可检索
