# 会话摄入通道(dogfood 子项 A)Implementation Plan — v2 (spool 架构)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code 会话结束时把清洁对话经 **spool 文件**异步喂进 starling 产生真实记忆负载——纯 host 适配、零内核改动、复用现有 `remember`。

**Architecture:** SessionEnd hook 只写一个 job 文件到 `~/.starling/ingest-spool/` 立即退出 → dashboard 进程内后台 worker 扫 spool、claim、读 transcript、过滤(剥 thinking/工具/tool_result/代码围栏/超长行)、分块、逐块 `remember`(**不外套 engine 锁**)→ statements 落 `inferred_unreviewed`。job 文件即持久队列(崩溃不丢、瞬态失败下轮重扫自动重试)。

**Tech Stack:** Python stdlib 脚本(`scripts/`)、FastAPI host worker(`python/starling/dashboard/`)、文件系统 spool(无 SQLite 队列、无 migration)、Claude Code SessionEnd hook。**无 C++。**

**Approved spec:** `docs/superpowers/specs/2026-07-11-session-ingestion-channel-design.md`(v2,spool;经 plan-eng-review + codex outside voice 重构)。

**⚠️ v3 amendment(D3=A,2026-07-12 实现期定谳 — 取代本文所有「worker 不外套 _lock / 锁等待埋点」表述):** opus 审出 worker 绕 `_lock` 直调 `_core.remember` = 单写者 VIOLATION(`remember` 的 `BEGIN IMMEDIATE` 横跨 44s extraction,并发写同一连接抛错/丢写)。用户裁定 **D3=A:worker 用 `self.remember` 持锁 + 重限流(`_ingest_throttle_s`)**;metric 改 `ingest_remember_ms_total`(持锁抽取墙钟)。空抽取(`extraction_failed=False`)= 成功进 done/(不再「零语句=失败」);`extraction_failed` 经绑定转发暴露;有界重试(attempts<5→留 spool、>=5→failed/)+ reaper 收残留 `.processing`。Task 3 的最终代码以 commit 952a456 为准(非本文 v2 伪代码)。

**v1→v2(plan-eng-review 定谳 2026-07-11):** 弃 v1 的「同步 POST 端点 + SQLite 队列表 + worker 外套锁」。codex 指出 v1 破两核心承诺(hook 同步 POST N 块阻塞退出;dashboard 挂时静默丢失)且外层锁零收益(remember 自持锁)。v2 spool 架构根除三者且更简单。**架构边界 eng-review 定谳:全 host(去重=remember 自带幂等/分块=传输/dead-letter=spool 目录机械,无一是记忆语义);队列=spool 文件(不碰 SQLite,彻底不涉单写者)。**

## Global Constraints

- 架构边界(硬):全 host 应用适配;`remember`/extraction/幂等/`review_status`/recall 语义全在 C++ 零改动;spool = 文件系统,无 SQLite 队列、无 C++ migration。
- **锁纪律(codex 核心):worker 消化时不外套 `engine._lock`**——`remember` 自身持锁写;摄入块之间其他请求可插入,dashboard 保持可用。
- hook 近零工作:只写 job 文件 + `exit 0`;任何异常 → 记 `~/.starling/ingest.log` + exit 0(绝不非零退出阻塞会话)。
- 幂等:job 文件 claim 用 `rename` 到 `.processing`(原子占用);statement 级重复由 `remember` 自带幂等键吸收(重抽不产重复行)。
- 瞬态失败(timeout/transport/黑洞)→ 留 spool 下轮重扫自动重试;永久失败(parse/validation)→ 移 `failed/`。
- worker 独立于 `tick_interval_s`;关停时序 = begin_drain → 停 ingest worker → stop core。
- pytest 一律 `.venv/bin/python -m pytest`。零内核改动 → 无需 `configure_build`。
- git:显式路径 `git add`(禁 `.`/`-A`);不用 `--no-verify`/`--amend`;commit 尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- NEVER merge:PR + CI 绿 + 用户明确合并。

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `scripts/ingest_session.py` | transcript 过滤/分块(纯函数)+ hook/bootstrap spool 写入器 | 新建 |
| `python/starling/dashboard/engine.py` | 后台 ingest worker + 锁等待埋点 + spool 状态计数 | + worker 方法 |
| `python/starling/dashboard/routes/inspect.py` | `GET /api/ingest_status` 只读检视 | + 路由 |
| `python/starling/dashboard/app.py` | lifespan 启/停 worker(独立于 tick;关停时序) | 改 lifespan |
| `tests/python/test_ingest_session_filter.py` | 过滤/分块 | 新建 |
| `tests/python/test_ingest_session_spool.py` | hook/bootstrap 写 job | 新建 |
| `tests/python/test_dashboard_ingest_worker.py` | worker 消化/dead-letter/不持锁/状态 | 新建 |

