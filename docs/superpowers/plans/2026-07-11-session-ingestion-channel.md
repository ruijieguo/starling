# 会话摄入通道(dogfood 子项 A)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code 会话结束时自动把清洁对话喂进 starling 产生真实记忆负载——纯 host 适配、零内核改动、复用现有 `remember`。

**Architecture:** SessionEnd hook → 过滤脚本(剥 thinking/tool/代码、分块)→ `POST /api/ingest`(幂等入队 + 立即 200)→ 后台 worker(串行消化 → `engine.remember`)→ statements 落 `inferred_unreviewed` 可 dashboard 检视。队列用 **host 独立 `ingest.db`**(与 core 的 `dashboard.db` 分离,彻底避开单写者争议)。

**Tech Stack:** FastAPI host(`python/starling/dashboard/`)、Python stdlib 脚本(`scripts/`)、sqlite3(host 队列)、Claude Code SessionEnd hook。**无 C++。**

**Approved spec:** `docs/superpowers/specs/2026-07-11-session-ingestion-channel-design.md`(branch `feat/session-ingestion-channel` @ `058dc38`)。

**⚠️ eng-review 定谳点(实现前 `/plan-eng-review`):** (1) 去重键/分块/dead-letter 策略是否属「预算/裁剪」核心须归 C++;(2) 队列用独立 `ingest.db`(本计划默认,最保守)vs 共享 `dashboard.db`(spec §③ 原文)。**本计划按独立 `ingest.db` 写**——比 spec 更保守(host 完全自持、不与 core 写连接争 db);若 eng-review 判要共享或归内核,Task 1 的连接目标与建表位置随之调整,其余任务不变。

## Global Constraints

- 架构边界(硬):全 host 应用适配;`remember`/extraction/幂等/`review_status`/recall 语义全在 C++ 零改动;`ingest_queue` 是 host 建表(`CREATE TABLE IF NOT EXISTS`)不进 C++ MigrationRunner。
- 单写者不变:队列写在 host 独立 `ingest.db`(不碰 core 的 `dashboard.db` 写连接);worker 的 `remember` 经 `engine._lock`。
- 幂等去重不变式归写入器:`ingest_queue` INSERT OR IGNORE by `(session_id, chunk_index)`,调用方不自建防重集合。
- hook 脚本绝不非零退出阻塞会话:任何异常 exit 0 + 本地日志。
- 摄入端点绝不在请求内跑 extraction:入队 → 立即 200。
- pytest 一律 `.venv/bin/python -m pytest`。零内核改动 → 无需 `configure_build`(除非 eng-review 翻案判某策略须归 C++)。
- git:显式路径 `git add`(禁 `.`/`-A`);不用 `--no-verify`/`--amend`;commit 尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- NEVER merge:PR + CI 绿 + 用户明确合并。

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `python/starling/dashboard/engine.py` | 引擎门面 | + `ingest.db` 建表 + `enqueue_ingest` + `_ingest_drain_once` + `start/stop_ingest_worker` |
| `python/starling/dashboard/routes/commands.py` | 命令路由 | + `IngestBody` + `POST /api/ingest`(挨着 `/api/remember`) |
| `python/starling/dashboard/app.py` | ASGI 装配 | lifespan 启/停 ingest worker(挨着 tick) |
| `scripts/ingest_session.py` | transcript 解析/过滤/分块/POST | 新建(部署到 `~/.starling/bin/` 是运维) |
| `tests/python/test_dashboard_ingest.py` | 端点 + 入队 | 新建 |
| `tests/python/test_dashboard_ingest_worker.py` | worker 消化 | 新建 |
| `tests/python/test_ingest_session_filter.py` | 脚本过滤/分块 | 新建 |

---

### Task 1: `ingest.db` 队列表 + `POST /api/ingest` 端点

**Files:**
- Modify: `python/starling/dashboard/engine.py`(`__init__` 尾 + 新方法)
- Modify: `python/starling/dashboard/routes/commands.py`(body 定义区 + `build_commands_router` 内)
- Test: `tests/python/test_dashboard_ingest.py`

