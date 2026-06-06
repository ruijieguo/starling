# P2.h Dashboard 一键启动 + UI 配置 LLM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 dashboard 一键单进程启动（FastAPI 同端口 serve 前端静态产物 + /api + /ws），LLM 与 embedder 在 `/settings` 界面后配置，所有配置收敛到一个 `~/.starling/starling.json`（gitignored + 0600），token 首次自动生成并以 `#token=` 登录 URL 呈现。

**Architecture:** 新增统一配置 `DashboardConfig.load()`（文件+env+默认+token 自动生成）；新增 dashboard 自有可配置/部分热切换引擎栈 `DashboardEngine`（镜像 `starling.Memory` 薄逻辑，llm+embedder 可配，key 经瞬时 env-swap at build 注入）；`/api/config` 路由读写配置 + 重建栈；前端切 `adapter-static`（SPA），FastAPI `StaticFiles` + SPA catch-all 单端口 serve。**不改 `starling.Memory`、零 C++、无 migration。**

**Tech Stack:** Python 3.14 + FastAPI + uvicorn；SvelteKit (Svelte 5) + adapter-static + Tailwind + TS (Node ≥20)；pytest + vitest + Playwright。

**Spec:** `docs/superpowers/specs/2026-06-06-p2-h-oneclick-config-design.md`（commit 3c99322）。

**执行位置：** 直接在 main 工作树执行（纯增量 Python+TS，无 C++/无 migration）。commit 到本地 main；push 需显式 consent。

---

## 文件结构（决策锁定）

**后端（`python/starling/dashboard/`）**
- `config.py`（Modify）— `DashboardConfig` 加 `llm`/`embedder` 字段 + `load()`/`save()`/`to_dict()` + token 自动生成 + 默认路径
- `engine.py`（Create）— `DashboardEngine`（可配 llm/embedder + 部分热切换 + env-swap build + 命令方法）
- `routes/config.py`（Create）— `GET/POST /api/config`（masked + 持久化 + set_llm/rebuild_embedder）
- `routes/commands.py`（Modify）— `_memory` → `_engine`；remember 未配 llm → 409
- `app.py`（Modify）— 建 `app.state.engine`；装 config router；挂 `StaticFiles` + SPA catch-all（最后）
- `__init__.py`（Modify）— 导出 `DashboardEngine`

**启动器** `scripts/run_dashboard.py`（Modify）— `load()` + 自动 build + 打印 `#token=` 登录 URL

**前端（`dashboard/web/`）**
- `package.json` / `svelte.config.js`（Modify）— adapter-node → adapter-static（SPA）
- `src/routes/+layout.ts`（Create）— `ssr=false; prerender=false`
- `src/lib/token.ts`（Modify）— `#token=` 自动登录
- `src/routes/+layout.svelte`（Modify）— 加 `/settings` 导航 + LLM 状态灯
- `src/routes/settings/+page.svelte`（Create）— LLM + embedder 表单
- `src/lib/api.ts` 复用

**其它** `.gitignore`（Modify）— 补 `starling.json`、`dashboard/web/build`

**测试** `tests/python/test_dashboard_config.py`、`test_dashboard_engine.py`、`test_dashboard_config_routes.py`（Create）；前端 `src/lib/token.test.ts`

---

## Task 0: Baseline 确认

**Files:** 无

- [ ] **Step 1: 基线全绿**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && source .venv/bin/activate
python -m pytest -q 2>&1 | tail -2
cd dashboard/web && npx vitest run 2>&1 | tail -2 && npm run build 2>&1 | tail -2
```
Expected: pytest `526 passed`；vitest `2 passed`；前端 build 成功。

- [ ] **Step 2: 确认 adapter-static 未装 + migrations 0021**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
grep -c adapter-static dashboard/web/package.json || echo "0 (未装，Task 5 装)"
ls migrations/ | tail -1
```
Expected: adapter-static 计数 0；migration `0021_commitment_tenant_keys.sql`。

无 commit。

---

## Task 1: 统一配置 `DashboardConfig.load()` + token 自动生成

**Files:**
- Modify: `python/starling/dashboard/config.py`
- Modify: `.gitignore`
- Test: `tests/python/test_dashboard_config.py`

- [ ] **Step 1: 重写 `config.py`**

Replace `python/starling/dashboard/config.py` 全文：
```python
"""Dashboard runtime configuration.

Single source of truth is `~/.starling/starling.json` (0600, gitignored): it
holds the dashboard fields plus the dashboard bearer `token` and the `llm` /
`embedder` provider configs (incl. their api_key). The file is the persistent
secret store — it is NEVER committed to git, written to the SQLite memory DB,
or logged. `GET /api/config` never returns the token or full keys.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".starling"
_DEFAULT_CONFIG = _DEFAULT_DIR / "starling.json"
_DEFAULT_DB = _DEFAULT_DIR / "dashboard.db"

_SERIALIZABLE = (
    "db_path", "agent", "tenant", "token", "host", "port",
    "cors_origins", "llm", "embedder",
)


def _default_llm() -> dict:
    return {"model": "", "base_url": "", "api_key": ""}


def _default_embedder() -> dict:
    return {"model": "", "base_url": "", "api_key": "", "dim": 1024}


@dataclass
class DashboardConfig:
    db_path: str = ""
    agent: str = "self"
    tenant: str = "default"
    token: str = ""
    host: str = "127.0.0.1"
    port: int = 8787
    cors_origins: list[str] = field(default_factory=list)
    llm: dict = field(default_factory=_default_llm)
    embedder: dict = field(default_factory=_default_embedder)
    config_path: str = ""  # not serialized; where load()/save() persist

    # -- env-only legacy path (kept for backward compat / CI) ----------------
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

    # -- unified config-file path (one-click) --------------------------------
    @classmethod
    def load(cls, path: str | None = None) -> "DashboardConfig":
        """Load defaults -> file -> env, then auto-generate+persist a token."""
        cfg = cls(db_path=str(_DEFAULT_DB))
        p = Path(path or os.environ.get("STARLING_CONFIG") or _DEFAULT_CONFIG).expanduser()
        cfg.config_path = str(p)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            for k in _SERIALIZABLE:
                if k in data and data[k] is not None:
                    setattr(cfg, k, data[k])
        _env_overlay(cfg)
        cfg.db_path = str(Path(cfg.db_path).expanduser())
        if not cfg.token:
            cfg.token = secrets.token_urlsafe(24)
            cfg.save()
        return cfg

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in _SERIALIZABLE}

    def save(self, path: str | None = None) -> None:
        p = Path(path or self.config_path or _DEFAULT_CONFIG).expanduser()
        p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                     encoding="utf-8")
        os.chmod(p, 0o600)
        self.config_path = str(p)

    def validate_bind(self) -> None:
        """Refuse to expose a tokenless service on a non-loopback interface."""
        if self.host not in ("127.0.0.1", "localhost", "::1") and not self.token:
            raise RuntimeError(
                "refusing to bind dashboard to non-loopback host without a token"
            )


def _env_overlay(cfg: DashboardConfig) -> None:
    """env > file for dashboard fields; seed llm from OPENAI_* when file empty."""
    e = os.environ.get
    if e("STARLING_DASH_DB"): cfg.db_path = e("STARLING_DASH_DB")
    if e("STARLING_DASH_AGENT"): cfg.agent = e("STARLING_DASH_AGENT")
    if e("STARLING_DASH_TENANT"): cfg.tenant = e("STARLING_DASH_TENANT")
    if e("STARLING_DASH_TOKEN"): cfg.token = e("STARLING_DASH_TOKEN")
    if e("STARLING_DASH_HOST"): cfg.host = e("STARLING_DASH_HOST")
    if e("STARLING_DASH_PORT"): cfg.port = int(e("STARLING_DASH_PORT"))
    if e("STARLING_DASH_CORS_ORIGINS"):
        cfg.cors_origins = [o.strip() for o in e("STARLING_DASH_CORS_ORIGINS").split(",") if o.strip()]
    if not cfg.llm.get("api_key") and e("OPENAI_API_KEY"):
        cfg.llm = {"model": e("OPENAI_MODEL", cfg.llm.get("model", "")),
                   "base_url": e("OPENAI_BASE_URL", cfg.llm.get("base_url", "")),
                   "api_key": e("OPENAI_API_KEY")}
```

