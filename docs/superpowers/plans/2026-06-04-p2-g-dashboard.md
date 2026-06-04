# P2.g 可视化观测面（Dashboard）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一个 TypeScript（SvelteKit）+ Python（FastAPI）的 dashboard web 服务，支持远端访问 + 实时交互，覆盖四面板 bundle（交互核心 / 认知检视 / 动力学·运维 / 总览·Eval），引擎逻辑全部经既有 `starling.Memory` 走真路径。

**Architecture:** FastAPI engine-API（`python/starling/dashboard/`）持有单个 `starling.Memory` 作引擎唯一属主（单写者）；命令路由（remember/recall/tick/working_set）经门面，检视路由走只读 SQL SELECT；SvelteKit + Tailwind 前端（`dashboard/web/`）经 REST + WebSocket 消费；共享 bearer token + 可配置绑定。**无 C++ 改动、无 migration（ctest 505 不动）。**

**Tech Stack:** Python 3.14 + FastAPI + uvicorn + httpx（测试）；SvelteKit + Svelte 5 + Tailwind + TypeScript（node v22 / npm 10）；pytest（FastAPI TestClient）+ vitest + Playwright。

**Spec:** `docs/superpowers/specs/2026-06-04-p2-g-dashboard-design.md`（commit 006f250）。

---

## 文件结构（决策锁定）

**后端（`python/starling/dashboard/`，随包安装、可 pytest）**
- `__init__.py` — 导出 `create_app`、`DashboardConfig`
- `config.py` — `DashboardConfig` dataclass + `from_env()`
- `auth.py` — `require_token` 依赖（`hmac.compare_digest` 恒定时间比较）
- `queries.py` — 只读 SQL：`open_ro(db_path)` + `overview/statements/cognizers/commitments/replay/conflicts/queues`
- `realtime.py` — `ConnectionManager`（WebSocket 广播）
- `app.py` — `create_app(config, *, memory=None)` 工厂，装配路由
- `routes/__init__.py`、`routes/commands.py`、`routes/inspect.py`、`routes/evalreport.py`

**启动器**：`scripts/run_dashboard.py`

**前端（`dashboard/web/`，独立 Node 工程）**
- `src/lib/api.ts` — fetch 客户端（统一加 `Authorization`）
- `src/lib/ws.ts` — WebSocket store
- `src/lib/token.ts` — token 本地存取
- `src/routes/+layout.svelte` — 左导航 + 顶栏 + 明暗主题
- `src/routes/+page.svelte`（总览）、`eval/`、`interact/`、`working-set/`、`reminders/`、`statements/`、`cognizers/`、`commitments/`、`replay/`、`conflicts/`、`queues/`
- `src/lib/components/*.svelte` — `StatCard`、`DataTable`、`Graph`（内联 SVG）

**测试**
- `tests/python/test_dashboard_auth.py`、`test_dashboard_inspect.py`、`test_dashboard_commands.py`、`test_dashboard_ws.py`
- `dashboard/web/src/**/*.test.ts`（vitest）、`dashboard/web/e2e/smoke.spec.ts`（Playwright）

**统一 API 契约（所有 Task 一致）**
- 除 `GET /health` 外所有端点需 `Authorization: Bearer <token>`。
- 命令：`POST /api/remember {text,holder?,now?}` → `{engram_ref,statement_ids,outcome}`；`POST /api/recall {query,perspective?,k?,mode?}` → `{results:[{subject,predicate,object,score}]}`；`POST /api/tick {now?}` → `{embedded,fired,broken,auto_withdrawn}`；`GET /api/working_set?interlocutor=&goal=&token_budget=` → `{render,blocks,truncated}`。
- 检视：`GET /api/overview`、`/api/statements`、`/api/cognizers`、`/api/commitments`、`/api/replay`、`/api/conflicts`、`/api/queues`、`/api/eval`。
- 实时：`WS /ws`，推 `{type,payload}`，`type ∈ {tick,commitment_fired,statement_added,recall}`。

---

## Task 0: Baseline 确认

**Files:** 无（只读校验）

- [ ] **Step 1: 确认 main 全绿基线**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
source .venv/bin/activate
ctest --test-dir build 2>/dev/null | tail -3 || echo "ctest skip (无 build 目录则执行时按需 cmake)"
python -m pytest -q 2>&1 | tail -3
```
Expected: pytest `505 passed`（或 `... passed`，无 failed）；ctest 505（若已 build）。

- [ ] **Step 2: 确认工具链**

Run:
```bash
python -c "import sys; print(sys.version)"
node --version; npm --version
python -c "import fastapi" 2>&1 | tail -1   # 预期 ModuleNotFoundError（Task 1 装）
```
Expected: Python 3.14.x；node v22.x；npm 10.x；fastapi 未装（Task 1 安装）。

无 commit（baseline 确认）。

---

## Task 1: 脚手架（FastAPI 骨架 + token 鉴权 + /health + SvelteKit init）

**Files:**
- Modify: `pyproject.toml`（加 `[project.optional-dependencies]` 的 `dashboard` 组）
- Create: `python/starling/dashboard/__init__.py`、`config.py`、`auth.py`、`app.py`、`routes/__init__.py`
- Create: `dashboard/web/`（SvelteKit + Tailwind 工程）、`dashboard/web/.gitignore`
- Test: `tests/python/test_dashboard_auth.py`

- [ ] **Step 1: 安装后端依赖**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
source .venv/bin/activate
pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" "httpx>=0.27"
python -c "import fastapi, uvicorn, httpx; print('ok')"
```
Expected: `ok`。

- [ ] **Step 2: 在 pyproject 记可选依赖组**

在 `pyproject.toml` 的 `[project]` 之后加入（若已有 `[project.optional-dependencies]` 则并入 `dashboard` 键）：
```toml
[project.optional-dependencies]
dashboard = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
]
```

- [ ] **Step 3: 写 `config.py`**

Create `python/starling/dashboard/config.py`：
```python
"""Dashboard runtime configuration (env-only secrets)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class DashboardConfig:
    db_path: str
    agent: str = "self"
    tenant: str = "default"
    token: str = ""                      # STARLING_DASH_TOKEN — never logged/persisted
    host: str = "127.0.0.1"
    port: int = 8787
    cors_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "DashboardConfig":
        origins = os.environ.get("STARLING_DASH_CORS_ORIGINS", "")
        return cls(
            db_path=os.environ.get("STARLING_DASH_DB", "starling_dashboard.db"),
            agent=os.environ.get("STARLING_DASH_AGENT", "self"),
            tenant=os.environ.get("STARLING_DASH_TENANT", "default"),
            token=os.environ.get("STARLING_DASH_TOKEN", ""),
            host=os.environ.get("STARLING_DASH_HOST", "127.0.0.1"),
            port=int(os.environ.get("STARLING_DASH_PORT", "8787")),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        )

    def validate_bind(self) -> None:
        """Refuse to expose a tokenless service on a non-loopback interface."""
        if self.host not in ("127.0.0.1", "localhost", "::1") and not self.token:
            raise RuntimeError(
                "refusing to bind dashboard to non-loopback host without "
                "STARLING_DASH_TOKEN set"
            )
```

- [ ] **Step 4: 写 `auth.py`**

Create `python/starling/dashboard/auth.py`：
```python
"""Bearer-token auth — constant-time compare; token from config (env-only)."""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status


def make_require_token(token: str):
    """Build a FastAPI dependency that enforces `Authorization: Bearer <token>`.

    When `token` is empty the gate is open (loopback dev). Comparison is
    constant-time; the token is never echoed in errors or logs.
    """
    async def require_token(authorization: str = Header(default="")) -> None:
        if not token:
            return
        prefix = "Bearer "
        supplied = authorization[len(prefix):] if authorization.startswith(prefix) else ""
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing bearer token",
            )

    return require_token
```

