"""Task 3 — dashboard-embedded spool ingest worker (dogfood sub-project A).

Consumes jobs written by `scripts/ingest_session.py` (Task 2) from
`<spool>/*.json`: claim -> clean/chunk the transcript (ingest_filter, Task 1)
-> remember() each chunk -> done/ on success, failed/ on a permanent error,
back to the spool root on a transient one.

Ground truth verified directly against the C++ core (not assumed from the
task brief):
  - Interlocutor attribution is stored in `statements.scope_parties_json`
    (a JSON array like ["claude-code:foo","self"]; migrations/0022), not an
    `interlocutor_id` column.
  - `MemoryCore.remember()` (python/starling/_memory_core.py) forwards to
    `_core.memory_remember`, which never raises on an extraction failure —
    src/extractor/extractor.cpp's Extractor::run retries kMaxRetries times
    then commits with Status::FAILED (no exception) — and the
    RememberOutcome.extraction_failed flag is NOT surfaced by the
    memory_remember Python binding (bindings/python/bind_13_memory_ops.cpp
    only exposes engram_ref/statement_ids/outcome). Confirmed empirically:
    an ok=False FakeLLM returns {"outcome": "accepted", "statement_ids": []}
    with no exception raised and no extraction_failed key. So the worker's
    only Python-observable signal of a systemic extraction failure is "an
    accepted/idempotent write producing zero statements across every chunk
    of a job" (see _ingest_drain_once's docstring in engine.py).
"""
import json
import sqlite3
import threading
import time

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _engine(tmp_path, spool, ok=True, delay_ms=0):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="")
    eng = DashboardEngine(cfg)
    eng._ingest_spool = spool                     # 测试注入 spool 目录
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB if ok else "not json", ok, "" if ok else "boom")
    if delay_ms:
        fake.set_delay_ms(delay_ms)
    eng.llm = fake
    return eng


def _transcript(tmp_path, text="Bob owns auth"):
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps(
        {"type": "user", "message": {"role": "user", "content": text}}))
    return tp


def _job(spool, tp, cwd="/proj/foo", sid="s1"):
    spool.mkdir(parents=True, exist_ok=True)
    (spool / f"{sid}.json").write_text(json.dumps(
        {"session_id": sid, "transcript_path": str(tp), "cwd": cwd, "tenant": "default"}))


def test_worker_consumes_job_into_statements_with_interlocutor(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool)
    _job(spool, _transcript(tmp_path))
    assert eng._ingest_drain_once() is True
    # 真断言 interlocutor 归属:scope_parties_json 是 sorted [holder, interlocutor]
    # 的 JSON 数组(verified against migrations/0022 + src/extractor/extractor.cpp),
    # 不是 interlocutor_id 列。
    conn = sqlite3.connect(eng._db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM statements "
            "WHERE scope_parties_json LIKE '%claude-code:foo%'"
        ).fetchone()[0]
        assert n >= 1
    finally:
        conn.close()
    assert (spool / "done").exists() and not list(spool.glob("*.json"))
    assert eng._ingest_drain_once() is False


def test_permanent_failure_moves_to_failed(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, ok=False)      # extraction 抽取失败(ok=False) = 永久
    _job(spool, _transcript(tmp_path))
    eng._ingest_drain_once()
    assert list((spool / "failed").glob("*")) and not list(spool.glob("*.json"))


def test_worker_does_not_hold_lock_across_remember(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, delay_ms=700)  # remember 内睡 700ms(×3 抽取通道)
    _job(spool, _transcript(tmp_path))
    t = threading.Thread(target=eng._ingest_drain_once)
    t.start()
    time.sleep(0.15)                              # worker 已进 remember(锁外读队列后)
    start = time.monotonic()
    with eng._lock:                               # 并发拿锁:worker 不该整段占着
        pass
    waited = time.monotonic() - start
    t.join(timeout=5)
    assert waited < 0.4, f"等锁 {waited:.2f}s —— worker 把 remember 圈进了外层锁"


def test_ingest_status_counts(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool)
    _job(spool, _transcript(tmp_path), sid="a"); _job(spool, _transcript(tmp_path), sid="b")
    st = eng.ingest_status()
    assert st["pending"] == 2 and st["done"] == 0 and st["failed"] == 0


# ── GET /api/ingest_status (mirrors test_dashboard_runtime_health_route.py's
# pattern: this route reaches live in-memory engine state, not a read-only
# SQL query, so it needs a real engine handle + the same 503-without-engine
# capability probe as /api/runtime_health) ──────────────────────────────────

def test_ingest_status_route_reports_counts(tmp_path):
    from fastapi.testclient import TestClient
    from starling.dashboard import create_app

    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool)
    _job(spool, _transcript(tmp_path), sid="a")
    client = TestClient(create_app(eng._cfg, engine=eng))
    r = client.get("/api/ingest_status")
    assert r.status_code == 200
    body = r.json()
    assert body["pending"] == 1 and body["done"] == 0 and body["failed"] == 0
    assert body["lock_wait_ms_total"] == 0


def test_ingest_status_route_503_when_no_engine(tmp_path):
    from fastapi.testclient import TestClient
    from starling.dashboard import DashboardConfig, create_app

    cfg = DashboardConfig(db_path=str(tmp_path / "rh.db"), token="", tick_interval_s=0)
    client = TestClient(create_app(cfg))   # engine=None
    r = client.get("/api/ingest_status")
    assert r.status_code == 503