- [ ] **Step 2: 写测试 `tests/python/test_dashboard_config.py`**

```python
import json
import os
import stat

from starling.dashboard.config import DashboardConfig


def test_load_defaults_and_token_autogen(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_DASH_TOKEN", raising=False)
    cfg_path = tmp_path / "starling.json"
    cfg = DashboardConfig.load(str(cfg_path))
    assert cfg.token and len(cfg.token) >= 20          # auto-generated
    assert cfg_path.exists()                            # persisted
    assert stat.S_IMODE(os.stat(cfg_path).st_mode) == 0o600
    # token stable across reloads
    cfg2 = DashboardConfig.load(str(cfg_path))
    assert cfg2.token == cfg.token


def test_file_then_env_precedence(tmp_path, monkeypatch):
    cfg_path = tmp_path / "starling.json"
    cfg_path.write_text(json.dumps({
        "token": "filetok", "host": "127.0.0.1", "port": 9000,
        "llm": {"model": "m-file", "base_url": "", "api_key": "k-file"},
    }))
    monkeypatch.setenv("STARLING_DASH_PORT", "9999")    # env overrides file
    cfg = DashboardConfig.load(str(cfg_path))
    assert cfg.port == 9999 and cfg.token == "filetok"
    assert cfg.llm["api_key"] == "k-file"


def test_save_roundtrip_excludes_config_path(tmp_path):
    cfg = DashboardConfig(db_path="x.db", token="t", config_path=str(tmp_path / "c.json"))
    cfg.llm = {"model": "gpt", "base_url": "", "api_key": "sk-xyz"}
    cfg.save()
    data = json.loads((tmp_path / "c.json").read_text())
    assert "config_path" not in data and data["llm"]["api_key"] == "sk-xyz"
```

- [ ] **Step 3: 跑测试**

Run: `cd /Users/jaredguo-mini/develop/memory/starling && source .venv/bin/activate && python -m pytest tests/python/test_dashboard_config.py -v`
Expected: 3 passed。

- [ ] **Step 4: `.gitignore` 补两行**

在 `/Users/jaredguo-mini/develop/memory/starling/.gitignore` 末尾追加：
```gitignore
starling.json
dashboard/web/build
```

- [ ] **Step 5: 回归**

Run: `python -m pytest tests/python/test_dashboard_*.py -q 2>&1 | tail -2`
Expected: 既有 dashboard 用例 + 新 3 个全 passed（注意：现有 P2.g 测试以 `DashboardConfig(db_path=...)` 关键字构造，db_path 现有默认值不影响）。

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard/config.py tests/python/test_dashboard_config.py .gitignore
git commit -F - <<'EOF'
feat(P2.h): 统一配置 DashboardConfig.load + token 自动生成

config.py：加 llm/embedder 字段 + load()(默认→文件→env 优先级)+ save()(0600)+
to_dict()(排除 config_path)+ token 首次 secrets.token_urlsafe(24) 自动生成回写。
默认 ~/.starling/starling.json + dashboard.db。.gitignore 补 starling.json +
dashboard/web/build。3 测试（token 自动生成+0600+稳定、文件/env 优先级、save 往返）。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 2: `engine.py` DashboardEngine（可配 llm/embedder + 命令方法）

**Files:**
- Create: `python/starling/dashboard/engine.py`
- Modify: `python/starling/dashboard/__init__.py`
- Test: `tests/python/test_dashboard_engine.py`

- [ ] **Step 1: 写 `engine.py`**