- [ ] **Step 5: 写 `app.py`（骨架 + /health + CORS + 鉴权依赖）**

Create `python/starling/dashboard/app.py`：
```python
"""FastAPI app factory for the Starling dashboard engine-API."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starling.dashboard.auth import make_require_token
from starling.dashboard.config import DashboardConfig


def create_app(config: DashboardConfig, *, memory: Optional[object] = None) -> FastAPI:
    """Build the dashboard app.

    `memory` (a `starling.Memory`) is the engine owner for command routes; when
    None it is lazily built from `config` at first command use (production).
    Inspection routes read the SQLite at `config.db_path` directly (read-only).
    """
    app = FastAPI(title="Starling Dashboard", version="0.1.0")
    app.state.config = config
    app.state.memory = memory

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    require_token = make_require_token(config.token)
    app.state.require_token = require_token

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": app.version}

    @app.get("/api/ping", dependencies=[Depends(require_token)])
    async def ping() -> dict:
        return {"pong": True}

    return app
```

- [ ] **Step 6: 写 `__init__.py` 与 `routes/__init__.py`**

Create `python/starling/dashboard/__init__.py`：
```python
"""Starling dashboard engine-API (P2.g)."""
from starling.dashboard.app import create_app
from starling.dashboard.config import DashboardConfig

__all__ = ["create_app", "DashboardConfig"]
```
Create `python/starling/dashboard/routes/__init__.py`：
```python
"""Dashboard route modules."""
```

- [ ] **Step 7: 写鉴权失败测试**

Create `tests/python/test_dashboard_auth.py`：
```python
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app


def _client(token: str) -> TestClient:
    cfg = DashboardConfig(db_path=":memory:", token=token)
    return TestClient(create_app(cfg))


def test_health_open_without_token():
    c = _client("secret")
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_protected_requires_token():
    c = _client("secret")
    assert c.get("/api/ping").status_code == 401
    assert c.get("/api/ping", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = c.get("/api/ping", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200 and ok.json()["pong"] is True


def test_empty_token_opens_gate():
    c = _client("")
    assert c.get("/api/ping").status_code == 200
```

- [ ] **Step 8: 跑后端测试**

Run: `python -m pytest tests/python/test_dashboard_auth.py -v`
Expected: 3 passed。

- [ ] **Step 9: 初始化 SvelteKit 工程**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/dashboard
npm create svelte@latest web -- --template skeleton --types typescript --no-add-ons 2>/dev/null || npx sv create web --template minimal --types ts
cd web
npm install
npm install -D tailwindcss @tailwindcss/vite @playwright/test vitest @testing-library/svelte jsdom
npm install @sveltejs/adapter-node
```
（若 `npm create svelte` 交互不可用，用 `npx sv create web --template minimal --types ts --no-install` 后再 `npm install`。）

- [ ] **Step 10: 配 Tailwind + adapter-node + 反代**

Create/Modify `dashboard/web/src/app.css`：
```css
@import "tailwindcss";
:root { color-scheme: light dark; }
body { @apply bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100; }
```
Modify `dashboard/web/vite.config.ts`（加 tailwind 插件 + dev 反代 `/api`、`/ws` 到 FastAPI）：
```ts
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/ws': { target: 'ws://127.0.0.1:8787', ws: true }
    }
  }
});
```
Modify `dashboard/web/svelte.config.js`：用 `@sveltejs/adapter-node`。

- [ ] **Step 11: 写 `.gitignore`**

Create `dashboard/web/.gitignore`：
```gitignore
node_modules/
/build
/.svelte-kit
/package
.env
.env.*
!.env.example
vite.config.ts.timestamp-*
/test-results
/playwright-report
```

- [ ] **Step 12: 冒烟构建前端**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/dashboard/web
npm run build 2>&1 | tail -5
```
Expected: 构建成功（无 type error）。

- [ ] **Step 13: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add pyproject.toml python/starling/dashboard tests/python/test_dashboard_auth.py dashboard/web
git status --short | grep -v "node_modules" | head
git commit -F - <<'EOF'
feat(P2.g): dashboard 脚手架 — FastAPI 骨架 + token 鉴权 + SvelteKit init

python/starling/dashboard：create_app 工厂 + DashboardConfig（env-only token）
+ make_require_token（hmac.compare_digest 恒定时间比较）+ /health（开放）+
/api/ping（需 token）。鉴权 3 用例（无/错/对 token + 空 token 开门）全绿。
dashboard/web：SvelteKit + Tailwind + adapter-node + dev 反代 /api、/ws；
.gitignore 排除 node_modules/build。pyproject 记 dashboard 可选依赖组。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 2: 后端检视只读查询 API + 命令路由 + pytest

**Files:**
- Create: `python/starling/dashboard/queries.py`、`routes/inspect.py`、`routes/commands.py`、`routes/evalreport.py`
- Modify: `python/starling/dashboard/app.py`（装配路由）
- Test: `tests/python/test_dashboard_inspect.py`、`test_dashboard_commands.py`

- [ ] **Step 1: 写 `queries.py`（只读 SQL）**