**Interfaces:**
- Consumes:`DashboardEngine._lock`(RLock, engine.py:153)、`self._db_path`(engine.py:155)、`_engine(request)`(commands.py:74)、`build_commands_router(require_token)`(commands.py:88)。
- Produces:
  - `DashboardEngine.enqueue_ingest(session_id: str, source: str, text: str, cwd: str, chunk_index: int) -> bool`(True=新入队,False=幂等跳过)
  - `POST /api/ingest`,body `{session_id, source, text, cwd, chunk_index}` → `{"queued": bool}`

- [ ] **Step 1: 写失败的端点测试**

新建 `tests/python/test_dashboard_ingest.py`(夹具抄 `tests/python/test_dashboard_commands.py` 的 `_engine_with_llm`/`client` 模式):

```python
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


@pytest.fixture
def env(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_STUB_JSON, True, "")
    eng.llm = fake
    return cfg, eng, TestClient(create_app(cfg, engine=eng))


def _ingest_rows(cfg):
    conn = sqlite3.connect(str(Path(cfg.db_path).parent / "ingest.db"))
    try:
        return conn.execute(
            "SELECT session_id, chunk_index, source, text, cwd, status "
            "FROM ingest_queue ORDER BY chunk_index").fetchall()
    finally:
        conn.close()


def test_ingest_enqueues_and_returns_200_immediately(env):
    cfg, _eng, client = env
    r = client.post("/api/ingest", json={
        "session_id": "s1", "source": "claude-code",
        "text": "User: hi\nAssistant: hello", "cwd": "/proj/foo", "chunk_index": 0})
    assert r.status_code == 200 and r.json()["queued"] is True
    rows = _ingest_rows(cfg)
    assert len(rows) == 1
    assert rows[0][0] == "s1" and rows[0][5] == "pending"


def test_ingest_is_idempotent_on_session_chunk(env):
    cfg, _eng, client = env
    body = {"session_id": "s1", "source": "claude-code", "text": "a",
            "cwd": "/p", "chunk_index": 0}
    assert client.post("/api/ingest", json=body).json()["queued"] is True
    # 重放同 (session_id, chunk_index):不重复入队,queued=False
    assert client.post("/api/ingest", json={**body, "text": "DIFFERENT"}).json()["queued"] is False
    rows = _ingest_rows(cfg)
    assert len(rows) == 1 and rows[0][3] == "a"   # 原文本不被覆盖
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_ingest.py -q`
Expected: FAIL(404 无 `/api/ingest` 路由 / `ingest.db` 不存在)。

- [ ] **Step 3: engine 建表 + enqueue**

`engine.py` 顶部确保 `import sqlite3` 与 `from pathlib import Path`(已有 Path)。在 `__init__` 末尾(:184 之后)加建表:

```python
        # dogfood 子项 A:会话摄入队列。HOST 独立 sqlite(与 core 的 dashboard.db
        # 分离——不碰单写者;非记忆 schema,不进 C++ MigrationRunner)。
        self._ingest_db_path = Path(self._db_path).parent / "ingest.db"
        self._init_ingest_db()
```

新增方法(放在 `start_background_tick` 附近):

```python
    def _ingest_conn(self) -> "sqlite3.Connection":
        return sqlite3.connect(str(self._ingest_db_path))

    def _init_ingest_db(self) -> None:
        conn = self._ingest_conn()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ingest_queue ("
                " session_id TEXT NOT NULL,"
                " chunk_index INTEGER NOT NULL,"
                " source TEXT NOT NULL,"
                " text TEXT NOT NULL,"
                " cwd TEXT,"
                " status TEXT NOT NULL DEFAULT 'pending'"
                "   CHECK (status IN ('pending','done','failed')),"
                " last_error TEXT,"
                " created_at TEXT NOT NULL,"
                " PRIMARY KEY (session_id, chunk_index))")
            conn.commit()
        finally:
            conn.close()

    def enqueue_ingest(self, session_id: str, source: str, text: str,
                       cwd: str, chunk_index: int) -> bool:
        """幂等入队一个会话对话块。INSERT OR IGNORE by (session_id,chunk_index)
        (幂等去重归写入器);撞键静默跳过返回 False。绝不在此跑 extraction。"""
        with self._lock:
            conn = self._ingest_conn()
            try:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO ingest_queue"
                    " (session_id, chunk_index, source, text, cwd, status, created_at)"
                    " VALUES (?,?,?,?,?, 'pending', ?)",
                    (session_id, chunk_index, source, text, cwd, _now_iso()))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()
```

