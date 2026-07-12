"""Task 3 — dashboard-embedded spool ingest worker (dogfood sub-project A).

Consumes jobs written by `scripts/ingest_session.py` (Task 2) from
`<spool>/*.json`: claim -> clean/chunk the transcript (ingest_filter, Task 1)
-> self.remember() each chunk -> done/ on success or once retries are
exhausted, back to the spool root (attempts incremented) on a still-retryable
failure.

Ground truth verified directly against the C++ core (not assumed from the
task brief), updated by the opus review fix wave (2026-07-12):
  - Interlocutor attribution is stored in `statements.scope_parties_json`
    (a JSON array like ["claude-code:foo","self"]; migrations/0022), not an
    `interlocutor_id` column.
  - The worker calls `self.remember(...)` (DashboardEngine's lock-wrapped
    method), NOT `self._core.remember(...)`. remember() holds `self._lock`
    across the whole extraction LLM call — the same discipline every other
    engine writer (tick/forget/approve_review/converse_commit) follows — so
    the worker's writes correctly serialize against concurrent tick/HTTP
    engine calls instead of racing the single sqlite3 writer connection
    (see _ingest_drain_once's docstring in engine.py for the full
    single-writer-violation analysis this fix addresses). The cost (ingest
    serialized with the rest of the dashboard during extraction) is offset
    by a heavy throttle (_ingest_throttle_s) between processed jobs so a
    backlog doesn't pin the dashboard.
  - `RememberOutcome.extraction_failed` (src/memory/memory_ops.cpp:78) is
    now surfaced through the `memory_remember` binding (bindings/python/
    bind_13_memory_ops.cpp) and forwarded untouched by MemoryCore.remember()
    (python/starling/_memory_core.py). extraction_failed=False is success
    REGARDLESS of statement count (an all-chitchat chunk legitimately
    extracts zero statements and is not an error) — the old "zero
    statements across every chunk = permanent failure" heuristic
    misclassified exactly this common case and has been removed.
  - Every failure (extraction_failed=True, or any raised exception) is now
    a uniform bounded retry: `attempts` is persisted on the job JSON and
    incremented each retryable failure; below `_ingest_max_attempts` the
    job goes back to the spool root for a LATER poll (never hot-reclaimed
    in the same call), at/above it the job is dead-lettered to failed/ with
    a `.error` sidecar. This replaces the old message-substring
    transient/permanent keyword heuristic entirely.
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
    assert eng._ingest_drain_once() == "done"
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
    assert eng._ingest_drain_once() == "empty"


def test_worker_uses_locked_remember(tmp_path):
    """Fix 1 (opus review Hazard 1): the worker MUST serialize its remember()
    call through self._lock like every other engine writer. This is the
    opposite assertion of the deleted test_worker_does_not_hold_lock_across_
    remember, which was a false victory — it passed only because the worker
    bypassed the single-writer lock entirely. Here, a concurrent thread
    trying to acquire self._lock while the worker is mid-remember() must
    WAIT at least the stub delay, proving the lock is actually held across
    the call (not released early)."""
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, delay_ms=700)  # remember 内睡 700ms(×3 抽取通道)
    _job(spool, _transcript(tmp_path))
    t = threading.Thread(target=eng._ingest_drain_once)
    t.start()
    time.sleep(0.15)                              # worker 已进 remember()
    start = time.monotonic()
    with eng._lock:                                # 并发拿锁:worker 应该整段占着
        pass
    waited = time.monotonic() - start
    t.join(timeout=5)
    assert waited >= 0.4, (
        f"等锁仅 {waited:.2f}s —— worker 没有把 remember 圈进 self._lock,"
        f"single-writer 保证已失效")


def test_empty_extraction_is_success_not_failed(tmp_path):
    """Fix 2 (opus review Hazard 2): a legit zero-statement extraction
    (ok=True, valid empty JSON array — e.g. a pure-chitchat chunk with no
    memory-worthy facts) is a SUCCESS, not a failure. RememberOutcome.
    extraction_failed is only True when the LLM/parse failed on every
    retry (Status::FAILED) — never for a successful-but-empty result."""
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool)
    eng.llm.set_default_response("[]", True, "")  # valid JSON, zero statements
    _job(spool, _transcript(tmp_path, text="ok, sounds good"))
    assert eng._ingest_drain_once() == "done"
    assert list((spool / "done").glob("*.json")) and not list(spool.glob("*.json"))
    assert not (spool / "failed").exists() or not list((spool / "failed").glob("*"))


def test_retryable_failure_bounded_retry_then_failed(tmp_path):
    """Fix 3: extraction_failed=True (adapter ok=False -> every retry
    attempt fails -> Status::FAILED) is retryable, not instantly permanent.
    The job stays in the spool (attempts incremented each round) while
    attempts < _ingest_max_attempts, and is only dead-lettered to failed/
    once the bound is reached."""
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, ok=False)   # 抽取 LLM 持续失败 → extraction_failed=True
    eng._ingest_max_attempts = 3               # 收紧到 3 轮,测试不必跑默认的 5 轮
    _job(spool, _transcript(tmp_path))

    assert eng._ingest_drain_once() == "deferred"
    job = json.loads((spool / "s1.json").read_text())
    assert job["attempts"] == 1
    assert not (spool / "failed").exists() or not list((spool / "failed").glob("*"))

    assert eng._ingest_drain_once() == "deferred"
    job = json.loads((spool / "s1.json").read_text())
    assert job["attempts"] == 2

    assert eng._ingest_drain_once() == "done"  # 第 3 次(达到 max attempts)→ dead-letter
    assert list((spool / "failed").glob("s1.json")) and not (spool / "s1.json").exists()
    assert (spool / "failed" / "s1.json.error").exists()


def test_reaper_reclaims_stale_processing(tmp_path):
    """Fix 4: a `*.json.processing` file present at start_ingest_worker()
    time is a crash-stranded claim (single worker -> no live claimant could
    exist yet). The reaper renames it back to `*.json` synchronously,
    BEFORE the poll loop starts, so it is immediately visible again and no
    data is lost to a mid-flight crash."""
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool)
    spool.mkdir(parents=True, exist_ok=True)
    stale = spool / "crashed.json.processing"
    stale.write_text(json.dumps(
        {"session_id": "crashed", "transcript_path": "/nonexistent", "cwd": "/proj/x"}))
    eng.start_ingest_worker(poll_interval_s=60)  # 大间隔:断言窗口内 worker 线程不会自己抢
    try:
        assert not stale.exists()
        assert (spool / "crashed.json").exists()
    finally:
        eng.stop_ingest_worker()


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
    assert body["ingest_remember_ms_total"] == 0


def test_ingest_status_route_503_when_no_engine(tmp_path):
    from fastapi.testclient import TestClient
    from starling.dashboard import DashboardConfig, create_app

    cfg = DashboardConfig(db_path=str(tmp_path / "rh.db"), token="", tick_interval_s=0)
    client = TestClient(create_app(cfg))   # engine=None
    r = client.get("/api/ingest_status")
    assert r.status_code == 503