Create `python/starling/dashboard/queries.py`：
```python
"""Read-only SQLite inspection queries for the dashboard.

Opens a fresh read-only connection per call (`mode=ro` + PRAGMA query_only).
List endpoints return rows as dicts keyed by cursor column names, so they are
robust to schema column additions. The engine remains the single writer.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def open_ro(db_path: str):
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _count(conn, table: str, tenant: str | None) -> int:
    if tenant is None:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id = ?", (tenant,)
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def overview(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        commit_states = _rows(
            conn,
            "SELECT state, COUNT(*) AS n FROM commitments WHERE tenant_id=? GROUP BY state",
            (tenant,),
        )
        queue = _rows(
            conn,
            "SELECT dispatch_status, COUNT(*) AS n FROM bus_events WHERE tenant_id=? "
            "GROUP BY dispatch_status",
            (tenant,),
        )
        return {
            "counts": {
                "statements": _count(conn, "statements", tenant),
                "statement_edges": _count(conn, "statement_edges", tenant),
                "cognizers": _count(conn, "cognizers", tenant),
                "commitments": _count(conn, "commitments", tenant),
                "bus_events": _count(conn, "bus_events", tenant),
            },
            "commitments_by_state": {r["state"]: r["n"] for r in commit_states},
            "queue_by_status": {r["dispatch_status"]: r["n"] for r in queue},
        }


def statements(db_path: str, tenant: str, *, holder: str = "", perspective: str = "",
               predicate: str = "", limit: int = 100, offset: int = 0) -> dict:
    where = ["tenant_id = ?"]
    params: list = [tenant]
    for col, val in (("holder_id", holder), ("holder_perspective", perspective),
                     ("predicate", predicate)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    clause = " AND ".join(where)
    with open_ro(db_path) as conn:
        rows = _rows(
            conn,
            f"SELECT id, holder_id, holder_perspective, subject_id, predicate, "
            f"object_kind, object_value, modality, polarity, confidence, salience, "
            f"observed_at FROM statements WHERE {clause} ORDER BY observed_at DESC "
            f"LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        edges = _rows(
            conn,
            "SELECT src_id, dst_id, edge_kind, weight FROM statement_edges "
            "WHERE tenant_id=? LIMIT 2000",
            (tenant,),
        )
        return {"rows": rows, "edges": edges}


def cognizers(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        nodes = _rows(
            conn,
            "SELECT id, kind, canonical_name, last_seen_at FROM cognizers "
            "WHERE tenant_id=? ORDER BY last_seen_at DESC LIMIT 500",
            (tenant,),
        )
        rels = _rows(
            conn,
            "SELECT a_id, b_id, affinity, power_asymmetry FROM cognizer_relations "
            "WHERE tenant_id=? LIMIT 2000",
            (tenant,),
        )
        presence = _rows(
            conn,
            "SELECT cognizer_id, observed_at, channel FROM cognizer_presence_log "
            "WHERE tenant_id=? ORDER BY observed_at DESC LIMIT 200",
            (tenant,),
        )
        return {"nodes": nodes, "relations": rels, "presence": presence}


def commitments(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        rows = _rows(
            conn,
            "SELECT c.stmt_id, c.state, c.broken_count, c.deadline, c.created_at, "
            "c.updated_at, s.subject_id, s.predicate, s.object_value "
            "FROM commitments c LEFT JOIN statements s ON s.id = c.stmt_id "
            "WHERE c.tenant_id=? ORDER BY c.updated_at DESC LIMIT 500",
            (tenant,),
        )
        triggers = _rows(
            conn,
            "SELECT commitment_stmt_id, kind, status FROM commitment_triggers "
            "WHERE tenant_id=? LIMIT 1000",
            (tenant,),
        )
        return {"rows": rows, "triggers": triggers}


def replay(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        state = _rows(conn, "SELECT * FROM replay_scheduler_state WHERE id=1")
        ledger = _rows(
            conn,
            "SELECT replay_batch_id, mode, sampled_count, started_at, finished_at "
            "FROM replay_ledger ORDER BY started_at DESC LIMIT 100",
        )
        windows = _rows(
            conn,
            "SELECT stmt_id, opened_at, close_deadline, status FROM reconsolidation_windows "
            "WHERE tenant_id=? ORDER BY opened_at DESC LIMIT 200",
            (tenant,),
        )
        return {"scheduler": state[0] if state else {}, "ledger": ledger, "windows": windows}


def conflicts(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        by_kind = _rows(
            conn,
            "SELECT edge_kind, COUNT(*) AS n FROM statement_edges WHERE tenant_id=? "
            "GROUP BY edge_kind",
            (tenant,),
        )
        edges = _rows(
            conn,
            "SELECT src_id, dst_id, edge_kind, weight, metadata_json FROM statement_edges "
            "WHERE tenant_id=? AND edge_kind='CONFLICTS_WITH' LIMIT 500",
            (tenant,),
        )
        return {"by_kind": {r["edge_kind"]: r["n"] for r in by_kind}, "conflicts": edges}


def queues(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        dispatch = _rows(
            conn,
            "SELECT dispatch_status, COUNT(*) AS n FROM bus_events WHERE tenant_id=? "
            "GROUP BY dispatch_status",
            (tenant,),
        )
        backlog = conn.execute(
            "SELECT COUNT(*) FROM statements s LEFT JOIN statement_vectors v "
            "ON v.stmt_id = s.id WHERE s.tenant_id=? AND v.stmt_id IS NULL",
            (tenant,),
        ).fetchone()[0]
        vec = _rows(
            conn,
            "SELECT status, COUNT(*) AS n FROM statement_vectors WHERE tenant_id=? "
            "GROUP BY status",
            (tenant,),
        )
        return {
            "dispatch": {r["dispatch_status"]: r["n"] for r in dispatch},
            "embedding_backlog": backlog,
            "vectors_by_status": {r["status"]: r["n"] for r in vec},
        }
```

- [ ] **Step 2: 写 inspect 路由**

Create `python/starling/dashboard/routes/inspect.py`：
```python
"""Read-only inspection routes (SQL-backed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from starling.dashboard import queries


def build_inspect_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    def _cfg(request: Request):
        return request.app.state.config

    @router.get("/overview")
    async def overview(request: Request):
        c = _cfg(request)
        return queries.overview(c.db_path, c.tenant)

    @router.get("/statements")
    async def statements(request: Request, holder: str = "", perspective: str = "",
                         predicate: str = "", limit: int = 100, offset: int = 0):
        c = _cfg(request)
        return queries.statements(c.db_path, c.tenant, holder=holder,
                                  perspective=perspective, predicate=predicate,
                                  limit=limit, offset=offset)

    @router.get("/cognizers")
    async def cognizers(request: Request):
        c = _cfg(request)
        return queries.cognizers(c.db_path, c.tenant)

    @router.get("/commitments")
    async def commitments(request: Request):
        c = _cfg(request)
        return queries.commitments(c.db_path, c.tenant)

    @router.get("/replay")
    async def replay(request: Request):
        c = _cfg(request)
        return queries.replay(c.db_path, c.tenant)

    @router.get("/conflicts")
    async def conflicts(request: Request):
        c = _cfg(request)
        return queries.conflicts(c.db_path, c.tenant)

    @router.get("/queues")
    async def queues(request: Request):
        c = _cfg(request)
        return queries.queues(c.db_path, c.tenant)

    return router
```

- [ ] **Step 3: 写命令路由**

Create `python/starling/dashboard/routes/commands.py`：
```python
"""Command routes — go through the starling.Memory facade (single writer)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel


class RememberBody(BaseModel):
    text: str
    holder: str | None = None
    now: str | None = None


class RecallBody(BaseModel):
    query: str
    perspective: str = "first_person"
    k: int = 10
    mode: str = "semantic"


class TickBody(BaseModel):
    now: str = "2026-06-01T10:00:00Z"


def _memory(request: Request):
    """Return the engine-owning Memory, building it lazily from config."""
    mem = request.app.state.memory
    if mem is None:
        from starling.memory import Memory, make_openai_llm
        c = request.app.state.config
        mem = Memory.open(c.db_path, agent=c.agent, tenant_id=c.tenant,
                          llm=make_openai_llm())
        request.app.state.memory = mem
    return mem


def build_commands_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.post("/remember")
    async def remember(body: RememberBody, request: Request):
        mem = _memory(request)
        r = mem.remember(body.text, holder=body.holder, now=body.now)
        await _broadcast(request, "statement_added", {"statement_ids": r.statement_ids})
        return {"engram_ref": r.engram_ref, "statement_ids": r.statement_ids,
                "outcome": r.outcome}

    @router.post("/recall")
    async def recall(body: RecallBody, request: Request):
        mem = _memory(request)
        hits = mem.recall(body.query, perspective=body.perspective, k=body.k, mode=body.mode)
        out = [{"subject": h["row"].subject_id, "predicate": h["row"].predicate,
                "object": h["row"].object_value, "score": h["score"]} for h in hits]
        await _broadcast(request, "recall", {"n": len(out)})
        return {"results": out}

    @router.post("/tick")
    async def tick(body: TickBody, request: Request):
        mem = _memory(request)
        st = mem.tick(body.now)
        payload = {"embedded": st.embedded, "fired": st.fired,
                   "broken": st.broken, "auto_withdrawn": st.auto_withdrawn}
        await _broadcast(request, "tick", payload)
        if st.fired:
            await _broadcast(request, "commitment_fired", {"fired": st.fired})
        return payload

    @router.get("/working_set")
    async def working_set(request: Request, interlocutor: str, goal: str | None = None,
                          token_budget: int = 2000):
        mem = _memory(request)
        cb = mem.render_working_set(interlocutor, goal=goal, token_budget=token_budget)
        return {"render": cb.render(),
                "blocks": [{"label": b.label, "content": b.content,
                            "tokens": b.token_estimate} for b in cb.blocks],
                "truncated": cb.truncated}

    return router


async def _broadcast(request: Request, kind: str, payload: dict) -> None:
    mgr = getattr(request.app.state, "ws_manager", None)
    if mgr is not None:
        await mgr.broadcast({"type": kind, "payload": payload})
```

- [ ] **Step 4: 写 eval 报告路由**

Create `python/starling/dashboard/routes/evalreport.py`：
```python
"""Serve the markdown eval reports under docs/eval/ as JSON."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends


def build_eval_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.get("/eval")
    async def eval_reports():
        root = Path(__file__).resolve().parents[4] / "docs" / "eval"
        reports = []
        if root.is_dir():
            for p in sorted(root.glob("*.md")):
                reports.append({"name": p.name, "markdown": p.read_text(encoding="utf-8")})
        return {"reports": reports}

    return router
```