镜像 `python/starling/memory.py` 的命令逻辑（已读确认签名）。Create `python/starling/dashboard/engine.py`：
```python
"""DashboardEngine — a configurable, partially-hot-swappable engine stack.

Mirrors the thin command logic of `starling.Memory` but builds the chat LLM and
the embedder from `DashboardConfig` (both UI-configurable), so the embedder used
to WRITE vectors (EmbeddingWorker) and READ them (SemanticRetriever) stay the
same. `starling.Memory` is left untouched.

The SQLite runtime/connection is built ONCE at construction (db_path is fixed)
and never rebuilt — config changes only swap the llm and/or rebuild the
embedder-dependent components, reusing the single writer connection (no WAL
double-writer). API keys are injected via a transient os.environ swap at
adapter-build time (the binding does not expose api_key; Config.from_env()
captures it at build), so chat and embedder may use different providers/keys.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from starling import _core
from starling import runtime as _runtime
from starling.evidence.inputs import for_user_input
from starling.testing import relax_preflight_for_m0_3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@contextmanager
def _env_swap(api_key: str, base_url: str):
    """Temporarily set OPENAI_API_KEY/BASE_URL so from_env() captures them."""
    saved = {k: os.environ.get(k) for k in ("OPENAI_API_KEY", "OPENAI_BASE_URL")}
    try:
        os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["OPENAI_BASE_URL"] = base_url
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _build_chat_adapter(llm_cfg: dict):
    with _env_swap(llm_cfg["api_key"], llm_cfg.get("base_url", "")):
        cfg = _core.OpenAIAdapterConfig.from_env()
        if llm_cfg.get("model"):
            cfg.model = llm_cfg["model"]
        if llm_cfg.get("base_url"):
            cfg.base_url = llm_cfg["base_url"]
        return _core.OpenAIAdapter(cfg)


def _build_embed_adapter(emb_cfg: dict):
    with _env_swap(emb_cfg["api_key"], emb_cfg.get("base_url", "")):
        cfg = _core.OpenAIEmbeddingConfig.from_env()
        if emb_cfg.get("model"):
            cfg.model = emb_cfg["model"]
        if emb_cfg.get("base_url"):
            cfg.base_url = emb_cfg["base_url"]
        if emb_cfg.get("dim"):
            cfg.dim = int(emb_cfg["dim"])
        return _core.OpenAIEmbeddingAdapter(cfg)


class DashboardEngine:
    def __init__(self, config) -> None:
        relax_preflight_for_m0_3()
        self._cfg = config
        self._tenant = config.tenant
        self._agent = config.agent
        self._db_path = config.db_path
        self._rt = _runtime._build_local_store_sqlite_runtime(Path(config.db_path))
        self._rt.start()
        self._conn = self._rt.adapter.connection()
        self._idx = _core.SqliteBlobVectorIndex()
        self._policy = _core.PolicyEngine(self._rt.adapter)
        self.llm = None
        self._emb = None
        self._semantic = None
        self._completor = None
        self._worker = None
        self.set_llm(config.llm)
        self.rebuild_embedder(config.embedder, reembed=False)

    # -- hot-swap (no connection rebuild) -----------------------------------
    def set_llm(self, llm_cfg: dict) -> None:
        self.llm = _build_chat_adapter(llm_cfg) if llm_cfg.get("api_key") else None

    def rebuild_embedder(self, emb_cfg: dict, *, reembed: bool = True) -> None:
        self._emb = (_build_embed_adapter(emb_cfg) if emb_cfg.get("api_key")
                     else _core.StubEmbeddingAdapter(8))
        self._semantic = _core.SemanticRetriever(self._rt.adapter, self._emb, self._idx)
        self._completor = _core.PatternCompletor(self._rt.adapter, self._semantic)
        self._worker = _core.EmbeddingWorker(self._rt.adapter, self._emb, self._idx)
        if reembed:
            self._reembed()

    def _reembed(self) -> None:
        """Clear this tenant's stored vectors (dim/space changed) and re-embed."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("DELETE FROM statement_vectors WHERE tenant_id = ?",
                         (self._tenant,))
            conn.commit()
        finally:
            conn.close()
        self._worker.tick_one_batch(_now_iso())

    @property
    def llm_configured(self) -> bool:
        return self.llm is not None

    # -- command methods (mirror memory.py) ---------------------------------
    def remember(self, text: str, *, holder=None, now=None) -> dict:
        if self.llm is None:
            raise _LLMNotConfigured()
        holder = holder or self._agent
        payload = text.encode("utf-8")
        created_at = _parse_now(now)
        inp = for_user_input(
            tenant_id=self._tenant, adapter_name="dashboard", adapter_version="1",
            source_item_id="dash-" + str(abs(hash(text))), source_version="1",
            payload_bytes=payload, privacy_class=_core.PrivacyClass.INTERNAL,
            retention_mode=_core.EngramRetentionMode.AUDIT_RETAIN, created_at=created_at,
        )
        out = self._rt.bus.append_evidence(inp, None)
        kind = out["kind"]
        if kind not in ("accepted", "idempotent"):
            return {"engram_ref": "", "statement_ids": [], "outcome": kind}
        engram_ref = out["engram_ref"].id
        r = _core.Extractor(self._conn, self.llm).run(engram_ref, payload, holder, self._tenant, {})
        return {"engram_ref": engram_ref, "statement_ids": list(r.accepted_statement_ids),
                "outcome": kind}

    def recall(self, query: str, *, perspective="first_person", k=10, mode="semantic") -> list:
        if mode == "completion":
            res = self._completor.complete(_core.PatternCompletionParams(
                tenant_id=self._tenant, holder_id=self._agent,
                holder_perspective=perspective, cue_text=query, result_k=k))
            return [{"row": s.row, "score": s.activation} for s in res.rows]
        res = self._semantic.vector_recall(_core.SemanticRetrieverParams(
            tenant_id=self._tenant, holder_id=self._agent,
            holder_perspective=perspective, query_text=query, k=k))
        return [{"row": s.row, "score": s.score} for s in res.rows]

    def tick(self, now: str) -> dict:
        es = self._worker.tick_one_batch(now)
        ps = self._policy.tick(now)
        embedded = es.embedded if hasattr(es, "embedded") else (es if isinstance(es, int) else 0)
        return {"embedded": embedded, "fired": ps.fired, "broken": ps.broken,
                "auto_withdrawn": ps.auto_withdrawn}

    def working_set(self, interlocutor, *, goal=None, token_budget=2000) -> dict:
        from starling import working_set as _ws
        adapter = self._rt.adapter
        sections = {}
        pv = _core.PersonaContainer(adapter).read(self._tenant, self._agent)
        if pv.found and pv.dimensions:
            sections["persona"] = "; ".join(f"{k}: {v}" for k, v in pv.dimensions.items())
        cg = _core.CommonGroundContainer(adapter).read(self._tenant, f"{self._agent}::{interlocutor}")
        if cg.found and cg.grounded:
            sections["common_ground"] = "\n".join("- " + g for g in cg.grounded)
        hits = self.recall(goal, mode="semantic", k=5) if goal else []
        if hits:
            sections["relevant_memories"] = "\n".join(
                "- " + f"{h['row'].subject_id} {h['row'].predicate} {h['row'].object_value}" for h in hits)
        pend = _core.CommitmentEngine(adapter).pending(self._tenant, self._agent, interlocutor)
        if pend:
            lines = []
            for c in pend:
                tag = "⚠ DUE: " if c.fired else ""
                lines.append(f"- {tag}{c.subject_id} {c.predicate} {c.object_value}"
                             + (f" (by {c.deadline})" if c.deadline else ""))
            sections["pending_commitments"] = "\n".join(lines)
        cb = _ws.assemble(sections, token_budget)
        return {"render": cb.render(),
                "blocks": [{"label": b.label, "content": b.content, "tokens": b.token_estimate}
                           for b in cb.blocks],
                "truncated": cb.truncated}

    def close(self) -> None:
        self._conn = None


class _LLMNotConfigured(RuntimeError):
    pass


def _parse_now(now):
    if now is None:
        return datetime.now(timezone.utc)
    s = now.replace("Z", "+00:00") if now.endswith("Z") else now
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
```
注意：`remember` 的 `for_user_input` / `PrivacyClass.INTERNAL` / `EngramRetentionMode.AUDIT_RETAIN` / `Extractor.run` 签名与 `memory.py` 一致（已核对）。若 `EmbeddingWorker.tick_one_batch` 返回值形态不同，按 `memory.py:170-185` 的 `embedded` 兜底处理（已含）。

