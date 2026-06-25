"""Phase 3 片 6 干预集 — engine 路径连通 + 写动作语义(approve/reject=forget/replay/reconsolidate)。

approve_review 的 SQL 守卫/幂等/tenant 语义在 ctest StatementStore.ApproveReview* 钉死;
这里测 **Python 连通**:engine → MemoryCore → _core 绑定回正确形、走 self._lock、且实际改库。
全用真 DashboardEngine + FakeLLMAdapter(真 remember 造真语句),只读校验走 queries.open_ro。"""
import sqlite3

import pytest

from starling import _core
from starling.dashboard import DashboardConfig, queries
from starling.dashboard.engine import DashboardEngine

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _engine(db):
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    eng.llm = fake
    return eng


def test_approve_review_wiring_and_guard(tmp_path, monkeypatch):
    # remember → approved 语句;approve 它 → 守卫 no-op(非 review_requested)→ approved=0。
    # 证明 engine→MemoryCore→_core 连通 + 守卫(→approved 转换由 ctest 钉)。
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "iv.db")
    eng = _engine(db)
    sid = eng.remember("Bob is responsible for auth")["statement_ids"][0]
    r = eng.approve_review(sid)
    assert r == {"approved": 0}          # 该行是 approved,非 review_requested → 守卫挡住
    # 不存在的 id 也安全(0),不崩。
    assert eng.approve_review("nope")["approved"] == 0


def test_reject_is_forget(tmp_path, monkeypatch):
    # reject = forget(决策):→forgotten 终态,检索排除。
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "iv.db")
    eng = _engine(db)
    sid = eng.remember("Bob is responsible for auth")["statement_ids"][0]
    assert eng.forget([sid])["forgotten"] == 1
    with queries.open_ro(db) as c:
        state = c.execute("SELECT consolidation_state FROM statements WHERE id=?",
                          (sid,)).fetchone()[0]
    assert state == "forgotten"


def test_run_replay_sleep_produces_batch(tmp_path, monkeypatch):
    # 手动 SLEEP 触发(批 200)采样 volatile 语句 → 写一条 replay_ledger(mode='sleep')。
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "iv.db")
    eng = _engine(db)
    eng.remember("Bob is responsible for auth")
    r = eng.run_replay("sleep")
    assert r["mode"] == "sleep" and "sampled" in r and "replay_batch_id" in r
    with queries.open_ro(db) as c:
        modes = {row[0] for row in c.execute("SELECT DISTINCT mode FROM replay_ledger")}
    assert "sleep" in modes        # SLEEP 批落了 ledger 行(片 2/4 的空 SLEEP 数据被接通)


def test_run_replay_idle_wiring(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "iv.db")
    eng = _engine(db)
    eng.remember("Bob is responsible for auth")
    r = eng.run_replay("idle")
    assert r["mode"] == "idle" and isinstance(r["sampled"], int)


def test_request_reconsolidation_emits_event(tmp_path, monkeypatch):
    # 请求再固化 → 发 reconsolidate.requested 事件(引擎异步开窗)。
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "iv.db")
    eng = _engine(db)
    sid = eng.remember("Bob is responsible for auth")["statement_ids"][0]
    out = eng.request_reconsolidation(sid, request_id="req-1")
    assert out["event_id"]
    with queries.open_ro(db) as c:
        n = c.execute("SELECT COUNT(*) FROM bus_events WHERE event_type='reconsolidate.requested' "
                      "AND primary_id=?", (sid,)).fetchone()[0]
    assert n == 1


def test_statements_review_status_filter(tmp_path, monkeypatch):
    # 审批队列复用 queries.statements(review_status=...) 过滤。
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "iv.db")
    eng = _engine(db)
    eng.remember("Bob is responsible for auth")   # approved
    approved = queries.statements(db, "default", review_status="approved")["rows"]
    assert approved and all(r["review_status"] == "approved" for r in approved)
    # review_requested 队列此刻为空(无 chunk-dup)。
    assert queries.statements(db, "default", review_status="review_requested")["rows"] == []