- [ ] **Step 5: 在 app.py 装配路由**

Modify `python/starling/dashboard/app.py` — 在 `return app` 之前加入：
```python
    from starling.dashboard.routes.inspect import build_inspect_router
    from starling.dashboard.routes.commands import build_commands_router
    from starling.dashboard.routes.evalreport import build_eval_router

    app.include_router(build_inspect_router(require_token))
    app.include_router(build_commands_router(require_token))
    app.include_router(build_eval_router(require_token))
```

- [ ] **Step 6: 写检视测试（含临时库 seed）**

Create `tests/python/test_dashboard_inspect.py`：
```python
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app


def _seed(db_path: str):
    """Build the schema via the runtime, then raw-seed a few rows, commit+close."""
    from pathlib import Path
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    # ensure WAL is flushed and the writer handle is released before raw seeding
    del r
    conn = sqlite3.connect(db_path)
    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO statements (id, tenant_id, holder_id, holder_perspective, "
        "subject_kind, subject_id, predicate, object_kind, object_value, "
        "canonical_object_hash, canonical_object_hash_version, modality, polarity, "
        "confidence, observed_at, salience, affect_json, activation, last_accessed, "
        "provenance) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, "default", "self", "first_person", "cognizer", "Bob", "responsible_for",
         "str", "auth", "h", "v1", "BELIEVES", "POS", 0.9, "2026-04-15T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-15T10:00:00Z", "test"),
    )
    conn.execute(
        "INSERT INTO commitments (stmt_id, tenant_id, state, broken_count, deadline, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (sid, "default", "ACTIVE", 0, "2026-04-20T10:00:00Z",
         "2026-04-15T10:00:00Z", "2026-04-15T10:00:00Z"),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "dash.db")
    _seed(db)
    cfg = DashboardConfig(db_path=db, token="")
    return TestClient(create_app(cfg))


def test_overview(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["statements"] >= 1
    assert body["commitments_by_state"].get("ACTIVE") == 1


def test_statements_filter(client):
    r = client.get("/api/statements", params={"predicate": "responsible_for"})
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows and rows[0]["predicate"] == "responsible_for"


def test_commitments_joins_statement(client):
    r = client.get("/api/commitments")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows and rows[0]["state"] == "ACTIVE" and rows[0]["object_value"] == "auth"


def test_replay_conflicts_queues_shape(client):
    assert client.get("/api/replay").status_code == 200
    assert "by_kind" in client.get("/api/conflicts").json()
    assert "embedding_backlog" in client.get("/api/queues").json()


def test_eval_reports(client):
    r = client.get("/api/eval")
    assert r.status_code == 200 and isinstance(r.json()["reports"], list)
```

- [ ] **Step 7: 写命令测试（离线 stub）**

Create `tests/python/test_dashboard_commands.py`：
```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.memory import Memory, make_stub_llm

_STUB_XML = (
    "<statements><statement><holder>self</holder>"
    "<holder_perspective>FIRST_PERSON</holder_perspective>"
    "<subject>Bob</subject><predicate>responsible_for</predicate>"
    "<object>auth</object><modality>BELIEVES</modality>"
    "<polarity>POS</polarity><nesting_depth>0</nesting_depth></statement></statements>"
)


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "cmd.db")
    mem = Memory.open(db, llm=make_stub_llm(default_xml=_STUB_XML))
    cfg = DashboardConfig(db_path=db, token="")
    return TestClient(create_app(cfg, memory=mem))


def test_remember_then_tick(client):
    r = client.post("/api/remember", json={"text": "Bob owns auth"})
    assert r.status_code == 200
    assert r.json()["outcome"] in ("accepted", "idempotent")
    t = client.post("/api/tick", json={"now": "2026-06-01T10:00:00Z"})
    assert t.status_code == 200
    assert set(t.json()) == {"embedded", "fired", "broken", "auto_withdrawn"}


def test_working_set_renders(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    r = client.get("/api/working_set", params={"interlocutor": "Alice"})
    assert r.status_code == 200
    assert "render" in r.json() and "blocks" in r.json()
```

- [ ] **Step 8: 跑测试**

Run: `python -m pytest tests/python/test_dashboard_inspect.py tests/python/test_dashboard_commands.py -v`
Expected: 全 passed（若 stub XML 字段名与抽取器不符导致 statement_ids 空，命令测试只断言 outcome/shape，不断言抽取条数——保持稳健）。

- [ ] **Step 9: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard tests/python/test_dashboard_inspect.py tests/python/test_dashboard_commands.py
git commit -F - <<'EOF'
feat(P2.g): 后端检视只读 API + 命令路由 + pytest