（`_now_iso()` 是 engine.py 模块级已有 helper——确认存在;若无则用 `datetime.now(timezone.utc).isoformat()`。）

- [ ] **Step 4: 端点**

`commands.py` body 定义区(挨着 `RememberBody`, :24)加:

```python
class IngestBody(BaseModel):
    session_id: str
    source: str = "claude-code"
    text: str
    cwd: str = ""
    chunk_index: int = 0
```

`build_commands_router` 内(挨着 `/api/remember`, :91)加:

```python
    @router.post("/ingest")
    async def ingest(body: IngestBody, request: Request):
        # dogfood A:会话对话块入队 → 立即 200。后台 worker 异步消化(绝不在
        # 请求内跑 extraction,否则阻塞 SessionEnd hook 拖住会话退出)。
        eng = _engine(request)
        queued = await to_thread.run_sync(partial(
            eng.enqueue_ingest, body.session_id, body.source, body.text,
            body.cwd, body.chunk_index))
        return {"queued": queued}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_ingest.py -q`
Expected: 2 passed。

- [ ] **Step 6: Commit**

```bash
git add python/starling/dashboard/engine.py python/starling/dashboard/routes/commands.py tests/python/test_dashboard_ingest.py
git commit -m "feat(dashboard): ingest queue table + POST /api/ingest (immediate 200, idempotent)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 后台摄入 worker

**Files:**
- Modify: `python/starling/dashboard/engine.py`(新方法)
- Modify: `python/starling/dashboard/app.py`(lifespan 启/停)
- Test: `tests/python/test_dashboard_ingest_worker.py`

**Interfaces:**
- Consumes:`enqueue_ingest`(Task 1)、`self._ingest_conn`(Task 1)、`self._lock`、`engine.remember(text, holder=, interlocutor=, now=)`(engine.py:388,走 `_lock`)、`start_background_tick`/`stop_background_tick` 线程范本(engine.py:549/600)。
- Produces:
  - `DashboardEngine._ingest_drain_once() -> bool`(消化一条 pending → True;无 pending → False)
  - `DashboardEngine.start_ingest_worker(poll_interval_s: float = 2.0) -> None` / `stop_ingest_worker() -> None`

**失败策略(YAGNI 简化,plan 内定):** 失败即标 `failed` + `last_error`(dead-letter,**不 online retry**)——摄入可重放(历史 bootstrap 重灌),在线 retry 无必要;dead-letter 绝不卡队头(`failed` 不再被 `_ingest_drain_once` 取)。这是对 spec「重试有限次」的简化(理由记此)。

- [ ] **Step 1: 写失败的 worker 测试**

新建 `tests/python/test_dashboard_ingest_worker.py`:

```python
import sqlite3
from pathlib import Path

import pytest

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _engine(tmp_path, ok=True):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_JSON if ok else "not json", ok, "" if ok else "boom")
    eng.llm = fake
    return cfg, eng


def _status(cfg, session_id, chunk_index):
    conn = sqlite3.connect(str(Path(cfg.db_path).parent / "ingest.db"))
    try:
        return conn.execute(
            "SELECT status FROM ingest_queue WHERE session_id=? AND chunk_index=?",
            (session_id, chunk_index)).fetchone()[0]
    finally:
        conn.close()


def test_drain_consumes_pending_into_statements(tmp_path):
    cfg, eng = _engine(tmp_path)
    eng.enqueue_ingest("s1", "claude-code", "User: Bob owns auth", "/proj/foo", 0)
    assert eng._ingest_drain_once() is True
    assert _status(cfg, "s1", 0) == "done"
    # statement 落库,interlocutor 带项目名(cwd basename)
    import sqlite3 as _s
    conn = _s.connect(cfg.db_path)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM statements WHERE provenance LIKE 'dash-%'").fetchone()
        assert rows[0] >= 1
    finally:
        conn.close()
    assert eng._ingest_drain_once() is False   # 队列空