- [ ] **Step 2: 导出 `DashboardEngine`**

Modify `python/starling/dashboard/__init__.py`：
```python
"""Starling dashboard engine-API (P2.g/P2.h)."""
from starling.dashboard.app import create_app
from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine

__all__ = ["create_app", "DashboardConfig", "DashboardEngine"]
```

- [ ] **Step 3: 写离线测试 `tests/python/test_dashboard_engine.py`**

```python
import pytest

from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine, _LLMNotConfigured

_STUB_XML = (
    "<statements><statement><holder>self</holder>"
    "<holder_perspective>FIRST_PERSON</holder_perspective>"
    "<subject>Bob</subject><predicate>responsible_for</predicate>"
    "<object>auth</object><modality>BELIEVES</modality>"
    "<polarity>POS</polarity><nesting_depth>0</nesting_depth></statement></statements>"
)


@pytest.fixture
def engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "eng.db"), token="t")
    eng = DashboardEngine(cfg)   # llm unset, embedder -> stub8
    return eng


def test_unconfigured_llm_recall_tick_ok_but_remember_raises(engine):
    # recall/tick work with the stub embedder; remember raises (no llm)
    assert engine.recall("auth") == [] or isinstance(engine.recall("auth"), list)
    st = engine.tick("2026-06-01T10:00:00Z")
    assert set(st) == {"embedded", "fired", "broken", "auto_withdrawn"}
    with pytest.raises(_LLMNotConfigured):
        engine.remember("Bob owns auth")


def test_set_llm_enables_remember_offline_stub(engine, monkeypatch):
    # swap in an offline FakeLLMAdapter directly (no network); mimics set_llm result
    from starling import _core
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_XML, True, "")
    engine.llm = fake
    r = engine.remember("Bob owns auth")
    assert r["outcome"] in ("accepted", "idempotent")
    st = engine.tick("2026-06-01T10:00:00Z")
    assert "embedded" in st


def test_working_set_renders(engine):
    ws = engine.working_set("Alice")
    assert "render" in ws and "blocks" in ws and "truncated" in ws
```
注意：`set_llm` 真实路径会经 env-swap 建 `OpenAIAdapter`（需 key、联网），离线测试改为直接把 `engine.llm` 设成 `FakeLLMAdapter`（验证命令逻辑），与 `memory.py` 的 stub 测试一致；`_build_chat_adapter` 的 env-swap 逻辑由 config 路由测试（Task 4）用 monkeypatch 覆盖其 os.environ 行为，不联网。

- [ ] **Step 4: 跑测试**

Run: `cd /Users/jaredguo-mini/develop/memory/starling && source .venv/bin/activate && python -m pytest tests/python/test_dashboard_engine.py -v`
Expected: 3 passed。若 `for_user_input` / `Extractor` 在 stub 下报错，对照 `python/starling/memory.py:108-142` 调参（保持 outcome/shape 断言不依赖抽取条数）。

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard/engine.py python/starling/dashboard/__init__.py tests/python/test_dashboard_engine.py
git commit -F - <<'EOF'
feat(P2.h): DashboardEngine — 可配 llm/embedder + 部分热切换引擎栈

engine.py：镜像 starling.Memory 薄命令逻辑（remember/recall/tick/working_set），
runtime/连接建一次永不重建（db 固定，避 WAL 双写）；可配 llm（key_set 才建
OpenAIAdapter）+ 可配 embedder（key_set 才建 OpenAIEmbeddingAdapter，否则 stub8）；
set_llm/rebuild_embedder 部分热切换；key 经瞬时 env-swap at build 注入（from_env
构建期捕获）；改 embedder 清 statement_vectors(该 tenant)重嵌。不改 starling.Memory。
3 离线测试（未配 remember raise、FakeLLM 启用、working_set 渲染）。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 3: 命令路由改调 engine + 未配 remember 409

**Files:**
- Modify: `python/starling/dashboard/routes/commands.py`
- Modify: `python/starling/dashboard/app.py`（建 `app.state.engine`）
- Test: `tests/python/test_dashboard_commands.py`（更新）

- [ ] **Step 1: `app.py` 建 engine（替代 lazy memory）**

Modify `python/starling/dashboard/app.py`：把 `create_app(config, *, memory=None)` 改为 `create_app(config, *, engine=None)`；`app.state.memory = memory` 改为 `app.state.engine = engine`（懒构建移到命令路由）。具体：
```python
def create_app(config: DashboardConfig, *, engine: object | None = None) -> FastAPI:
    config.validate_bind()
    app = FastAPI(title="Starling Dashboard", version="0.1.0")
    app.state.config = config
    app.state.engine = engine
    ...
```
（其余 ws/health/ping/路由 include 不动；StaticFiles 在 Task 5 加。）

- [ ] **Step 2: `commands.py` `_memory` → `_engine`**

Modify `python/starling/dashboard/routes/commands.py`：把 `_memory` 换成 `_engine`，命令方法改调 engine（注意 engine.remember/recall/tick/working_set 返回 dict/list，签名见 Task 2）：
```python
from fastapi import APIRouter, Depends, HTTPException, Request, status

def _engine(request: Request):
    eng = request.app.state.engine
    if eng is None:
        from starling.dashboard.engine import DashboardEngine
        eng = DashboardEngine(request.app.state.config)
        request.app.state.engine = eng
    return eng
```
remember 路由（未配 llm → 409）：
```python
    @router.post("/remember")
    async def remember(body: RememberBody, request: Request):
        from starling.dashboard.engine import _LLMNotConfigured
        eng = _engine(request)
        try:
            r = eng.remember(body.text, holder=body.holder, now=body.now)
        except _LLMNotConfigured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="llm_not_configured")
        await _broadcast(request, "statement_added", {"statement_ids": r["statement_ids"]})
        return r
```
recall/tick/working_set 改调 engine（返回已是 dict/list，直接返回；recall 项已是 `{"row":..,"score":..}` → 转 `{subject,predicate,object,score}`）：
```python
    @router.post("/recall")
    async def recall(body: RecallBody, request: Request):
        eng = _engine(request)
        hits = eng.recall(body.query, perspective=body.perspective, k=body.k, mode=body.mode)
        out = [{"subject": h["row"].subject_id, "predicate": h["row"].predicate,
                "object": h["row"].object_value, "score": h["score"]} for h in hits]
        await _broadcast(request, "recall", {"n": len(out)})
        return {"results": out}

    @router.post("/tick")
    async def tick(body: TickBody, request: Request):
        eng = _engine(request)
        payload = eng.tick(body.now or _now_iso())
        await _broadcast(request, "tick", payload)
        if payload["fired"]:
            await _broadcast(request, "commitment_fired", {"fired": payload["fired"]})
        return payload

    @router.get("/working_set")
    async def working_set(request: Request, interlocutor: str, goal: str | None = None,
                          token_budget: int = 2000):
        eng = _engine(request)
        return eng.working_set(interlocutor, goal=goal, token_budget=token_budget)
```
（`_broadcast` 不变。）