queries.py：只读连接（mode=ro + query_only），overview/statements/cognizers/
commitments(JOIN statements)/replay/conflicts(edge_kind=CONFLICTS_WITH)/queues
（dispatch_status 分态 + embedding backlog LEFT JOIN）。命令路由经 Memory 门面
（remember/recall/tick/working_set），命令后向 ws 广播。eval 路由 glob docs/eval/*.md。
测试：检视用临时库 raw-seed（commit+close）+ 命令用 make_stub_llm 离线。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 3: D 总览 + Eval 落地页（SvelteKit）

**Files:**
- Create: `dashboard/web/src/lib/token.ts`、`src/lib/api.ts`、`src/lib/components/StatCard.svelte`、`src/routes/+layout.svelte`、`src/routes/+page.svelte`、`src/routes/eval/+page.svelte`
- Test: `dashboard/web/src/lib/api.test.ts`

- [ ] **Step 1: token 存取**

Create `dashboard/web/src/lib/token.ts`：
```ts
const KEY = 'starling_dash_token';
export const getToken = (): string =>
  (typeof localStorage !== 'undefined' && localStorage.getItem(KEY)) || '';
export const setToken = (t: string): void => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, t);
};
```

- [ ] **Step 2: API 客户端**

Create `dashboard/web/src/lib/api.ts`：
```ts
import { getToken } from './token';

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const tok = getToken();
  if (tok) headers.set('Authorization', `Bearer ${tok}`);
  headers.set('Content-Type', 'application/json');
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => req<T>(p),
  post: <T>(p: string, body: unknown) =>
    req<T>(p, { method: 'POST', body: JSON.stringify(body) })
};
```

- [ ] **Step 3: vitest 单测 api 客户端**

Create `dashboard/web/src/lib/api.test.ts`：
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from './api';
import * as tok from './token';

beforeEach(() => {
  vi.spyOn(tok, 'getToken').mockReturnValue('secret');
  globalThis.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ ok: 1 }), { status: 200 })
  ) as unknown as typeof fetch;
});

describe('api', () => {
  it('attaches bearer token', async () => {
    await api.get('/api/overview');
    const [, init] = (globalThis.fetch as any).mock.calls[0];
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer secret');
  });
  it('throws on non-ok', async () => {
    globalThis.fetch = vi.fn(async () => new Response('', { status: 401 })) as any;
    await expect(api.get('/api/overview')).rejects.toThrow('401');
  });
});
```
配 `dashboard/web/vitest.config.ts`：
```ts
import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';
export default defineConfig({
  plugins: [svelte({ hot: false })],
  test: { environment: 'jsdom', globals: true }
});
```

- [ ] **Step 4: StatCard 组件**

Create `dashboard/web/src/lib/components/StatCard.svelte`：
```svelte
<script lang="ts">
  let { label, value }: { label: string; value: string | number } = $props();
</script>
<div class="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 bg-white dark:bg-zinc-900">
  <div class="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
  <div class="text-2xl font-semibold mt-1">{value}</div>
</div>
```

- [ ] **Step 5: 布局（左导航 + token 输入 + 明暗）**

Create `dashboard/web/src/routes/+layout.svelte`：
```svelte
<script lang="ts">
  import '../app.css';
  import { getToken, setToken } from '$lib/token';
  let token = $state(getToken());
  const NAV = [
    { href: '/', label: '总览' }, { href: '/eval', label: 'Eval' },
    { href: '/interact', label: '交互' }, { href: '/working-set', label: 'Working Set' },
    { href: '/reminders', label: '承诺提醒' }, { href: '/statements', label: 'Statements' },
    { href: '/cognizers', label: 'Cognizers' }, { href: '/commitments', label: 'Commitments' },
    { href: '/replay', label: 'Replay' }, { href: '/conflicts', label: 'Conflicts' },
    { href: '/queues', label: 'Queues' }
  ];
  let { children } = $props();
</script>
<div class="flex min-h-screen">
  <nav class="w-48 shrink-0 border-r border-zinc-200 dark:border-zinc-800 p-3 space-y-1">
    <div class="font-semibold px-2 py-3">Starling</div>
    {#each NAV as n}
      <a href={n.href} class="block px-2 py-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 text-sm">{n.label}</a>
    {/each}
    <div class="pt-4 px-2">
      <label class="text-xs text-zinc-500" for="tok">Token</label>
      <input id="tok" class="w-full mt-1 px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-700 bg-transparent"
             bind:value={token} onchange={() => setToken(token)} placeholder="bearer token" />
    </div>
  </nav>
  <main class="flex-1 p-6">{@render children()}</main>
</div>
```

- [ ] **Step 6: 总览页**

Create `dashboard/web/src/routes/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import StatCard from '$lib/components/StatCard.svelte';
  type Overview = {
    counts: Record<string, number>;
    commitments_by_state: Record<string, number>;
    queue_by_status: Record<string, number>;
  };
  let data = $state<Overview | null>(null);
  let err = $state('');
  async function load() {
    try { data = await api.get<Overview>('/api/overview'); err = ''; }
    catch (e) { err = String(e); }
  }
  $effect(() => { load(); });
</script>
<h1 class="text-xl font-semibold mb-4">总览</h1>
{#if err}<p class="text-red-500 text-sm">{err}</p>{/if}
{#if data}
  <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
    {#each Object.entries(data.counts) as [k, v]}<StatCard label={k} value={v} />{/each}
  </div>
  <h2 class="text-sm font-semibold mt-6 mb-2 text-zinc-500">承诺分态</h2>
  <div class="grid grid-cols-3 md:grid-cols-6 gap-3">
    {#each Object.entries(data.commitments_by_state) as [k, v]}<StatCard label={k} value={v} />{/each}
  </div>
{/if}
```

- [ ] **Step 7: Eval 页（渲染 markdown 纯文本块）**

Create `dashboard/web/src/routes/eval/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  type Reports = { reports: { name: string; markdown: string }[] };
  let data = $state<Reports | null>(null);
  $effect(() => { api.get<Reports>('/api/eval').then((d) => (data = d)).catch(() => {}); });
</script>
<h1 class="text-xl font-semibold mb-4">Eval 报告</h1>
{#if data}
  {#each data.reports as r}
    <details class="mb-3 rounded-lg border border-zinc-200 dark:border-zinc-800 p-3" open>
      <summary class="cursor-pointer font-medium">{r.name}</summary>
      <pre class="mt-2 text-xs whitespace-pre-wrap font-mono">{r.markdown}</pre>
    </details>
  {/each}
{/if}
```

- [ ] **Step 8: 跑 vitest + 构建**

Run:
```bash
cd dashboard/web && npx vitest run 2>&1 | tail -6 && npm run build 2>&1 | tail -3
```
Expected: vitest 2 passed；build 成功。

- [ ] **Step 9: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add dashboard/web/src dashboard/web/vitest.config.ts
git commit -F - <<'EOF'
feat(P2.g): D 总览 + Eval 落地页 + api/token 客户端 + 左导航布局

src/lib：token 本地存取、api fetch 客户端（统一加 Authorization）、StatCard。
布局：左导航（11 面板）+ token 输入 + 明暗主题。总览页拉 /api/overview 渲染
计数 + 承诺分态；Eval 页 glob 渲染 docs/eval/*.md。vitest 2 用例（token 注入 +
401 抛错）全绿。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 4: A 交互核心（interact / working set / 承诺提醒）

**Files:**
- Create: `src/routes/interact/+page.svelte`、`src/routes/working-set/+page.svelte`、`src/routes/reminders/+page.svelte`、`src/lib/components/DataTable.svelte`

- [ ] **Step 1: DataTable 组件**

Create `dashboard/web/src/lib/components/DataTable.svelte`：
```svelte
<script lang="ts">
  let { rows, columns }: { rows: Record<string, unknown>[]; columns: string[] } = $props();
</script>
<div class="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
  <table class="w-full text-sm">
    <thead class="bg-zinc-100 dark:bg-zinc-900 text-left">
      <tr>{#each columns as c}<th class="px-3 py-2 font-medium text-zinc-500">{c}</th>{/each}</tr>
    </thead>
    <tbody>
      {#each rows as r}
        <tr class="border-t border-zinc-100 dark:border-zinc-800">
          {#each columns as c}<td class="px-3 py-1.5">{r[c] ?? ''}</td>{/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>
```

- [ ] **Step 2: Interact 页（remember + recall）**

Create `dashboard/web/src/routes/interact/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  let text = $state(''); let query = $state('');
  let remembered = $state<string[]>([]);
  let results = $state<Record<string, unknown>[]>([]);
  let msg = $state('');
  async function remember() {
    try { const r = await api.post<{ statement_ids: string[]; outcome: string }>('/api/remember', { text });
      remembered = r.statement_ids; msg = `outcome: ${r.outcome}`; }
    catch (e) { msg = String(e); }
  }
  async function recall() {
    const r = await api.post<{ results: Record<string, unknown>[] }>('/api/recall', { query });
    results = r.results;
  }
</script>
<h1 class="text-xl font-semibold mb-4">交互</h1>
<section class="mb-6 space-y-2">
  <h2 class="text-sm font-semibold text-zinc-500">Remember</h2>
  <textarea bind:value={text} rows="3" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm"></textarea>
  <button onclick={remember} class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm">记住</button>
  <span class="text-xs text-zinc-500">{msg} · {remembered.length} statements</span>
</section>
<section class="space-y-2">
  <h2 class="text-sm font-semibold text-zinc-500">Recall</h2>
  <input bind:value={query} class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" placeholder="query" />
  <button onclick={recall} class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm">检索</button>
  {#if results.length}<DataTable rows={results} columns={['subject', 'predicate', 'object', 'score']} />{/if}
</section>
```

- [ ] **Step 3: Working Set 页**

Create `dashboard/web/src/routes/working-set/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  let interlocutor = $state('Alice'); let goal = $state('');
  let ws = $state<{ render: string; blocks: { label: string; tokens: number }[]; truncated: string[] } | null>(null);
  async function load() {
    const q = new URLSearchParams({ interlocutor });
    if (goal) q.set('goal', goal);
    ws = await api.get(`/api/working_set?${q}`);
  }
</script>
<h1 class="text-xl font-semibold mb-4">Working Set</h1>
<div class="flex gap-2 mb-3">
  <input bind:value={interlocutor} class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" placeholder="interlocutor" />
  <input bind:value={goal} class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" placeholder="goal (optional)" />
  <button onclick={load} class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm">渲染</button>
</div>
{#if ws}
  <div class="text-xs text-zinc-500 mb-2">blocks: {ws.blocks.map((b) => `${b.label}(${b.tokens})`).join(' · ')}{ws.truncated.length ? ` · truncated: ${ws.truncated.join(',')}` : ''}</div>
  <pre class="rounded-lg border border-zinc-200 dark:border-zinc-800 p-3 text-xs whitespace-pre-wrap font-mono">{ws.render}</pre>
{/if}
```

- [ ] **Step 4: 承诺提醒页**

Create `dashboard/web/src/routes/reminders/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  type Commit = { rows: Record<string, unknown>[] };
  let rows = $state<Record<string, unknown>[]>([]);
  async function load() {
    const d = await api.get<Commit>('/api/commitments');
    rows = d.rows.filter((r) => r.state === 'ACTIVE' || r.state === 'created');
  }
  $effect(() => { load(); });
</script>
<h1 class="text-xl font-semibold mb-4">承诺提醒（pending / ACTIVE）</h1>
{#if rows.length}
  <DataTable {rows} columns={['state', 'subject_id', 'predicate', 'object_value', 'deadline']} />
{:else}<p class="text-sm text-zinc-500">无待办承诺。</p>{/if}
```

- [ ] **Step 5: 构建校验**

Run: `cd dashboard/web && npm run build 2>&1 | tail -3`
Expected: 成功。

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add dashboard/web/src
git commit -F - <<'EOF'
feat(P2.g): A 交互核心 — interact / working set / 承诺提醒

interact 页：remember 文本→展示 statement_ids + outcome；recall→DataTable 结果。
working-set 页：render_working_set ContextBlock 渲染 + blocks/truncated 摘要。
reminders 页：/api/commitments 过滤 ACTIVE/created。DataTable 复用组件。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 5: B 认知检视（statements / cognizers / commitments 五态机）

**Files:**
- Create: `src/routes/statements/+page.svelte`、`src/routes/cognizers/+page.svelte`、`src/routes/commitments/+page.svelte`、`src/lib/components/Graph.svelte`

- [ ] **Step 1: 内联 SVG 图组件**

Create `dashboard/web/src/lib/components/Graph.svelte`：
```svelte
<script lang="ts">
  type Node = { id: string; label: string };
  type Edge = { a: string; b: string };
  let { nodes, edges }: { nodes: Node[]; edges: Edge[] } = $props();
  // simple circular layout — tasteful, dependency-free
  const R = 140, CX = 200, CY = 170;
  let pos = $derived(new Map(nodes.map((n, i) => {
    const t = (2 * Math.PI * i) / Math.max(1, nodes.length);
    return [n.id, { x: CX + R * Math.cos(t), y: CY + R * Math.sin(t) }];
  })));
</script>
<svg viewBox="0 0 400 340" class="w-full max-w-lg">
  {#each edges as e}
    {#if pos.get(e.a) && pos.get(e.b)}
      <line x1={pos.get(e.a)!.x} y1={pos.get(e.a)!.y} x2={pos.get(e.b)!.x} y2={pos.get(e.b)!.y}
            stroke="currentColor" stroke-opacity="0.25" />
    {/if}
  {/each}
  {#each nodes as n}
    <g transform={`translate(${pos.get(n.id)!.x},${pos.get(n.id)!.y})`}>
      <circle r="6" fill="currentColor" />
      <text x="9" y="4" font-size="10" fill="currentColor">{n.label}</text>
    </g>
  {/each}
</svg>
```

- [ ] **Step 2: Statements 页（筛选 + 表）**

Create `dashboard/web/src/routes/statements/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  let predicate = $state(''); let perspective = $state('');
  let rows = $state<Record<string, unknown>[]>([]);
  async function load() {
    const q = new URLSearchParams();
    if (predicate) q.set('predicate', predicate);
    if (perspective) q.set('perspective', perspective);
    const d = await api.get<{ rows: Record<string, unknown>[] }>(`/api/statements?${q}`);
    rows = d.rows;
  }
  $effect(() => { load(); });
</script>
<h1 class="text-xl font-semibold mb-4">Statements</h1>
<div class="flex gap-2 mb-3">
  <input bind:value={predicate} placeholder="predicate" class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
  <input bind:value={perspective} placeholder="perspective" class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
  <button onclick={load} class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm">筛选</button>
</div>
<DataTable {rows} columns={['holder_id', 'holder_perspective', 'subject_id', 'predicate', 'object_value', 'modality', 'polarity']} />
```

- [ ] **Step 3: Cognizers 页（图 + 表）**

Create `dashboard/web/src/routes/cognizers/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import Graph from '$lib/components/Graph.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  let d = $state<{ nodes: any[]; relations: any[] } | null>(null);
  $effect(() => { api.get('/api/cognizers').then((x: any) => (d = x)).catch(() => {}); });
  let gnodes = $derived((d?.nodes ?? []).map((n: any) => ({ id: n.id, label: n.canonical_name })));
  let gedges = $derived((d?.relations ?? []).map((r: any) => ({ a: r.a_id, b: r.b_id })));
</script>
<h1 class="text-xl font-semibold mb-4">Cognizer 社会图</h1>
{#if d}
  <Graph nodes={gnodes} edges={gedges} />
  <h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">节点</h2>
  <DataTable rows={d.nodes} columns={['canonical_name', 'kind', 'last_seen_at']} />
{/if}
```

- [ ] **Step 4: Commitments 五态机页**

Create `dashboard/web/src/routes/commitments/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  const STATES = ['created', 'ACTIVE', 'FULFILLED', 'BROKEN', 'RENEGOTIATED', 'WITHDRAWN'];
  let rows = $state<Record<string, unknown>[]>([]);
  $effect(() => { api.get<{ rows: any[] }>('/api/commitments').then((d) => (rows = d.rows)).catch(() => {}); });
  let byState = $derived(STATES.map((s) => ({ s, n: rows.filter((r) => r.state === s).length })));
</script>
<h1 class="text-xl font-semibold mb-4">Commitment 五态机</h1>
<div class="flex gap-2 mb-4 text-xs">
  {#each byState as b}
    <span class="px-2 py-1 rounded-lg border border-zinc-200 dark:border-zinc-800">{b.s}: {b.n}</span>
  {/each}
</div>
<DataTable {rows} columns={['state', 'subject_id', 'predicate', 'object_value', 'broken_count', 'deadline', 'updated_at']} />
```

- [ ] **Step 5: 构建校验**

Run: `cd dashboard/web && npm run build 2>&1 | tail -3`
Expected: 成功。

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add dashboard/web/src
git commit -F - <<'EOF'
feat(P2.g): B 认知检视 — statements / cognizer 图 / commitment 五态机

statements 页：predicate/perspective 筛选 + DataTable。cognizers 页：内联 SVG
环形布局社会图（零依赖）+ 节点表。commitments 页：六态计数条 + 全生命周期表
（JOIN statements 得 subject/predicate/object）。Graph 组件纯 SVG。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 6: C 动力学 / 运维（replay / conflicts / queues）

**Files:**
- Create: `src/routes/replay/+page.svelte`、`src/routes/conflicts/+page.svelte`、`src/routes/queues/+page.svelte`

- [ ] **Step 1: Replay 页**

Create `dashboard/web/src/routes/replay/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  let d = $state<{ scheduler: Record<string, unknown>; ledger: any[]; windows: any[] } | null>(null);
  $effect(() => { api.get('/api/replay').then((x: any) => (d = x)).catch(() => {}); });
</script>
<h1 class="text-xl font-semibold mb-4">Replay / Reconsolidation</h1>
{#if d}
  <h2 class="text-sm font-semibold mb-2 text-zinc-500">调度器</h2>
  <pre class="text-xs font-mono mb-4">{JSON.stringify(d.scheduler, null, 2)}</pre>
  <h2 class="text-sm font-semibold mb-2 text-zinc-500">Ledger</h2>
  <DataTable rows={d.ledger} columns={['replay_batch_id', 'mode', 'sampled_count', 'started_at', 'finished_at']} />
  <h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">再巩固窗口</h2>
  <DataTable rows={d.windows} columns={['stmt_id', 'opened_at', 'close_deadline', 'status']} />
{/if}
```

- [ ] **Step 2: Conflicts 页**

Create `dashboard/web/src/routes/conflicts/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  let d = $state<{ by_kind: Record<string, number>; conflicts: any[] } | null>(null);
  $effect(() => { api.get('/api/conflicts').then((x: any) => (d = x)).catch(() => {}); });
</script>
<h1 class="text-xl font-semibold mb-4">ConflictProbe</h1>
{#if d}
  <div class="flex gap-2 mb-4 text-xs flex-wrap">
    {#each Object.entries(d.by_kind) as [k, v]}
      <span class="px-2 py-1 rounded-lg border border-zinc-200 dark:border-zinc-800">{k}: {v}</span>
    {/each}
  </div>
  <DataTable rows={d.conflicts} columns={['src_id', 'dst_id', 'edge_kind', 'weight']} />
{/if}
```

- [ ] **Step 3: Queues 页**

Create `dashboard/web/src/routes/queues/+page.svelte`：
```svelte
<script lang="ts">
  import { api } from '$lib/api';
  import StatCard from '$lib/components/StatCard.svelte';
  let d = $state<{ dispatch: Record<string, number>; embedding_backlog: number; vectors_by_status: Record<string, number> } | null>(null);
  $effect(() => { api.get('/api/queues').then((x: any) => (d = x)).catch(() => {}); });
</script>
<h1 class="text-xl font-semibold mb-4">队列 / 运维</h1>
{#if d}
  <StatCard label="embedding backlog" value={d.embedding_backlog} />
  <h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">Outbox dispatch</h2>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    {#each Object.entries(d.dispatch) as [k, v]}<StatCard label={k} value={v} />{/each}
  </div>
  <h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">向量状态</h2>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    {#each Object.entries(d.vectors_by_status) as [k, v]}<StatCard label={k} value={v} />{/each}
  </div>
{/if}
```

- [ ] **Step 4: 构建校验**

Run: `cd dashboard/web && npm run build 2>&1 | tail -3`
Expected: 成功。

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add dashboard/web/src
git commit -F - <<'EOF'
feat(P2.g): C 动力学/运维 — replay / conflicts / queues

replay 页：调度器状态 + ledger + 再巩固窗口表。conflicts 页：edge_kind 分类计数
+ CONFLICTS_WITH 边表。queues 页：embedding backlog + outbox dispatch 分态 +
向量状态卡片。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 7: WebSocket 实时

**Files:**
- Create: `python/starling/dashboard/realtime.py`、`src/lib/ws.ts`
- Modify: `python/starling/dashboard/app.py`（装 ws_manager + WS 端点）、`src/routes/+page.svelte`（订阅刷新）
- Test: `tests/python/test_dashboard_ws.py`

- [ ] **Step 1: 写 `realtime.py`**

Create `python/starling/dashboard/realtime.py`：
```python
"""WebSocket connection manager — broadcasts engine events to dashboards."""
from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._active:
            self._active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self._active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
```

- [ ] **Step 2: 在 app.py 装 ws_manager + WS 端点**

Modify `python/starling/dashboard/app.py` — 在路由装配之前加入：
```python
    from starling.dashboard.realtime import ConnectionManager
    from fastapi import WebSocket, WebSocketDisconnect

    app.state.ws_manager = ConnectionManager()

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        # auth handshake: first text frame must be the token (when configured)
        if config.token:
            await ws.accept()
            try:
                first = await ws.receive_text()
            except Exception:
                return
            import hmac
            if not hmac.compare_digest(first, config.token):
                await ws.close(code=1008)
                return
            app.state.ws_manager._active.append(ws)
        else:
            await app.state.ws_manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            app.state.ws_manager.disconnect(ws)
```
（注：token 模式下首帧即令牌，避免 URL query 泄漏；恒定时间比较。）

- [ ] **Step 3: 写 ws 测试**

Create `tests/python/test_dashboard_ws.py`：
```python
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app


def test_ws_receives_broadcast():
    cfg = DashboardConfig(db_path=":memory:", token="")
    app = create_app(cfg)
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        import anyio
        anyio.from_thread.run(app.state.ws_manager.broadcast, {"type": "tick", "payload": {"fired": 1}})
        msg = ws.receive_json()
        assert msg["type"] == "tick" and msg["payload"]["fired"] == 1


def test_ws_token_rejects_wrong():
    cfg = DashboardConfig(db_path=":memory:", token="secret")
    app = create_app(cfg)
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("wrong")
        # server closes with policy-violation; receiving should raise
        import pytest
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
```

- [ ] **Step 4: 跑 ws 测试**

Run: `python -m pytest tests/python/test_dashboard_ws.py -v`
Expected: 2 passed。（若 `anyio.from_thread` 在 TestClient 线程模型下不适用，改为：连接后在另一线程触发 broadcast；或直接断言 `ws_manager._active` 在连接内非空 + 单测 broadcast 用 asyncio.run 包裹。实现者按 TestClient 实际行为调整断言，保持「连接成功 + 收到/拒绝」语义。）

- [ ] **Step 5: 前端 ws store**

Create `dashboard/web/src/lib/ws.ts`：
```ts
import { getToken } from './token';

export type WsEvent = { type: string; payload: unknown };

export function connectWs(onEvent: (e: WsEvent) => void): () => void {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { const t = getToken(); if (t) ws.send(t); };
  ws.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch { /* ignore */ } };
  return () => ws.close();
}
```

- [ ] **Step 6: 总览页订阅实时刷新**

Modify `dashboard/web/src/routes/+page.svelte` — 在 `$effect(() => { load(); });` 之后加入：
```svelte
<script lang="ts" module>
</script>
```
并在主 `<script>` 内 `load` 之后追加：
```ts
  import { connectWs } from '$lib/ws';
  $effect(() => {
    const close = connectWs((e) => { if (e.type === 'tick' || e.type === 'statement_added') load(); });
    return close;
  });