---

### Task 1: 过滤 + 分块纯函数(含代码围栏剔除)

**Files:**
- Create: `scripts/ingest_session.py`(先只写 `clean_turns` + `chunk_dialogue` + 模块常量)
- Test: `tests/python/test_ingest_session_filter.py`

**Interfaces:**
- Produces:
  - `clean_turns(lines: list[str]) -> list[tuple[str, str]]`(jsonl 行 → `[(role, text)]`,已剥 thinking/tool_use/tool_result/**代码围栏/超长行**)
  - `chunk_dialogue(turns: list[tuple[str, str]], max_chars: int = 8000) -> list[str]`

- [ ] **Step 1: 写失败的过滤测试**

新建 `tests/python/test_ingest_session_filter.py`(importlib 从 `scripts/` 加载):

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


def test_clean_keeps_dialogue_drops_thinking_tools_tool_results():
    lines = _lines(
        {"type": "user", "message": {"role": "user", "content": "Bob owns auth"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "secret reasoning"},
            {"type": "text", "text": "Got it, Bob owns auth."},
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls -la"}}]}},
        {"type": "user", "message": {"role": "user",
            "content": "<tool-result><content>file1 file2</content></tool-result>"}},
    )
    turns = ingest_session.clean_turns(lines)
    assert turns == [("user", "Bob owns auth"), ("assistant", "Got it, Bob owns auth.")]
    joined = "\n".join(t for _, t in turns)
    assert "secret reasoning" not in joined and "ls -la" not in joined and "file1" not in joined


def test_clean_strips_code_fences_and_long_lines():
    # codex 修正:spec 说去代码围栏 + 超长行,过滤必须真去(否则 commit 撒谎)。
    text = ("Here is the fix:\n```python\ndef f():\n    return 42\n```\nDone.\n"
            + "X" * 5000)   # 超长单行(命令 stdout 残留)
    lines = _lines({"type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
    turns = ingest_session.clean_turns(lines)
    kept = turns[0][1]
    assert "Here is the fix:" in kept and "Done." in kept
    assert "def f():" not in kept and "return 42" not in kept   # 围栏内容去掉
    assert "X" * 5000 not in kept                                # 超长行去掉


def test_chunk_splits_long_dialogue():
    turns = [("user", "x" * 5000), ("assistant", "y" * 5000)]
    chunks = ingest_session.chunk_dialogue(turns, max_chars=8000)
    assert len(chunks) >= 2 and all(len(c) <= 8000 + 200 for c in chunks)


def test_malformed_lines_skipped_not_raised():
    lines = ["{not json", json.dumps(
        {"type": "user", "message": {"role": "user", "content": "ok"}})]
    assert ingest_session.clean_turns(lines) == [("user", "ok")]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_ingest_session_filter.py -q`
Expected: FAIL(`scripts/ingest_session.py` 不存在)。

- [ ] **Step 3: 实现过滤(先写文件头 + 两个纯函数)**

新建 `scripts/ingest_session.py`:

```python
#!/usr/bin/env python3
"""dogfood 子项 A:Claude Code SessionEnd → 写 spool job 文件(hook 近零工作);
worker 异步消费。也支持 --bootstrap 批量喂历史会话。纯 stdlib。"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

SPOOL = Path.home() / ".starling" / "ingest-spool"
LOG = Path.home() / ".starling" / "ingest.log"
MAX_CHARS = 8000     # ~2000 token
_LONG_LINE = 400     # 超长单行阈值(命令 stdout / base64 残留)
_FENCE = re.compile(r"```.*?```", re.DOTALL)   # 代码围栏(含多行)


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass


def _strip_code(text: str) -> str:
    text = _FENCE.sub(" ", text)                                   # 去代码围栏
    keep = [ln for ln in text.splitlines() if len(ln) <= _LONG_LINE]  # 去超长行
    return "\n".join(keep).strip()


def clean_turns(lines: list[str]) -> list[tuple[str, str]]:
    """jsonl 行 → [(role, text)]。保留 user 纯文本 + assistant text 块;剔除
    thinking / tool_use / tool_result / 代码围栏 / 超长行。"""
    out: list[tuple[str, str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if not isinstance(ev, dict) or ev.get("type") not in ("user", "assistant"):
            continue
        msg = ev.get("message") or {}
        role, content = msg.get("role"), msg.get("content")
        if role == "user" and isinstance(content, str):
            if "<tool-result>" in content:
                continue
            text = _strip_code(content)
            if text:
                out.append(("user", text))
        elif role == "assistant" and isinstance(content, list):
            parts = [blk.get("text", "") for blk in content
                     if isinstance(blk, dict) and blk.get("type") == "text"]
            text = _strip_code("\n".join(p for p in parts if p))
            if text:
                out.append(("assistant", text))
    return out


def chunk_dialogue(turns: list[tuple[str, str]], max_chars: int = MAX_CHARS) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for role, text in turns:
        line = f"{'User' if role == 'user' else 'Assistant'}: {text}"
        if buf and size + len(line) > max_chars:
            chunks.append("\n".join(buf)); buf, size = [], 0
        buf.append(line); size += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/python/test_ingest_session_filter.py -q`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_session.py tests/python/test_ingest_session_filter.py
git commit -m "feat(ingest): transcript filter/chunk (drops thinking/tools/tool_results/code fences/long lines)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: spool 写入器(hook 入口 + bootstrap)

**Files:**
- Modify: `scripts/ingest_session.py`(+ `write_job` + `main`)
- Test: `tests/python/test_ingest_session_spool.py`

**Interfaces:**
- Consumes:`SPOOL`、`_log`(Task 1)。
- Produces:
  - `write_job(session_id: str, transcript_path: str, cwd: str, tenant: str) -> Path`(写 `SPOOL/<uuid>.json`,返回路径)
  - `main()`(hook:读 stdin JSON → write_job → exit 0;`--bootstrap <path...>`:每 path 一个 job)

**⚠️ 前置(codex 时序修正):在写本任务前先核实 SessionEnd hook 精确 payload**(find-docs/claude-code-guide 查 hooks.md:SessionEnd stdin 是否含 `transcript_path`/`session_id`/`cwd`)。据结果定 `main` 的字段读取;若无 `transcript_path`,job 记 `session_id`+`cwd`,worker 按约定路径 `~/.claude/projects/<slug>/<session_id>.jsonl` 定位。把结论写进 `scripts/ingest_session.py` 顶部注释。

- [ ] **Step 1: 写失败的 spool 测试**

新建 `tests/python/test_ingest_session_spool.py`:

```python
import importlib.util
import io
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "ingest_session",
    str(Path(__file__).resolve().parents[2] / "scripts" / "ingest_session.py"))
ingest_session = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest_session)


def test_write_job_creates_spool_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    p = ingest_session.write_job("s1", "/t/x.jsonl", "/proj/foo", "default")
    assert p.exists()
    job = json.loads(p.read_text())
    assert job["session_id"] == "s1" and job["transcript_path"] == "/t/x.jsonl"
    assert job["cwd"] == "/proj/foo" and job["tenant"] == "default"


def test_hook_main_reads_stdin_and_exits_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        {"session_id": "s2", "transcript_path": "/t/y.jsonl", "cwd": "/proj/bar"})))
    monkeypatch.setattr("sys.argv", ["ingest_session.py"])
    ingest_session.main()                       # 不抛
    jobs = list((tmp_path / "spool").glob("*.json"))
    assert len(jobs) == 1 and json.loads(jobs[0].read_text())["session_id"] == "s2"


def test_malformed_stdin_exits_zero_no_throw(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    monkeypatch.setattr("sys.argv", ["ingest_session.py"])
    ingest_session.main()                       # 绝不抛(hook 不能非零退出)


def test_bootstrap_writes_job_per_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_session, "SPOOL", tmp_path / "spool")
    monkeypatch.setattr("sys.argv",
                        ["ingest_session.py", "--bootstrap", "/t/a.jsonl", "/t/b.jsonl"])
    ingest_session.main()
    assert len(list((tmp_path / "spool").glob("*.json"))) == 2
```

- [ ] **Step 2: 跑确认失败** — `.venv/bin/python -m pytest tests/python/test_ingest_session_spool.py -q`(FAIL:`write_job`/`main` 不存在)。

- [ ] **Step 3: 实现 write_job + main**

`scripts/ingest_session.py` 追加:

```python
def write_job(session_id: str, transcript_path: str, cwd: str, tenant: str) -> Path:
    SPOOL.mkdir(parents=True, exist_ok=True)
    job = {"session_id": session_id, "transcript_path": transcript_path,
           "cwd": cwd, "tenant": tenant}
    path = SPOOL / f"{uuid.uuid4().hex}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(job))
    tmp.rename(path)                              # 原子出现(worker 不会读到半写)
    return path


def main() -> None:
    try:
        argv = sys.argv[1:]
        tenant = os.environ.get("STARLING_DASH_TENANT", "default")
        if argv and argv[0] == "--bootstrap":
            for tp in argv[1:]:
                write_job(Path(tp).stem, tp, "", tenant)
            return
        payload = json.loads(sys.stdin.read() or "{}")
        sid = payload.get("session_id") or "unknown"
        tp = payload.get("transcript_path") or ""
        cwd = payload.get("cwd") or ""
        if not tp:
            _log(f"no transcript_path for session={sid}; skipped"); return
        write_job(sid, tp, cwd, tenant)
    except Exception as exc:                      # 绝不非零退出阻塞会话
        _log(f"hook failed: {exc!r}")


if __name__ == "__main__":
    main()
    sys.exit(0)
```

（注:`session_id="unknown"` 仅在无 `transcript_path` 时出现,而该分支直接 `return` 不写 job——codex 指出的「unknown 碰撞」不发生,因为无 transcript 的 job 根本不入 spool。有 transcript 时 sid 来自真实 payload。）

- [ ] **Step 4: 跑确认通过** — 4 passed。

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_session.py tests/python/test_ingest_session_spool.py
git commit -m "feat(ingest): SessionEnd hook writes spool job file + --bootstrap (near-zero hook work)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 后台 ingest worker + 状态检视

**Files:**
- Modify: `python/starling/dashboard/engine.py`（worker + 锁等待埋点）
- Modify: `python/starling/dashboard/routes/inspect.py`（`GET /api/ingest_status`）
- Modify: `python/starling/dashboard/app.py`（lifespan 启/停,独立于 tick + 关停时序）
- Test: `tests/python/test_dashboard_ingest_worker.py`

**Interfaces:**
- Consumes:`engine.remember(text, holder=, interlocutor=, now=, tenant=?)`——**确认 remember 是否接受 tenant 覆盖**;dashboard 单租户,若 remember 不收 tenant 参数,则 worker 用引擎默认 tenant(job.tenant 记录留待多租户,现阶段断言等于默认)。`self._lock`、`start_background_tick` 线程范本(engine.py:549)。`scripts/ingest_session.py` 的 `clean_turns`/`chunk_dialogue`（worker importlib 加载,或将纯函数移入可 import 的 `python/starling/dashboard/ingest_filter.py` 再由 script 复用——**实现时选后者**,避免 dashboard import scripts/)。
- Produces:
  - `DashboardEngine.start_ingest_worker(poll_interval_s=2.0)` / `stop_ingest_worker()`
  - `DashboardEngine._ingest_drain_once() -> bool`（处理一个 spool job → True;无 job → False）
  - `DashboardEngine.ingest_status() -> dict`（`{pending, processing, done, failed}`）
  - `GET /api/ingest_status`

**架构说明（避免 dashboard import scripts/):** 把 `clean_turns`/`chunk_dialogue` 抽到 `python/starling/dashboard/ingest_filter.py`（可正常 import 的包内模块),`scripts/ingest_session.py` 顶部 `from starling.dashboard.ingest_filter import clean_turns, chunk_dialogue` 复用。Task 1 的纯函数实现相应移入该模块（测试 import 路径同步改为 `from starling.dashboard.ingest_filter import ...`)。

- [ ] **Step 1: 写失败的 worker 测试**

新建 `tests/python/test_dashboard_ingest_worker.py`:

```python
import json
import threading
import time
from pathlib import Path

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
    # codex 修正:真断言 interlocutor,不只 provenance
    import sqlite3
    conn = sqlite3.connect(eng._db_path)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM statements WHERE scope_parties LIKE '%claude-code:foo%' "
            "OR interlocutor_id LIKE '%claude-code:foo%'").fetchone()
        # 若 schema 无 interlocutor 列,退化断言 provenance + 存在 statement(实现时据实定列名)
        assert rows[0] >= 1 or conn.execute(
            "SELECT COUNT(*) FROM statements WHERE provenance LIKE 'dash-%'").fetchone()[0] >= 1
    finally:
        conn.close()
    assert (spool / "done").exists() and not list(spool.glob("*.json"))
    assert eng._ingest_drain_once() is False


def test_permanent_failure_moves_to_failed(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, ok=False)      # extraction 解析失败 = 永久
    _job(spool, _transcript(tmp_path))
    eng._ingest_drain_once()
    assert list((spool / "failed").glob("*")) and not list(spool.glob("*.json"))


def test_worker_does_not_hold_lock_across_remember(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, delay_ms=700)  # remember 内睡 700ms
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
```

（注:`interlocutor`/`scope_parties` 的实际列名 + `remember` 失败是抛异常还是返回 outcome，实现 Step 3 时据 `statements` schema 与 `memory_ops` 失败语义据实定;测试断言相应微调,但「消化→落库+归属、永久失败→failed/、不持外层锁、状态计数」四个行为契约不变。)

- [ ] **Step 2: 跑确认失败** — worker 方法不存在。

- [ ] **Step 3: 实现 worker**

`engine.py`（`import json, os, time, uuid`,`from pathlib import Path` 已有;worker 用 `from starling.dashboard.ingest_filter import clean_turns, chunk_dialogue`):

```python
    # __init__ 末尾:
    self._ingest_spool = Path.home() / ".starling" / "ingest-spool"
    self._ingest_thread = None
    self._ingest_stop = None
    self._ingest_lock_wait_ms_total = 0     # 埋点:extraction-出锁 gated 项证据

    def ingest_status(self) -> dict:
        sp = self._ingest_spool
        cnt = lambda p, pat: len(list(p.glob(pat))) if p.exists() else 0
        return {"pending": cnt(sp, "*.json"), "processing": cnt(sp, "*.processing"),
                "done": cnt(sp / "done", "*"), "failed": cnt(sp / "failed", "*"),
                "lock_wait_ms_total": self._ingest_lock_wait_ms_total}

    def _ingest_drain_once(self) -> bool:
        """处理一个 spool job:claim→读 transcript→过滤→分块→逐块 remember(不外套
        _lock)→ 全成移 done/;永久错移 failed/;瞬态错留 spool 下轮重试。"""
        sp = self._ingest_spool
        jobs = sorted(sp.glob("*.json")) if sp.exists() else []
        if not jobs:
            return False
        job_path = jobs[0]
        claimed = job_path.with_suffix(".json.processing")
        try:
            job_path.rename(claimed)              # 原子 claim
        except OSError:
            return True                            # 被别的消费者抢走,下轮继续
        try:
            job = json.loads(claimed.read_text())
            tp = Path(job["transcript_path"])
            lines = tp.read_text(errors="replace").splitlines()
            project = os.path.basename((job.get("cwd") or "").rstrip("/")) or "unknown"
            chunks = chunk_dialogue(clean_turns(lines))
            for chunk in chunks:
                t0 = time.monotonic()
                with self._lock:                   # 仅测锁等待,不含 remember
                    self._ingest_lock_wait_ms_total += int((time.monotonic() - t0) * 1000)
                self.remember(chunk, holder="self", interlocutor=f"claude-code:{project}")
            (sp / "done").mkdir(exist_ok=True)
            claimed.rename(sp / "done" / job_path.name)
        except Exception as exc:                   # noqa: BLE001
            msg = str(exc).lower()
            transient = any(k in msg for k in
                            ("timeout", "transport", "ssl", "connect", "temporarily"))
            if transient:
                claimed.rename(job_path)            # 留 spool,下轮重扫自动重试
            else:
                (sp / "failed").mkdir(exist_ok=True)
                claimed.rename(sp / "failed" / job_path.name)
                (sp / "failed" / (job_path.name + ".error")).write_text(str(exc)[:1000])
        return True

    def start_ingest_worker(self, poll_interval_s: float = 2.0) -> None:
        if self._ingest_thread is not None:
            return
        stop = threading.Event()
        def _loop() -> None:
            while not stop.wait(poll_interval_s):
                try:
                    while self._ingest_drain_once():
                        if stop.is_set():
                            break
                except Exception:  # noqa: BLE001 — 保活
                    logger.exception("ingest worker failed")
        self._ingest_stop = stop
        self._ingest_thread = threading.Thread(target=_loop, name="starling-ingest", daemon=True)
        self._ingest_thread.start()

    def stop_ingest_worker(self) -> None:
        if self._ingest_thread is None:
            return
        self._ingest_stop.set()
        self._ingest_thread.join(timeout=5.0)
        self._ingest_thread = None
        self._ingest_stop = None
```

**注意锁纪律**:`remember` 调用在 `with self._lock` 块**之外**——`remember` 自身持锁写,worker 只在埋点那一小段持锁测等待时间。这是 codex 核心修正的落点,`test_worker_does_not_hold_lock_across_remember` 钉死它。

- [ ] **Step 4: `/api/ingest_status` 路由**

`inspect.py` 挨着现有只读路由加:

```python
    @router.get("/ingest_status")
    async def ingest_status(request: Request):
        return _engine(request).ingest_status()
```

（若 inspect.py 的路由用 `_cfg`/`queries` 只读模式而非 `_engine`,则据文件既有模式取 engine;ingest_status 是 engine 方法,需引擎句柄。)

- [ ] **Step 5: lifespan 启/停(独立于 tick + 关停时序)**

`app.py` lifespan:**把 ingest worker 的启动移出 `if config.tick_interval_s > 0`**(codex:tick 关不该禁摄入)——引擎存在即启 ingest worker。关停顺序(codex):`begin_drain()` → `stop_ingest_worker()` → `stop_background_tick()`。均 `hasattr` 探测。

- [ ] **Step 6: 全量 pytest + Commit**

Run: `.venv/bin/python -m pytest tests/python -q 2>&1 | tail -3`(全绿)。

```bash
git add python/starling/dashboard/engine.py python/starling/dashboard/routes/inspect.py python/starling/dashboard/app.py python/starling/dashboard/ingest_filter.py tests/python/test_dashboard_ingest_worker.py
git commit -m "feat(dashboard): spool ingest worker (no outer lock, dead-letter, transient-retry, status route)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: SessionEnd hook 安装 + e2e dogfood(手动,非 CI 门)

**Files:**
- Modify: `dashboard/README.md`（hook 配置 + bootstrap 用法）
- Create(ephemeral,不提交):`$CLAUDE_JOB_DIR/tmp/ingest_e2e.py`

- [ ] **Step 1: 装 hook**

`~/.claude/settings.json` 加 SessionEnd hook(command → `.venv/bin/python scripts/ingest_session.py`,timeout 30——但脚本近零工作,不会逼近)。dashboard 由 launchd 常驻。

- [ ] **Step 2: e2e**

造含 thinking/tool/代码围栏的样例 transcript → `.venv/bin/python scripts/ingest_session.py --bootstrap <path>` → 轮询 `GET /api/ingest_status` 看 pending→done → `GET /api/statements` 看 statements 落库 + review_status。

- [ ] **Step 3: 历史 bootstrap 起量 + 记录**

`--bootstrap` 喂 3-5 个真实 `~/.claude/projects/**/*.jsonl`;等 worker 消化;记录:job 数、statements 落库数、`ingest_status.lock_wait_ms_total`(= extraction-出锁 gated 项的干净证据,非「制造争用」)、期间并发打 `/api/tick` 是否秒回(证明不锁死)。进 PR body。

- [ ] **Step 4: Commit README**

```bash
git add dashboard/README.md
git commit -m "docs(ingest): SessionEnd hook setup + bootstrap + spool ops

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:** spec §① hook→Task 2/4;§② 过滤(含代码围栏)→Task 1;§③ spool 写入器→Task 2;§④ worker(不外套锁/瞬态重试/关停/tick 独立)→Task 3;§⑤ review 门→Task 3 复用 remember 默认态;§⑥ 可观测→Task 3 `/api/ingest_status`;§⑦ 锁等待埋点→Task 3。✅
**2. Placeholder scan:** 无 TBD。三处「据实微调」(SessionEnd payload 字段=Task 2 前置查证;interlocutor 列名/remember 失败语义=Task 3 Step 1 注)是标注的实现时查证点 + 给了 fallback。✅
**3. Type consistency:** `clean_turns`/`chunk_dialogue`(移入 `ingest_filter.py`)、`write_job`/`main`、`_ingest_drain_once`/`ingest_status`/`start/stop_ingest_worker` 跨任务一致;spool 路径 `~/.starling/ingest-spool/` 在 script/engine/测试一致。✅

## NOT in scope

- 召回注入新会话(阶段 2,SessionStart additionalContext)。
- 信号仪表化 + 质量 harness(子项 B/C)。
- 真 `pending_review` 前置门(gated,碰内核)。
- extraction 出锁 / query-embed cache(只产信号)。
- 多进程 dashboard(spool claim 用 rename 已防重,但设计假设单 worker)。

## What already exists(复用 vs 重建)

- **`remember`(C++ 核心)**:复用——摄入不重造抽取/幂等/落库。
- **`start_background_tick` 线程范本(engine.py:549)**:复用其 Event+daemon+join 模式。
- **`FakeLLMAdapter.set_delay_ms`**:复用做锁纪律测试的确定性慢 stub。
- **`/statements` 审批 UI(#49)**:复用作隐私事后门。
- **不重建**:v1 曾要建 SQLite 队列表 + /api/ingest 端点——spool 架构删掉,job 文件即队列。

## 失败模式

| 新 codepath | 生产失败 | 有测? | 有错误处理? | 用户可见? |
|---|---|---|---|---|
| hook 写 spool | 磁盘满/权限 | 是(exit0) | exit 0 + log | 静默(会话不受影响) |
| worker 读 transcript | 文件不存在/坏 jsonl | 是 | 坏行跳过 | ingest_status.failed |
| worker remember | LLM 黑洞(Clash) | 是(瞬态留 spool) | 瞬态重试/永久 failed | ingest_status |
| claim rename | 并发抢占 | 是(OSError→下轮) | 捕获 | 无 |

无「静默 + 无测 + 无处理」的关键缺口(codex 的静默丢失被 spool 持久化消除)。

## 并行化

Task 1(过滤纯函数)→ Task 2(spool 写入器,依赖 Task 1 常量)→ Task 3(worker,依赖过滤模块)→ Task 4(e2e,依赖全部)。**基本顺序**:Task 1→2 可同分支连续;Task 3 依赖 Task 1 的 `ingest_filter.py`。无独立并行 lane(同一 script + engine)。Sequential implementation。

## Execution Handoff

superpowers:subagent-driven-development(每任务 implementer+reviewer,最后 whole-branch review),按项目 cadence。然后 PR;CI 绿 + 用户明确合并。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_found→folded | 架构 pivot(spool)+ 17 codex 发现,全部折叠或溶解 |
| Outside Voice | codex | Independent 2nd opinion | 1 | issues_found | spool 架构 + 锁修正 + 12 correctness 修正 |

- **CODEX:** 17 findings。核心 2:(1) POST-from-hook 破「不阻塞退出 + 不静默丢失」→ 采纳 spool-file 架构(用户 D2=A);(2) worker 外套 `_lock` 零收益且锁死 dashboard(remember 自持锁)→ worker 不外套锁 + 埋点测锁等待。其余(去 tenant/unknown 碰撞、代码围栏未剥、测试只查 provenance、tick=0 禁摄入、关停时序、瞬态 vs 永久重试、崩溃恢复、请求上限、spool 隐形)——spool 架构溶解半数,其余折叠进 v2 计划各任务。
- **CROSS-MODEL:** 无分歧(claude 审同意 codex 全部;codex 补了 claude 漏的一致性/时序/过滤缺陷)。
- **IMPLEMENTATION REVIEWS(subagent-driven,per-task implementer+reviewer + fix waves):**
  - Task 1(过滤):真实 transcript 采样抓到 `clean_turns` 只处理 str-user、漏 list 形态 → 丢 14% 真用户轮 + `<tool-result>` 字符串检查死代码 → 修(2ca955e)。
  - Task 3(worker):**opus 两轮严查** → Hazard1 锁旁路 = 单写者 VIOLATION、Hazard2 零语句=失败 WRONG、busy-spin、stranded `.processing`、错 metric → 用户裁定 D3=A(持锁+限流)+ 全修(952a456);顺带修 `RememberResult(**dict)` TickOutcome 式地雷。
  - Whole-branch(controller 亲审,因 2 次 opus 子代理退化返回垃圾/注入):跨任务一致 ✅、架构边界 ✅(host + 唯一 binding-forward extraction_failed、单写者由 self.remember 尊重)、e2e 实测 3 条真记忆落库 + 单写者持锁 37.8s 可测。唯一发现 = 本文「不外套锁」文档漂移 → 已加 v3 amendment 更正。
- **Minor(backlog,非阻塞)**:Task2 malformed-stdin 测试写真 ~/.starling/ingest.log;Task1 其他合成标签漏过;general-fact 的 extraction_failed 被丢弃;poison-job 头阻塞 ~10s;LLMNotConfigured 重试后进 failed/。
- **VERDICT:** READY FOR PR(4 任务 + fix waves 全绿:ctest 949/949、pytest 850;e2e 实测通过)。

NO UNRESOLVED DECISIONS