def test_drain_dead_letters_failure_without_blocking_head(tmp_path):
    cfg, eng = _engine(tmp_path, ok=False)     # extraction 失败
    eng.enqueue_ingest("s1", "claude-code", "bad", "/p", 0)
    eng.enqueue_ingest("s1", "claude-code", "also", "/p", 1)
    eng._ingest_drain_once()                    # 头块失败 → failed
    assert _status(cfg, "s1", 0) == "failed"
    # 队头 dead-letter 后,后续块仍可被取(不卡头)
    assert eng._ingest_drain_once() is True or _status(cfg, "s1", 1) in ("done", "failed")


def test_done_chunk_not_reprocessed(tmp_path):
    cfg, eng = _engine(tmp_path)
    eng.enqueue_ingest("s1", "claude-code", "User: x", "/p", 0)
    eng._ingest_drain_once()
    assert _status(cfg, "s1", 0) == "done"
    assert eng._ingest_drain_once() is False    # done 不重复处理
```

（注:`remember` 失败语义——`FakeLLMAdapter` 返回 `ok=False` 时 `remember` 是否抛异常 or 返回 `extraction_failed`?实现 Step 3 时据实处理:若 remember 不抛而返回失败 outcome,则据 outcome 判 failed;测试断言按实际调整,但「失败块 → failed 状态、不卡后续块」的行为契约不变。）

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_ingest_worker.py -q`
Expected: FAIL(`_ingest_drain_once` 不存在)。

- [ ] **Step 3: worker 实现**

`engine.py` 加(`_now_iso` 已用于 Task 1;`import os` 确认在顶部——用于 `os.path.basename`):

```python
    def _ingest_drain_once(self) -> bool:
        """消化一条 pending 摄入块:remember 整段清洁对话 → 标 done;失败 → 标
        failed + last_error(dead-letter,不卡队头)。持 _lock 整段(摄入 extraction
        与 tick/converse 抢锁——spec §⑥ 自闭环,实测 extraction-出锁优先级)。"""
        with self._lock:
            conn = self._ingest_conn()
            try:
                row = conn.execute(
                    "SELECT session_id, chunk_index, text, cwd FROM ingest_queue"
                    " WHERE status='pending' ORDER BY created_at, chunk_index LIMIT 1"
                ).fetchone()
                if row is None:
                    return False
                session_id, chunk_index, text, cwd = row
            finally:
                conn.close()
            project = os.path.basename(cwd.rstrip("/")) or "unknown"
            try:
                self.remember(text, holder="self",
                              interlocutor=f"claude-code:{project}")
                status, err = "done", None
            except Exception as exc:  # noqa: BLE001 — dead-letter,不卡队头
                status, err = "failed", str(exc)[:500]
            conn = self._ingest_conn()
            try:
                conn.execute(
                    "UPDATE ingest_queue SET status=?, last_error=?"
                    " WHERE session_id=? AND chunk_index=?",
                    (status, err, session_id, chunk_index))
                conn.commit()
            finally:
                conn.close()
            return True

    def start_ingest_worker(self, poll_interval_s: float = 2.0) -> None:
        if self._ingest_thread is not None:
            return
        stop = threading.Event()

        def _loop() -> None:
            while not stop.wait(poll_interval_s):
                try:
                    # 消化到空;每条之间让出(检查 stop)——一次一条给 dashboard 让路。
                    while self._ingest_drain_once():
                        if stop.is_set():
                            break
                except Exception:  # noqa: BLE001 — 保活:单轮失败不终结 worker
                    logger.exception("ingest worker drain failed")

        self._ingest_stop = stop
        self._ingest_thread = threading.Thread(
            target=_loop, name="starling-ingest", daemon=True)
        self._ingest_thread.start()

    def stop_ingest_worker(self) -> None:
        if self._ingest_thread is None:
            return
        self._ingest_stop.set()
        self._ingest_thread.join(timeout=5.0)
        self._ingest_thread = None
        self._ingest_stop = None
```