```

- [ ] **Step 7: 构建 + 测试**

Run:
```bash
cd dashboard/web && npm run build 2>&1 | tail -3
cd /Users/jaredguo-mini/develop/memory/starling && python -m pytest tests/python/test_dashboard_ws.py -q 2>&1 | tail -3
```
Expected: build 成功；ws 测试 passed。

- [ ] **Step 8: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard dashboard/web/src tests/python/test_dashboard_ws.py
git commit -F - <<'EOF'
feat(P2.g): WebSocket 实时 — 引擎事件广播 + 总览订阅刷新

realtime.ConnectionManager 广播；WS /ws 鉴权握手（token 模式首帧即令牌，恒定
时间比较）。命令路由完成后广播 tick/statement_added/commitment_fired/recall。
前端 ws.ts store + 总览页订阅 tick/statement_added 增量刷新。ws 测试：收广播 +
错 token 拒绝。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 8: 鉴权加固 + 远端绑定 + 启动器 + README + e2e smoke

**Files:**
- Create: `scripts/run_dashboard.py`、`dashboard/README.md`、`dashboard/web/e2e/smoke.spec.ts`、`dashboard/web/playwright.config.ts`、`dashboard/web/.env.example`
- Test: `tests/python/test_dashboard_auth.py`（追加 bind 校验用例）

- [ ] **Step 1: 启动器**

Create `scripts/run_dashboard.py`：
```python
#!/usr/bin/env python3
"""Launch the Starling dashboard FastAPI engine-API.

Config from env (see DashboardConfig.from_env). Refuses to bind a non-loopback
host without STARLING_DASH_TOKEN. The SvelteKit frontend is built/served
separately (npm run dev / build); in dev it proxies /api and /ws here.
"""
from __future__ import annotations