- [ ] **Step 3: 更新 `tests/python/test_dashboard_commands.py`**

把 fixture 从注入 `Memory` 改为注入 `DashboardEngine`（llm 设为 FakeLLMAdapter 离线），并加未配 → 409 用例：
```python
import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine

_STUB_XML = (
    "<statements><statement><holder>self</holder>"
    "<holder_perspective>FIRST_PERSON</holder_perspective>"
    "<subject>Bob</subject><predicate>responsible_for</predicate>"
    "<object>auth</object><modality>BELIEVES</modality>"
    "<polarity>POS</polarity><nesting_depth>0</nesting_depth></statement></statements>"
)


def _engine_with_llm(db):
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_STUB_XML, True, "")
    eng.llm = fake
    return cfg, eng


@pytest.fixture
def client(tmp_path):
    cfg, eng = _engine_with_llm(str(tmp_path / "cmd.db"))
    return TestClient(create_app(cfg, engine=eng))


def test_remember_then_tick(client):
    r = client.post("/api/remember", json={"text": "Bob owns auth"})
    assert r.status_code == 200 and r.json()["outcome"] in ("accepted", "idempotent")
    t = client.post("/api/tick", json={})
    assert t.status_code == 200 and set(t.json()) == {"embedded", "fired", "broken", "auto_withdrawn"}


def test_recall_shape(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    r = client.post("/api/recall", json={"query": "auth", "k": 5})
    assert r.status_code == 200 and isinstance(r.json()["results"], list)


def test_remember_409_when_llm_unconfigured(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "nollm.db"), token="")
    eng = DashboardEngine(cfg)            # llm unset
    c = TestClient(create_app(cfg, engine=eng))
    r = c.post("/api/remember", json={"text": "x"})
    assert r.status_code == 409 and r.json()["detail"] == "llm_not_configured"


def test_working_set_renders(client):
    r = client.get("/api/working_set", params={"interlocutor": "Alice"})
    assert r.status_code == 200 and "render" in r.json()
```