在 `__init__` 的 `self._tick_thread = None`(:165)附近加:

```python
        self._ingest_thread: threading.Thread | None = None
        self._ingest_stop: threading.Event | None = None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_ingest_worker.py -q`
Expected: 3 passed（remember 失败语义按实际微调断言后)。

- [ ] **Step 5: lifespan 启/停**

`app.py` lifespan(:48-76):在 `eng.start_background_tick(...)` 后加 `if hasattr(eng, "start_ingest_worker"): eng.start_ingest_worker()`;在 `stop_background_tick()` 前(begin_drain 之后)加 `if hasattr(eng, "stop_ingest_worker"): eng.stop_ingest_worker()`。（capability-probe 对齐现有 tick 的 `hasattr` 探测,测试注入的引擎替身不受影响。)

- [ ] **Step 6: 全量 pytest 回归 + Commit**

Run: `.venv/bin/python -m pytest tests/python -q 2>&1 | tail -3`
Expected: 全绿(既有 827 + 新增)。

```bash
git add python/starling/dashboard/engine.py python/starling/dashboard/app.py tests/python/test_dashboard_ingest_worker.py
git commit -m "feat(dashboard): background ingest worker (serial drain, dead-letter, reuses remember)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 过滤脚本 `scripts/ingest_session.py`

**Files:**
- Create: `scripts/ingest_session.py`
- Test: `tests/python/test_ingest_session_filter.py`

**Interfaces:**
- Produces(纯函数,供测试直呼):
  - `clean_turns(lines: list[str]) -> list[tuple[str, str]]`(逐行 jsonl → `[(role, text)]`,已过滤)
  - `chunk_dialogue(turns: list[tuple[str, str]], max_chars: int = 8000) -> list[str]`(拼 `User:/Assistant:` + 按 ~2000 token≈8000 char 分块)
  - `main()`(读 stdin JSON 或 argv → transcript → POST 每块;异常 exit 0)

- [ ] **Step 1: 写失败的过滤测试**

新建 `tests/python/test_ingest_session_filter.py`(用 importlib 从 `scripts/` 加载):

```python
import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "ingest_session",
    str(Path(__file__).resolve().parents[2] / "scripts" / "ingest_session.py"))
ingest_session = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest_session)


def _lines(*objs):
    return [json.dumps(o) for o in objs]


def test_clean_keeps_dialogue_drops_thinking_tools_and_tool_results():
    lines = _lines(
        {"type": "user", "message": {"role": "user", "content": "Bob owns auth"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "secret reasoning"},
            {"type": "text", "text": "Got it, Bob owns auth."},
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}]}},
        {"type": "user", "message": {"role": "user",
            "content": "<tool-result><content>file1 file2</content></tool-result>"}},
    )
    turns = ingest_session.clean_turns(lines)
    assert turns == [("user", "Bob owns auth"), ("assistant", "Got it, Bob owns auth.")]
    joined = "\n".join(t for _, t in turns)
    assert "secret reasoning" not in joined      # thinking 剔除
    assert "ls" not in joined                     # tool_use 剔除
    assert "file1" not in joined                  # tool_result 剔除


def test_chunk_splits_long_dialogue():
    turns = [("user", "x" * 5000), ("assistant", "y" * 5000)]
    chunks = ingest_session.chunk_dialogue(turns, max_chars=8000)
    assert len(chunks) >= 2
    assert all(len(c) <= 8000 + 200 for c in chunks)   # 边界宽容(轮不切碎)