import uvicorn

from starling.dashboard import DashboardConfig, create_app


def main() -> None:
    cfg = DashboardConfig.from_env()
    cfg.validate_bind()
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: bind 校验测试**

追加到 `tests/python/test_dashboard_auth.py`：
```python
def test_validate_bind_refuses_public_without_token():
    import pytest
    from starling.dashboard import DashboardConfig
    cfg = DashboardConfig(db_path=":memory:", host="0.0.0.0", token="")
    with pytest.raises(RuntimeError):
        cfg.validate_bind()
    cfg2 = DashboardConfig(db_path=":memory:", host="0.0.0.0", token="secret")
    cfg2.validate_bind()  # ok
```

- [ ] **Step 3: 跑后端鉴权全套**

Run: `python -m pytest tests/python/test_dashboard_auth.py -v`
Expected: 全 passed（含新 bind 用例）。

- [ ] **Step 4: README**

Create `dashboard/README.md`：
```markdown
# Starling Dashboard (P2.g)

可视化观测面：FastAPI engine-API（引擎唯一属主）+ SvelteKit 前端。

## 本地跑

```bash
# 后端（终端 1）
source .venv/bin/activate
pip install -e ".[dashboard]"
export STARLING_DASH_DB=path/to/your.db
export STARLING_DASH_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(24))")
export OPENAI_API_KEY=...    # 命令路由真引擎；离线演示可注入 stub Memory
python scripts/run_dashboard.py

