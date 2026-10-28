"""设置页「危险区」:清空当前租户的全部记忆。

钉住:/api/clear_memory 的确认门(confirm 必须等于租户名)与写门(DRAINING → 503);
清空后本租户数据全无、self 认知体保留、同文本重新 remember 是全新 accepted;
spool 里本租户尚未 claim 的 job 移到 discarded/,别的租户的 job 不动;
清空发生在 job 抽取途中(锁外)时,该 job 作废进 discarded/,库里不留半截。
"""
import json
import sqlite3
import threading
import time

import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import ClearConfirmMismatch, DashboardEngine, _TenantCleared

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _engine(tmp_path, delay_ms=0):
    cfg = DashboardConfig(db_path=str(tmp_path / "clear.db"), token="")
    eng = DashboardEngine(cfg)
    eng._ingest_spool = tmp_path / "spool"
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    if delay_ms:
        fake.set_delay_ms(delay_ms)
    eng.llm = fake
    return cfg, eng


def _count(eng, sql):
    conn = sqlite3.connect(eng._db_path)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def _job(spool, tmp_path, sid, tenant="default", text="Bob owns auth"):
    spool.mkdir(parents=True, exist_ok=True)
    tp = tmp_path / f"{sid}.jsonl"
    tp.write_text(json.dumps(
        {"type": "user", "message": {"role": "user", "content": text}}))
    (spool / f"{sid}.json").write_text(json.dumps(
        {"session_id": sid, "transcript_path": str(tp), "cwd": "/proj/foo",
         "tenant": tenant}))


def test_clear_memory_rejects_wrong_confirm(tmp_path):
    cfg, eng = _engine(tmp_path)
    client = TestClient(create_app(cfg, engine=eng))
    assert client.post("/api/remember", json={"text": "Bob owns auth"}).status_code == 200
    before = _count(eng, "SELECT COUNT(*) FROM statements")
    assert before > 0

    r = client.post("/api/clear_memory", json={"confirm": "not-the-tenant"})

    assert r.status_code == 400
    assert r.json()["detail"] == "confirm_mismatch"
    assert _count(eng, "SELECT COUNT(*) FROM statements") == before   # 零写入
    with pytest.raises(ClearConfirmMismatch):
        eng.clear_memory(confirm="")


def test_clear_memory_wipes_tenant_and_remember_starts_fresh(tmp_path):
    cfg, eng = _engine(tmp_path)
    client = TestClient(create_app(cfg, engine=eng))
    assert client.post("/api/remember", json={"text": "Bob owns auth"}).json()["statement_ids"]
    client.post("/api/tick", json={})
    assert client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    selves = _count(eng, "SELECT COUNT(*) FROM cognizers WHERE kind='self'")

    r = client.post("/api/clear_memory", json={"confirm": "default"})

    assert r.status_code == 200
    body = r.json()
    assert body["tenant"] == "default"
    assert body["total"] > 0
    assert body["deleted"]["statements"] >= 1 and body["deleted"]["engrams"] >= 1
    assert body["spool_discarded"] == 0
    for table in ("statements", "engrams", "bus_events", "statement_vectors",
                  "governance_pipeline_run"):
        assert _count(eng, f"SELECT COUNT(*) FROM {table} WHERE tenant_id='default'") == 0, table
    assert _count(eng, "SELECT COUNT(*) FROM cognizers WHERE kind='self'") == selves
    assert client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"] == []

    again = client.post("/api/remember", json={"text": "Bob owns auth"}).json()
    assert again["outcome"] == "accepted"      # 旧 engram 已删,不再判 idempotent
    assert again["statement_ids"]


def test_clear_memory_503_when_draining(tmp_path):
    cfg, eng = _engine(tmp_path)
    client = TestClient(create_app(cfg, engine=eng))
    client.post("/api/remember", json={"text": "Bob owns auth"})
    before = _count(eng, "SELECT COUNT(*) FROM statements")
    generation = eng._clear_generation
    eng.begin_drain()

    r = client.post("/api/clear_memory", json={"confirm": "default"})

    assert r.status_code == 503
    assert r.json()["detail"] == "draining"
    assert _count(eng, "SELECT COUNT(*) FROM statements") == before
    assert eng._clear_generation == generation   # 没发生的清空不作废在途 job


def test_clear_memory_discards_pending_jobs_of_this_tenant_only(tmp_path):
    _, eng = _engine(tmp_path)
    spool = eng._ingest_spool
    _job(spool, tmp_path, "mine")
    _job(spool, tmp_path, "theirs", tenant="other")

    out = eng.clear_memory(confirm="default")

    assert out["spool_discarded"] == 1
    assert (spool / "discarded" / "mine.json").exists()
    assert not (spool / "mine.json").exists()
    assert (spool / "theirs.json").exists()          # 别的租户的 job 原样留下
    assert eng._ingest_drain_once() == "deferred"    # 剩下的只有别的租户的 job
    assert _count(eng, "SELECT COUNT(*) FROM statements") == 0