- [ ] **Step 4: 跑 + 回归**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && source .venv/bin/activate
python -m pytest tests/python/test_dashboard_commands.py tests/python/test_dashboard_inspect.py -v 2>&1 | tail -8
python -m pytest -q 2>&1 | tail -2
```
Expected: commands 4 passed + inspect 5 passed；全量无 failed。

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard/app.py python/starling/dashboard/routes/commands.py tests/python/test_dashboard_commands.py
git commit -F - <<'EOF'
feat(P2.h): 命令路由改调 DashboardEngine + 未配 remember 409

create_app 由 memory= 改 engine=（app.state.engine 懒构建 DashboardEngine）；
命令路由 _memory→_engine；remember 未配 llm（_LLMNotConfigured）→ 409
llm_not_configured，前端引导去设置页。recall/tick/working_set 改调 engine。
测试改注入 engine（FakeLLM 离线）+ 加 409 用例。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 4: `routes/config.py`（GET/POST 配置 + masked + 重建栈）

**Files:**
- Create: `python/starling/dashboard/routes/config.py`
- Modify: `python/starling/dashboard/app.py`（装 config router）
- Test: `tests/python/test_dashboard_config_routes.py`

- [ ] **Step 1: 写 `routes/config.py`**

```python
"""Config routes — read (masked) and update LLM/embedder config + hot-swap."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel


class ProviderBody(BaseModel):
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    dim: int | None = None


class ConfigBody(BaseModel):
    llm: ProviderBody | None = None
    embedder: ProviderBody | None = None


def _mask(d: dict) -> dict:
    out = {"model": d.get("model", ""), "base_url": d.get("base_url", ""),
           "key_set": bool(d.get("api_key"))}
    if "dim" in d:
        out["dim"] = d["dim"]
    return out


def _public(cfg) -> dict:
    return {"agent": cfg.agent, "tenant": cfg.tenant, "host": cfg.host, "port": cfg.port,
            "llm": _mask(cfg.llm), "embedder": _mask(cfg.embedder)}


def _merge(dst: dict, body) -> None:
    if body is None:
        return
    for k in ("model", "base_url", "api_key", "dim"):
        v = getattr(body, k, None)
        if v is not None:
            dst[k] = v


def build_config_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.get("/config")
    async def get_config(request: Request):
        return _public(request.app.state.config)

    @router.post("/config")
    async def post_config(body: ConfigBody, request: Request):
        cfg = request.app.state.config
        eng = request.app.state.engine
        llm_changed = body.llm is not None
        emb_changed = body.embedder is not None
        _merge(cfg.llm, body.llm)
        _merge(cfg.embedder, body.embedder)
        cfg.save()                                   # persist starling.json (0600)
        if eng is not None:
            if llm_changed:
                eng.set_llm(cfg.llm)
            if emb_changed:
                eng.rebuild_embedder(cfg.embedder)   # rebuild + re-embed
        return _public(cfg)

    return router
```

- [ ] **Step 2: `app.py` 装 config router**

Modify `python/starling/dashboard/app.py`：在 include commands/eval 旁加：
```python
    from starling.dashboard.routes.config import build_config_router
    app.include_router(build_config_router(require_token))
```

- [ ] **Step 3: 写测试 `tests/python/test_dashboard_config_routes.py`**

```python
import json
import os
import stat

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine


@pytest.fixture
def ctx(tmp_path):
    cfgfile = tmp_path / "starling.json"
    cfg = DashboardConfig(db_path=str(tmp_path / "c.db"), token="", config_path=str(cfgfile))
    eng = DashboardEngine(cfg)
    client = TestClient(create_app(cfg, engine=eng))
    return cfg, eng, client, cfgfile


def test_get_config_masks_keys(ctx):
    cfg, eng, client, _ = ctx
    cfg.llm["api_key"] = "sk-secret-1234"
    body = client.get("/api/config").json()
    assert body["llm"]["key_set"] is True
    assert "api_key" not in body["llm"] and "secret" not in json.dumps(body)


def test_post_config_persists_0600_and_hot_swaps(ctx):
    cfg, eng, client, cfgfile = ctx
    r = client.post("/api/config", json={"llm": {"model": "m", "base_url": "", "api_key": "sk-x"}})
    assert r.status_code == 200 and r.json()["llm"]["key_set"] is True
    # persisted with the key, 0600
    assert cfgfile.exists() and stat.S_IMODE(os.stat(cfgfile).st_mode) == 0o600
    assert json.loads(cfgfile.read_text())["llm"]["api_key"] == "sk-x"
    # engine.llm hot-swapped (built from the config key via env-swap)
    # (network not exercised here; just assert it attempted to build a non-None adapter
    #  by checking llm_configured flips when a key is present)
    assert eng.llm is not None


def test_get_config_never_returns_token(ctx):
    cfg, eng, client, _ = ctx
    assert "token" not in client.get("/api/config").json()
```
注意：`test_post_config_persists_0600_and_hot_swaps` 断言 `eng.llm is not None` —— `set_llm` 经 `_build_chat_adapter` 的 env-swap 建 `OpenAIAdapter`（构建不联网，仅 `OpenAIAdapter(cfg)` 实例化）。若实例化在无真实 key 下抛错，改为 monkeypatch `engine._build_chat_adapter` 返回一个 `_core.FakeLLMAdapter`，保持「key_set→llm 非 None」语义。

- [ ] **Step 4: 跑 + 回归**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && source .venv/bin/activate
python -m pytest tests/python/test_dashboard_config_routes.py -v 2>&1 | tail -8
python -m pytest -q 2>&1 | tail -2
```
Expected: config_routes 3 passed；全量无 failed。

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard/routes/config.py python/starling/dashboard/app.py tests/python/test_dashboard_config_routes.py
git commit -F - <<'EOF'
feat(P2.h): /api/config 读写配置 + masked + 热切换引擎栈

routes/config.py：GET /api/config 返回非密钥配置 + key_set 布尔（绝不回 token/
完整 key）；POST /api/config 合并进 app.state.config + 写 starling.json(0600) +
set_llm/rebuild_embedder 热切换（改 embedder 重嵌）。3 测试（key 打码、持久化
0600+热切换、不泄 token）。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 5: 单进程（adapter-static + StaticFiles + SPA 兜底 + 自动 build + 登录 URL）

**Files:**
- Modify: `dashboard/web/package.json`、`dashboard/web/svelte.config.js`
- Create: `dashboard/web/src/routes/+layout.ts`
- Modify: `python/starling/dashboard/app.py`（StaticFiles + SPA catch-all）
- Modify: `scripts/run_dashboard.py`（自动 build + 登录 URL）

- [ ] **Step 1: 装 adapter-static + 切换**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/dashboard/web
npm install -D @sveltejs/adapter-static
npm uninstall @sveltejs/adapter-node
```
Modify `dashboard/web/svelte.config.js`：`import adapter from '@sveltejs/adapter-node'` → `import adapter from '@sveltejs/adapter-static'`；`adapter: adapter()` → `adapter: adapter({ fallback: 'index.html' })`。
Create `dashboard/web/src/routes/+layout.ts`：
```ts
export const ssr = false;
export const prerender = false;
```

- [ ] **Step 2: 构建验证（产出 build/）**

Run: `cd /Users/jaredguo-mini/develop/memory/starling/dashboard/web && npm run build 2>&1 | tail -4 && ls build/index.html`
Expected: build 成功；`build/index.html` 存在（SPA fallback）。

- [ ] **Step 3: `app.py` 挂 StaticFiles + SPA catch-all**

Modify `python/starling/dashboard/app.py`：顶部 import 加 `from pathlib import Path` 与 `from fastapi.responses import FileResponse`、`from fastapi.staticfiles import StaticFiles`。在所有 `app.include_router(...)` 之后、`return app` 之前加：
```python
    _build = Path(__file__).resolve().parents[3] / "dashboard" / "web" / "build"
    if _build.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_build / "_app")), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str):
            # SPA fallback: serve a real static file if present, else index.html.
            candidate = _build / full_path
            if full_path and candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(_build / "index.html"))
```
注意：catch-all 用 `/{full_path:path}` 必须**在所有 /api、/ws、/health 路由注册之后**才挂（FastAPI 按注册顺序匹配，前面的具体路由优先）。`parents[3]` 从 `python/starling/dashboard/app.py` 上溯到仓库根（dashboard→starling→python→root）——实测 `Path('python/starling/dashboard/app.py').resolve().parents[3]` 应为仓库根；若层级不对调整。SvelteKit adapter-static 默认把构建资产放 `build/_app/`，故 `/assets` 挂 `_app`；若实际目录名不同（看 `ls build/`），按实际调整 mount 路径，或直接用 catch-all 兜底所有静态文件（已兜底）。

- [ ] **Step 4: `run_dashboard.py` 自动 build + 登录 URL**

Replace `scripts/run_dashboard.py` 全文：
```python
#!/usr/bin/env python3
"""One-click launcher for the Starling dashboard.