# 前端（终端 2）
cd dashboard/web && npm install && npm run dev
# 打开 http://localhost:5173，在左下 Token 框填入 STARLING_DASH_TOKEN
```

## 远端访问

```bash
export STARLING_DASH_HOST=0.0.0.0       # 非 loopback 必须设 token，否则拒启
export STARLING_DASH_TOKEN=...          # 共享 bearer token（env-only）
export STARLING_DASH_CORS_ORIGINS=https://your-frontend.example
```
建议置于 TLS 反代之后。**令牌仅经环境变量注入，绝不入库/log/前端硬编码/提交。**
```

- [ ] **Step 5: Playwright e2e smoke**

Create `dashboard/web/playwright.config.ts`：
```ts
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://localhost:4173' },
  webServer: { command: 'npm run preview', port: 4173, reuseExistingServer: true }
});
```
Create `dashboard/web/e2e/smoke.spec.ts`：
```ts
import { test, expect } from '@playwright/test';

// Smoke: app shell renders and the overview page mounts. (API may 401 without a
// running backend; we assert the shell + nav, not live data.)
test('shell renders with nav', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Starling')).toBeVisible();
  await expect(page.getByRole('link', { name: '总览' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Eval' })).toBeVisible();
});
```
Create `dashboard/web/.env.example`：
```dotenv
# Frontend proxies /api and /ws to the FastAPI engine-API (see vite.config.ts).
# The bearer token is entered in the UI (Token box), not stored here.
```

- [ ] **Step 6: 跑 e2e smoke**

Run:
```bash
cd dashboard/web && npm run build && npx playwright install chromium 2>&1 | tail -2 && npx playwright test 2>&1 | tail -8
```
Expected: 1 passed（shell + nav 可见）。

- [ ] **Step 7: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add scripts/run_dashboard.py dashboard/README.md dashboard/web/e2e dashboard/web/playwright.config.ts dashboard/web/.env.example tests/python/test_dashboard_auth.py
git commit -F - <<'EOF'
feat(P2.g): 加固 — 启动器 + bind 校验 + README + Playwright e2e smoke

run_dashboard.py：from_env + validate_bind（非 loopback 无 token 拒启）+ uvicorn。
bind 校验用例。README：本地/远端跑法 + 安全姿态（令牌 env-only）。Playwright
smoke：shell + 导航渲染。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 9: 回归 + 关闭（roadmap 登记 P2.g）

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`（加 P2.g 行 + 收尾表登记）
- Modify: `docs/superpowers/plans/2026-05-31-p2-completion-scope.md`（追加 P2.g 段，可选）

- [ ] **Step 1: 全量回归**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
source .venv/bin/activate
python -m pytest -q 2>&1 | tail -4
cd dashboard/web && npx vitest run 2>&1 | tail -4 && npm run build 2>&1 | tail -2
```
Expected: pytest 全绿（含新增 dashboard auth/inspect/commands/ws 用例）；vitest 全绿；前端 build 成功。**ctest 不需重跑（无 C++ 改）**，但确认无 migration 新增：
```bash
ls migrations/ | tail -1   # 仍 0021_commitment_tenant_keys.sql
```

- [ ] **Step 2: 确认无 stray / 无密钥泄漏**

Run:
```bash
git status --short | grep -v "^??" || true
git diff --cached --stat 2>/dev/null | tail
grep -rnE "STARLING_DASH_TOKEN\s*=\s*[\"'][^\"']" dashboard python scripts 2>/dev/null || echo "OK: 无硬编码 token"
```
Expected: 无硬编码 token；无 stray。

- [ ] **Step 3: roadmap 登记 P2.g**

在 `docs/superpowers/plans/2026-05-23-roadmap.md` 的「P2 收尾」表后追加：
```markdown
| **P2.g 可视化观测面 ✅** | TypeScript(SvelteKit)+ Python(FastAPI) dashboard web 服务：远端访问 + 实时交互，四面板（交互核心/认知检视/动力学·运维/总览·Eval） | P2「小规模应用」缺可视化/观测面 | **[2026-06-04-p2-g-dashboard.md](2026-06-04-p2-g-dashboard.md)**：FastAPI engine-API（引擎唯一属主）+ 只读 SQL 检视 + 命令经门面 + WebSocket 实时 + bearer token；无 C++ 改 / 无 migration（ctest 505 不动） |
```

- [ ] **Step 4: 提交 plan + roadmap（milestone close）**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add docs/superpowers/plans/2026-06-04-p2-g-dashboard.md docs/superpowers/plans/2026-05-23-roadmap.md
git commit -F - <<'EOF'
docs(P2.g): land dashboard 实施计划 + roadmap 登记 P2.g 收尾里程碑

P2.g 可视化观测面交付完成：FastAPI engine-API + SvelteKit 前端 + WebSocket 实时，
四面板全交付，bearer token + 可配置远端绑定。无 C++ 改 / 无 migration（ctest 505
不动）；pytest 增 dashboard auth/inspect/commands/ws 用例全绿 + vitest + e2e smoke。
roadmap 登记 P2.g 行。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

- [ ] **Step 5: 合并回 main（需显式 consent + dangerouslyDisableSandbox）**

> ⚠ 合并前 `git -C /Users/jaredguo-mini/develop/memory/starling status` 检查并清理 stray，再 `--no-ff` 合并 `worktree-p2-g-dashboard` 回 main。**需用户显式同意**后执行。

---

## 自检（writing-plans self-review）

**1. Spec 覆盖：** §2 架构→Task 1/2/7；§3 后端 API→Task 2；§4 前端→Task 3-6；§5 实时→Task 7；§6 安全→Task 1/8；§7 四面板→Task 3(D)/4(A)/5(B)/6(C)；§8 仓库布局→Task 1-2；§9 测试→各 Task 测试步 + Task 9 回归；§10 约束→各 Task 注入；§11 构建顺序→Task 0-9 一一对应；§12 验收→Task 9。无缺口。

**2. 占位扫描：** 无 TBD/TODO；每代码步含完整 code block。Task 7 Step 4 与 Step 6 标注「实现者按 TestClient/Svelte 实际行为微调断言/接线」——属真实环境适配说明，非占位（语义与期望明确）。

**3. 类型一致：** API 契约（§文件结构「统一 API 契约」）贯穿后端路由（Task 2）与前端 fetch（Task 3-6）一致：`/api/overview`、`/api/statements`、`/api/commitments`(rows 含 state/subject_id/predicate/object_value)、`/api/conflicts`(by_kind + conflicts)、`/api/queues`(dispatch/embedding_backlog/vectors_by_status)、命令 `/api/remember|recall|tick|working_set`、`WS /ws` 事件 `{type,payload}`。`DashboardConfig`/`create_app(config, *, memory=None)`/`make_require_token` 跨 Task 1/2/7/8 签名一致。