def test_job_in_flight_during_clear_is_discarded_not_written(tmp_path):
    _, eng = _engine(tmp_path, delay_ms=700)   # 三路抽取各 700ms,全在锁外
    spool = eng._ingest_spool
    _job(spool, tmp_path, "s1")
    result = {}
    worker = threading.Thread(
        target=lambda: result.setdefault("r", eng._ingest_drain_once()))
    worker.start()
    time.sleep(0.15)                             # prepare 已写 engram,正在锁外抽取

    eng.clear_memory(confirm="default")
    worker.join(timeout=15)

    assert result.get("r") == "done"
    assert (spool / "discarded" / "s1.json").exists()
    assert not (spool / "done" / "s1.json").exists()
    assert not (spool / "s1.json").exists()      # 不进重试
    assert _count(eng, "SELECT COUNT(*) FROM statements") == 0
    assert _count(eng, "SELECT COUNT(*) FROM engrams") == 0


def test_retried_job_is_discarded_not_requeued_when_cleared_after_its_last_chunk(tmp_path):
    """整支审查 I-1（通用重试分支，W4 之前就有的同类缺口）：最后一块抽取失败，而清空恰好落在这块
    commit 之后、job 放回 spool 之前。clear_memory 看不到 `.processing` 的 job；重试分支若照常写回
    attempts+1 并放回，下一轮就把清空前的会话重新灌回来。必须改进 discarded/，且不写回 attempts。
    lane 开启（stub 嵌入当标定模型），来源表与语句同样不得复活。"""
    cfg = DashboardConfig(db_path=str(tmp_path / "clear.db"), token="",
                          source_lane_model="stub", source_lane_dim=8)
    eng = DashboardEngine(cfg)
    spool = eng._ingest_spool = tmp_path / "spool"
    fake = _core.FakeLLMAdapter()
    fake.set_default_response("not json", False, "boom")   # 抽取失败 → extraction_failed=True
    eng.llm = fake
    tp = tmp_path / "s1.jsonl"
    tp.write_text("\n".join(json.dumps(line) for line in (
        {"type": "user", "timestamp": "2026-10-27T09:00:00.000Z",
         "message": {"role": "user", "content": "Bob owns auth"}},
        {"type": "assistant", "timestamp": "2026-10-27T09:00:05.000Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "noted"}]}})))
    spool.mkdir(parents=True)
    job_path = spool / "s1.json"
    job = {"session_id": "s1", "transcript_path": str(tp), "cwd": "/proj/foo", "tenant": "default"}
    job_path.write_text(json.dumps(job))

    real_remember = eng.remember
    remembered = []

    def _remember_then_clear(*args, **kwargs):
        out = real_remember(*args, **kwargs)
        remembered.append(out)
        eng.clear_memory(confirm="default")    # 落在这块 commit 之后、重试分支放回之前
        return out
    eng.remember = _remember_then_clear

    assert eng._ingest_drain_once() == "done"
    assert len(remembered) == 1 and remembered[0]["extraction_failed"] is True   # 确实走到了重试分支
    assert (spool / "discarded" / "s1.json").exists()
    assert json.loads((spool / "discarded" / "s1.json").read_text()) == job, "不写回 attempts"
    assert not job_path.exists() and not list(spool.glob("*.processing"))
    assert not (spool / "failed").exists()

    eng.remember = real_remember
    assert eng._ingest_drain_once() == "empty"
    for table in ("statements", "engrams", "source_unit_meta"):
        assert _count(eng, f"SELECT COUNT(*) FROM {table}") == 0, table


def _seed_ledger(eng, batch_id, tenant):
    conn = sqlite3.connect(eng._db_path)
    try:
        conn.execute(
            "INSERT INTO replay_ledger(replay_batch_id,mode,sampled_count,ops_applied_json,"
            "started_at,tenant_id) VALUES(?,?,?,?,?,?)",
            (batch_id, "idle", 1, "{}", "2026-06-11T10:00:00Z", tenant))
        conn.commit()
    finally:
        conn.close()


def test_clear_memory_removes_dream_log_of_this_tenant(tmp_path):
    cfg, eng = _engine(tmp_path)
    client = TestClient(create_app(cfg, engine=eng))
    client.post("/api/remember", json={"text": "Bob owns auth"})
    client.post("/api/tick", json={})
    _seed_ledger(eng, "b-mine", "default")
    _seed_ledger(eng, "b-theirs", "other")
    assert _count(eng, "SELECT COUNT(*) FROM replay_ledger WHERE tenant_id='default'") >= 1

    r = client.post("/api/clear_memory", json={"confirm": "default"})

    assert r.status_code == 200
    assert r.json()["deleted"]["replay_ledger"] >= 1
    assert _count(eng, "SELECT COUNT(*) FROM replay_ledger WHERE tenant_id='default'") == 0
    # 别的租户的梦境日志原样留下,库里已无 default 数据,梦境页只剩它自己的行。
    assert _count(eng, "SELECT COUNT(*) FROM replay_ledger WHERE replay_batch_id='b-theirs'") == 1
    ledger = client.get("/api/replay").json()["ledger"]
    assert all(row["replay_batch_id"] != "b-mine" for row in ledger)


def test_remember_with_stale_generation_writes_nothing(tmp_path):
    _, eng = _engine(tmp_path)
    generation = eng._clear_generation
    eng.clear_memory(confirm="default")

    with pytest.raises(_TenantCleared):
        eng.remember("Bob owns auth", clear_generation=generation)

    assert _count(eng, "SELECT COUNT(*) FROM engrams") == 0
    assert eng.remember("Bob owns auth")["outcome"] == "accepted"   # 不带代数的调用照常