def test_malformed_lines_are_skipped_not_raised():
    lines = ["{not json", json.dumps(
        {"type": "user", "message": {"role": "user", "content": "ok"}})]
    assert ingest_session.clean_turns(lines) == [("user", "ok")]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_ingest_session_filter.py -q`
Expected: FAIL(`scripts/ingest_session.py` 不存在)。

- [ ] **Step 3: 脚本实现**

新建 `scripts/ingest_session.py`:

```python
#!/usr/bin/env python3
"""dogfood 子项 A:Claude Code 会话结束 → 过滤 transcript → POST 清洁对话块给
starling /api/ingest。SessionEnd hook(command 型)以 stdin 传 {session_id,
transcript_path, cwd};也支持命令行位置参数(批量 bootstrap)。

绝不非零退出:任何异常吞掉 + 记 ~/.starling/ingest.log,exit 0(hook 失败会
阻塞会话退出)。纯 stdlib。"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = os.environ.get("STARLING_DASH_URL", "http://127.0.0.1:8787")
MAX_CHARS = 8000   # ~2000 token(1 token≈4 char);每块一条 remember
LOG = Path.home() / ".starling" / "ingest.log"


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


def clean_turns(lines: list[str]) -> list[tuple[str, str]]:
    """jsonl 行 → [(role, text)]。保留 user 纯文本 + assistant text 块;剔除
    thinking / tool_use / tool_result(<tool-result> 包裹)/ 空白。"""
    out: list[tuple[str, str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue                                  # 坏行跳过
        if not isinstance(ev, dict) or ev.get("type") not in ("user", "assistant"):
            continue
        msg = ev.get("message") or {}
        role = msg.get("role")
        content = msg.get("content")
        if role == "user" and isinstance(content, str):
            if "<tool-result>" in content:            # 工具结果注入,剔除
                continue
            text = content.strip()
            if text:
                out.append(("user", text))
        elif role == "assistant" and isinstance(content, list):
            parts = [blk.get("text", "") for blk in content
                     if isinstance(blk, dict) and blk.get("type") == "text"]
            text = "\n".join(p for p in parts if p).strip()
            if text:
                out.append(("assistant", text))
    return out


def chunk_dialogue(turns: list[tuple[str, str]], max_chars: int = MAX_CHARS) -> list[str]:
    """拼 'User: …' / 'Assistant: …',按 max_chars 分块(不切碎单轮)。"""
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for role, text in turns:
        label = "User" if role == "user" else "Assistant"
        line = f"{label}: {text}"
        if buf and size + len(line) > max_chars:
            chunks.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def _post(session_id: str, source: str, text: str, cwd: str, chunk_index: int) -> None:
    body = json.dumps({"session_id": session_id, "source": source, "text": text,
                       "cwd": cwd, "chunk_index": chunk_index}).encode()
    req = urllib.request.Request(BASE + "/api/ingest", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    token = os.environ.get("STARLING_DASH_TOKEN")
    if not token:
        try:
            cfg = json.loads((Path.home() / ".starling" / "starling.json").read_text())
            token = cfg.get("token")
        except Exception:
            token = None
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def _run(session_id: str, transcript_path: str, cwd: str) -> None:
    lines = Path(transcript_path).read_text(errors="replace").splitlines()
    chunks = chunk_dialogue(clean_turns(lines))
    for idx, chunk in enumerate(chunks):
        _post(session_id, "claude-code", chunk, cwd, idx)
    _log(f"ingested session={session_id} chunks={len(chunks)} from={transcript_path}")


def main() -> None:
    try:
        if len(sys.argv) >= 2:                        # 命令行:位置参数(bootstrap)
            transcript_path = sys.argv[1]
            session_id = sys.argv[2] if len(sys.argv) > 2 else Path(transcript_path).stem
            cwd = sys.argv[3] if len(sys.argv) > 3 else ""
        else:                                         # hook:stdin JSON
            payload = json.loads(sys.stdin.read() or "{}")
            session_id = payload.get("session_id") or "unknown"
            transcript_path = payload.get("transcript_path") or ""
            cwd = payload.get("cwd") or ""
            if not transcript_path:                   # 退化:约定路径定位
                _log(f"no transcript_path for session={session_id}; skipped")
                return
        _run(session_id, transcript_path, cwd)
    except Exception as exc:                          # 绝不非零退出阻塞会话
        _log(f"ingest failed: {exc!r}")


if __name__ == "__main__":
    main()
    sys.exit(0)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/python/test_ingest_session_filter.py -q`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_session.py tests/python/test_ingest_session_filter.py
git commit -m "feat(ingest): transcript filter/chunk script (drops thinking/tools/code, exit-0 safe)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: SessionEnd hook 配置 + 端到端 dogfood 验证(手动,非 CI 门)

**Files:**
- Modify: `dashboard/README.md`(hook 配置 + bootstrap 用法附录)
- Create(ephemeral,不提交):`$CLAUDE_JOB_DIR/tmp/ingest_e2e.py`

**Deliverable:** 真会话经 hook 全链路落库 + 一次历史 bootstrap 起量;数字进 PR body。

- [ ] **Step 1: 核实 SessionEnd hook 精确 payload**

用 find-docs / claude-code-guide 查证 hooks.md:SessionEnd 触发时机 + stdin JSON 是否含 `transcript_path`。若不含,`scripts/ingest_session.py` 的 hook 分支按 `~/.claude/projects/<cwd-slug>/<session_id>.jsonl` 约定路径定位(据查证结果补一个 fallback);记录结论到 `dashboard/README.md`。

- [ ] **Step 2: 装 hook + 端到端**

`~/.claude/settings.json` 加(dashboard 必须在跑,launchd `io.starling.dashboard`):

```json
{ "hooks": { "SessionEnd": [ { "hooks": [
  { "type": "command",
    "command": "/Users/jaredguo-mini/develop/memory/starling-web/.venv/bin/python /Users/jaredguo-mini/develop/memory/starling-web/scripts/ingest_session.py",
    "timeout": 30 } ] } ] } }
```

写 `$CLAUDE_JOB_DIR/tmp/ingest_e2e.py`:造一个含 thinking/tool/代码的样例 transcript.jsonl → 命令行跑 `scripts/ingest_session.py <path> testsess /proj/x` → 轮询 `GET /api/statements` 直到摄入 statements 出现(带 token)→ 打印 statements 数 + review_status。

- [ ] **Step 3: 历史 bootstrap 起量 + 记录**

选 3-5 个真实 `~/.claude/projects/**/*.jsonl` 批量跑脚本;等 worker 消化;记录:摄入块数、statements 落库数、期间 `POST /api/tick` 是否被摄入 extraction 阻塞(计时,对照 spec §⑥——卡顿严重度 = extraction-出锁 gated 项的实测证据)。数字进 PR body。

- [ ] **Step 4: Commit README**

```bash
git add dashboard/README.md
git commit -m "docs(ingest): SessionEnd hook setup + bootstrap usage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:** spec §① hook→Task 4;§② 过滤脚本→Task 3;§③ 异步端点→Task 1;§④ worker→Task 2;§⑤ review 门(落 inferred_unreviewed,不做前置门)→Task 2 复用 remember 默认态、无额外代码(符合);§⑥ 自闭环实测→Task 4 Step 3 记录;§⑦ 身份 holder="self"/interlocutor→Task 2;架构边界+eng-review→header 标注 + Execution Handoff。✅
**2. Placeholder scan:** 无 TBD/TODO。两处「据实微调」(Task 2 Step 1 remember 失败语义、Task 4 Step 1 SessionEnd 字段)是标注的实现时查证点 + 给了 fallback,非空占位。✅
**3. Type consistency:** `enqueue_ingest(session_id, source, text, cwd, chunk_index)→bool`、`_ingest_drain_once()→bool`、`clean_turns(lines)→[(role,text)]`、`chunk_dialogue(turns,max_chars)→[str]`——Task 间引用一致;`ingest.db` 路径 `Path(db_path).parent/"ingest.db"` 在 engine 与两个测试里一致;`IngestBody` 字段与 `enqueue_ingest` 参数一致。✅

## Execution Handoff

**先 `/plan-eng-review`**(带 outside voice,定谳 header 两个 borderline:去重/分块/dead-letter 是否属核心、独立 `ingest.db` vs 共享/内核),按结果调整计划,**再** superpowers:subagent-driven-development(每任务 implementer+reviewer,最后 whole-branch review),按项目 cadence。然后 PR;CI 绿 + 用户明确合并。