Loads unified config (~/.starling/starling.json; token auto-generated on first
run), builds the SvelteKit frontend if missing (needs node), then serves the
FastAPI engine-API + the static frontend on a single port. Prints a login URL
with the token in the URL fragment (#token=…), which browsers do NOT send to
the server — so the token never lands in access logs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import uvicorn

from starling.dashboard import DashboardConfig, create_app

_WEB = Path(__file__).resolve().parents[1] / "dashboard" / "web"


def _ensure_build(no_build: bool) -> None:
    build = _WEB / "build"
    if build.is_dir() or no_build:
        return
    if not (_WEB / "package.json").exists():
        return
    npm = "npm"
    if subprocess.run([npm, "--version"], capture_output=True).returncode != 0:
        sys.exit("frontend build missing and npm not found — run `npm ci && npm run build` in dashboard/web")
    print("building frontend (first run)…", file=sys.stderr)
    subprocess.run([npm, "ci"], cwd=str(_WEB), check=True)
    subprocess.run([npm, "run", "build"], cwd=str(_WEB), check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    cfg = DashboardConfig.load(args.config)
    cfg.validate_bind()
    _ensure_build(args.no_build)
    app = create_app(cfg)
    shown = cfg.host if cfg.host not in ("0.0.0.0", "::") else "127.0.0.1"
    print(f"\nDashboard ready → http://{shown}:{cfg.port}/#token={cfg.token}\n")
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 冒烟（不阻塞起服务）**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && source .venv/bin/activate
python -c "import ast; ast.parse(open('scripts/run_dashboard.py').read()); print('parse ok')"
python -m pytest tests/python/test_dashboard_*.py -q 2>&1 | tail -2
```
Expected: parse ok；dashboard 测试全 passed（StaticFiles 挂载在 build 存在时才生效，测试用 TestClient 不受影响）。

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add dashboard/web/package.json dashboard/web/package-lock.json dashboard/web/svelte.config.js dashboard/web/src/routes/+layout.ts python/starling/dashboard/app.py scripts/run_dashboard.py
git status --short | grep node_modules && echo "ERROR node_modules" || echo "OK"
git commit -F - <<'EOF'
feat(P2.h): 单进程一键启动 — adapter-static + StaticFiles + SPA 兜底 + 登录 URL

前端 adapter-node→adapter-static(SPA，fallback index.html，+layout.ts ssr=false)。
FastAPI 挂 StaticFiles + SPA catch-all（非 /api 非 /ws 回 index.html，深链刷新不
404）。run_dashboard.py：load()(token 自动生成) + 首次自动 npm build + uvicorn
单端口 + 打印 #token= 登录 URL（片段不进 access log）。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 6: 前端设置页 + 状态灯 + `#token=` 自动登录

**Files:**
- Modify: `dashboard/web/src/lib/token.ts`
- Modify: `dashboard/web/src/routes/+layout.svelte`
- Create: `dashboard/web/src/routes/settings/+page.svelte`
- Test: `dashboard/web/src/lib/token.test.ts`

- [ ] **Step 1: `token.ts` 加 `#token=` 自动登录**

Replace `dashboard/web/src/lib/token.ts`：
```ts
const KEY = 'starling_dash_token';

export const getToken = (): string =>
	(typeof localStorage !== 'undefined' && localStorage.getItem(KEY)) || '';

export const setToken = (t: string): void => {
	if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, t);
};

/** Read a `#token=…` URL fragment into storage, then strip it from the address bar.
 *  Fragments are never sent to the server, so the token never lands in access logs. */
export function adoptTokenFromHash(): void {
	if (typeof location === 'undefined' || !location.hash) return;
	const m = location.hash.match(/(?:^#|&)token=([^&]+)/);
	if (m) {
		setToken(decodeURIComponent(m[1]));
		const cleaned = location.hash.replace(/(?:^#|&)token=[^&]+/, '').replace(/^#&?/, '#');
		history.replaceState(null, '', location.pathname + location.search + (cleaned === '#' ? '' : cleaned));
	}
}
```

- [ ] **Step 2: vitest `token.test.ts`**

Create `dashboard/web/src/lib/token.test.ts`：
```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { adoptTokenFromHash, getToken } from './token';

beforeEach(() => {
	localStorage.clear();
	history.replaceState(null, '', '/');
});

describe('adoptTokenFromHash', () => {
	it('adopts #token= and strips it from the URL', () => {
		history.replaceState(null, '', '/#token=abc123');
		adoptTokenFromHash();
		expect(getToken()).toBe('abc123');
		expect(location.hash).toBe('');
	});
	it('no-op without a token fragment', () => {
		history.replaceState(null, '', '/#other=1');
		adoptTokenFromHash();
		expect(getToken()).toBe('');
	});
});
```

- [ ] **Step 3: `+layout.svelte` 加 settings 导航 + 状态灯 + 自动登录**

Modify `dashboard/web/src/routes/+layout.svelte`：① `<script>` import 加 `import { adoptTokenFromHash } from '$lib/token';`、`import { api } from '$lib/api';`；② `$effect(() => { adoptTokenFromHash(); })`（页面加载即吸收 #token）；③ NAV 数组加 `{ href: '/settings', label: '设置' }`；④ 顶部加 LLM 状态灯：
```svelte
	let llmConfigured = $state<boolean | null>(null);
	$effect(() => {
		adoptTokenFromHash();
		api.get<{ llm: { key_set: boolean } }>('/api/config')
			.then((c) => (llmConfigured = c.llm.key_set)).catch(() => (llmConfigured = null));
	});
```
在 nav 顶部「Starling」标题下加：
```svelte
		<div class="px-2 pb-2 text-xs">
			LLM:
			{#if llmConfigured === null}<span class="text-zinc-400">?</span>
			{:else if llmConfigured}<span class="text-green-600">已配置</span>
			{:else}<span class="text-amber-600">未配置</span>{/if}
		</div>
```
（保留现有 Token fallback 输入框。）

- [ ] **Step 4: 设置页 `settings/+page.svelte`**

Create `dashboard/web/src/routes/settings/+page.svelte`：
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	type Prov = { model: string; base_url: string; key_set?: boolean; dim?: number };
	let llm = $state<Prov>({ model: '', base_url: '' });
	let llmKey = $state('');
	let emb = $state<Prov>({ model: '', base_url: '', dim: 1024 });
	let embKey = $state('');
	let msg = $state('');
	$effect(() => {
		api.get<{ llm: Prov; embedder: Prov }>('/api/config')
			.then((c) => { llm = c.llm; emb = c.embedder; }).catch((e) => (msg = String(e)));
	});
	async function save() {
		try {
			const payload: Record<string, unknown> = {
				llm: { model: llm.model, base_url: llm.base_url, ...(llmKey ? { api_key: llmKey } : {}) },
				embedder: { model: emb.model, base_url: emb.base_url, dim: emb.dim,
					...(embKey ? { api_key: embKey } : {}) }
			};
			const c = await api.post<{ llm: Prov; embedder: Prov }>('/api/config', payload);
			llm = c.llm; emb = c.embedder; llmKey = ''; embKey = ''; msg = '已保存';
		} catch (e) { msg = String(e); }
	}
</script>
<h1 class="text-xl font-semibold mb-4">设置</h1>
<div class="space-y-6 max-w-xl">
	<section class="space-y-2">
		<h2 class="text-sm font-semibold text-zinc-500">LLM（抽取用）{#if llm.key_set}<span class="text-green-600 text-xs"> · 已配置</span>{/if}</h2>
		<input bind:value={llm.model} placeholder="model（如 gpt-4o-mini）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={llm.base_url} placeholder="base_url（可选）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={llmKey} type="password" placeholder={llm.key_set ? 'api_key（留空不改）' : 'api_key'} class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
	</section>
	<section class="space-y-2">
		<h2 class="text-sm font-semibold text-zinc-500">Embedder（召回用）{#if emb.key_set}<span class="text-green-600 text-xs"> · 已配置</span>{/if}</h2>
		<input bind:value={emb.model} placeholder="model（如 text-embedding-v3）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={emb.base_url} placeholder="base_url（可选）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={emb.dim} type="number" placeholder="dim" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={embKey} type="password" placeholder={emb.key_set ? 'api_key（留空不改）' : 'api_key'} class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<p class="text-xs text-zinc-400">改 embedder 会重嵌已有记忆（dim 变化）。</p>
	</section>
	<button onclick={save} class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm">保存</button>
	<span class="text-xs text-zinc-500 ml-2">{msg}</span>
</div>
```

- [ ] **Step 5: 构建 + check + vitest**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/dashboard/web
npm run build 2>&1 | tail -3
npx svelte-check 2>&1 | tail -4 || true
npx vitest run 2>&1 | tail -4
```
Expected: build 成功；svelte-check 0 error；vitest 4 passed（原 2 + token 2）。

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add dashboard/web/src
git status --short | grep node_modules && echo "ERROR node_modules" || echo "OK"
git commit -F - <<'EOF'
feat(P2.h): 前端设置页 + LLM 状态灯 + #token= 自动登录

token.ts 加 adoptTokenFromHash（读 #token=→localStorage→history.replaceState
抹掉，片段不进 access log）。+layout 加 /settings 导航 + LLM 状态灯 + 加载即自动
登录。settings 页：LLM + embedder 表单（key 密码框，留空不改），改 embedder 提示
重嵌。vitest 2 token 用例。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 7: 回归 + roadmap 登记 P2.h + close

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`

- [ ] **Step 1: 全量回归**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && source .venv/bin/activate
python -m pytest -q 2>&1 | tail -2
cd dashboard/web && npx vitest run 2>&1 | tail -2 && npm run build 2>&1 | tail -2
cd /Users/jaredguo-mini/develop/memory/starling
echo "migration: $(ls migrations/ | tail -1)"
echo "C++ diff: $(git diff --name-only 3c99322..HEAD | grep -cE '\.(cpp|hpp|h|cc)$|^src/|^include/|^bindings/')"
echo "Memory 改了吗: $(git diff --name-only 3c99322..HEAD | grep -c 'python/starling/memory.py')"
git ls-files | grep -cE 'node_modules|/build|starling.json' && echo "CHECK 上面应为 0"
```
Expected: pytest 全 passed（+config/engine/config_routes ~9 用例）；vitest 4 passed；build 成功；migration 0021；C++ diff 0；Memory 0；git 无 build/starling.json/node_modules。

- [ ] **Step 2: 无密钥泄漏扫描**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
grep -rnE "sk-[A-Za-z0-9]{16,}" python/starling/dashboard dashboard/web/src scripts docs/superpowers/plans/2026-06-06-p2-h-oneclick-config.md || echo "OK 无真实密钥"
```
Expected: OK 无真实密钥。

- [ ] **Step 3: roadmap 登记 P2.h**

在 `docs/superpowers/plans/2026-05-23-roadmap.md` 的 P2 收尾表（P2.g 行之后）追加：
```markdown
| **P2.h 一键启动 + UI 配置 ✅** | dashboard 一键单进程启动（FastAPI 同端口 serve 前端静态产物）+ LLM/embedder 在 /settings 界面后配置 + token 首次自动生成（#token 登录 URL） | P2.g 启动繁琐（两终端 + 一堆 env + LLM 写死 env） | **[2026-06-06-p2-h-oneclick-config.md](2026-06-06-p2-h-oneclick-config.md)**：统一 ~/.starling/starling.json（0600，含 token+key，绝不进 git/库/log）+ DashboardEngine（自有可热切换栈，不改 Memory）+ adapter-static 单端口 + #token 片段登录（不进 log）；无 C++/无 migration（ctest 505 不动） |
```
并把 P2 收尾标题 `## P2 收尾（P2.d / P2.e / P2.f / P2.g）` 改为 `## P2 收尾（P2.d / P2.e / P2.f / P2.g / P2.h）`。

- [ ] **Step 4: 提交 plan + roadmap（milestone close）**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add docs/superpowers/plans/2026-06-06-p2-h-oneclick-config.md docs/superpowers/plans/2026-05-23-roadmap.md
git commit -F - <<'EOF'
docs(P2.h): land 一键启动 + UI 配置实施计划 + roadmap 登记

P2.h 交付：dashboard 一键单进程启动 + LLM/embedder 在 /settings 后配置 + token
首次自动生成（#token 登录 URL）+ 统一 starling.json（0600，gitignored）。
DashboardEngine 自有可热切换栈，不改 starling.Memory；无 C++/无 migration
（ctest 505 不动）；pytest 增 config/engine/config_routes 用例 + vitest token。
roadmap 登记 P2.h。直接在 main 工作树执行（纯增量）。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

- [ ] **Step 5: 最终人工/真实 QA（可选，需 key）**

> 起服务 `python scripts/run_dashboard.py` → 打开打印的 `#token=` URL → 设置页填真 LLM/embedder → remember/recall 验证。需真实 key，不入自动化。

---

## 自检（writing-plans self-review）

**1. Spec 覆盖：** §2 统一配置→Task 1；§3 单进程→Task 5；§4 engine→Task 2；§5 config 路由+设置页→Task 4+6；§6 token 生命周期→Task 1(生成)+5(登录URL)+6(#token 前端)；§7 未配降级→Task 3(409)；§8 安全→Task 1(0600/gitignore)+4(masked)+5(#fragment)；§9 改动面→Task 1-6；§10 测试→各 Task + Task 7；§11 验收→Task 7。无缺口。

**2. 占位扫描：** 无 TBD/TODO；每代码步含完整 code block。`parents[3]`/`parents[1]`、`build/_app` 等标注「实测/按实际调整」属真实环境适配说明（给出验证命令），非占位。

**3. 类型一致：** `DashboardConfig.load/save/to_dict/llm/embedder/config_path`（Task 1）↔ `DashboardEngine`(Task 2 读 config.llm/embedder/db_path/tenant/agent) ↔ `create_app(config, *, engine=None)` / `app.state.engine`（Task 3 app.py + commands）↔ `_public/_mask/_merge` + `set_llm/rebuild_embedder`（Task 4 ↔ Task 2 方法名）↔ 前端 `/api/config` `{llm:{model,base_url,key_set,...}, embedder:{...}}`（Task 6 ↔ Task 4 `_public`）↔ `adoptTokenFromHash`（Task 6 token.ts ↔ +layout）。`_LLMNotConfigured`（Task 2 定义 ↔ Task 3 commands import）。一致。
