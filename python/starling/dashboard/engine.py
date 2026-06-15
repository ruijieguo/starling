"""DashboardEngine — a configurable, partially-hot-swappable engine stack.

The remember / recall / tick / working-set command logic lives in
`starling._memory_core.MemoryCore` (single implementation shared with
`starling.Memory`, so the two surfaces cannot drift). This engine keeps only
the dashboard-specific policy: the chat LLM and the embedder are built from
`DashboardConfig` (both UI-configurable), so the embedder used to WRITE vectors
(EmbeddingWorker) and READ them (SemanticRetriever) stay the same.

The SQLite runtime/connection is built ONCE at construction (db_path is fixed)
and never rebuilt — config changes only swap the llm and/or rebuild the
embedder-dependent components, reusing the single writer connection (no WAL
double-writer). API keys are injected via a transient os.environ swap at
adapter-build time (the binding does not expose api_key; Config.from_env()
captures it at build), so chat and embedder may use different providers/keys.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from starling import _core
from starling import runtime as _runtime
from starling._memory_core import LLMNotConfigured, MemoryCore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


logger = logging.getLogger(__name__)


# Routes run engine calls in worker threads (anyio to_thread), so the transient
# os.environ mutation below needs mutual exclusion or two concurrent adapter
# builds could capture each other's keys.
_ENV_SWAP_LOCK = threading.Lock()


@contextmanager
def _env_swap(api_key: str, base_url: str, *,
              key_env: str = "OPENAI_API_KEY", base_env: str = "OPENAI_BASE_URL"):
    """Temporarily set <key_env>/<base_env> so the adapter's from_env() captures them.

    Parametric over the env-var names so the Anthropic path can inject
    ANTHROPIC_API_KEY/ANTHROPIC_BASE_URL through the same transient swap.
    Serialized via _ENV_SWAP_LOCK — os.environ is process-global state.
    """
    with _ENV_SWAP_LOCK:
        saved = {k: os.environ.get(k) for k in (key_env, base_env)}
        try:
            os.environ[key_env] = api_key
            if base_url:
                os.environ[base_env] = base_url
            else:
                os.environ.pop(base_env, None)  # clear stale value
            yield
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def _build_chat_adapter(llm_cfg: dict):
    """Provider factory: anthropic → AnthropicAdapter (native Messages API),
    everything else → OpenAIAdapter (OpenAI-compatible: openai/azure/ollama/
    groq/deepseek/openrouter/vllm/lmstudio/custom). Key injected via env-swap."""
    provider = (llm_cfg.get("provider") or "openai").lower()
    if provider == "anthropic":
        with _env_swap(llm_cfg["api_key"], llm_cfg.get("base_url", ""),
                       key_env="ANTHROPIC_API_KEY", base_env="ANTHROPIC_BASE_URL"):
            cfg = _core.AnthropicAdapterConfig.from_env()
            if llm_cfg.get("model"):
                cfg.model = llm_cfg["model"]
            if llm_cfg.get("base_url"):
                cfg.base_url = llm_cfg["base_url"]
            return _core.AnthropicAdapter(cfg)
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
        # Embedded facade preflight: relax to the embedded capability subset
        # (testing_helper_marker test-only; engram_per_record_key deferred M0.4+KMS).
        _runtime.relax_preflight_for_embedded()
        # Serializes all engine entry points: routes call them from worker
        # threads (anyio to_thread) and SQLite has a single writer connection.
        # RLock because working_set() re-enters recall().
        self._lock = threading.RLock()
        self._cfg = config
        self._db_path = config.db_path
        rt = _runtime._build_local_store_sqlite_runtime(Path(config.db_path))
        rt.start()
        self._core = MemoryCore(rt, agent=config.agent, tenant_id=config.tenant,
                                adapter_name="dashboard", source_prefix="dash-",
                                vector_backend=config.vector_backend,
                                vector_store_path=(config.vector_store_path or None))
        # P2.o 后台维护 tick(写→读闭环的离线半边);start_background_tick 启动。
        self._tick_thread: threading.Thread | None = None
        self._tick_stop: threading.Event | None = None
        self.set_llm(config.llm)
        self.rebuild_embedder(config.embedder, reembed=False)

    # `engine.llm` stays read/write: tests and offline harnesses inject a
    # FakeLLMAdapter directly (`eng.llm = fake`).
    @property
    def llm(self):
        return self._core.llm

    @llm.setter
    def llm(self, value) -> None:
        self._core.llm = value

    def set_llm(self, llm_cfg: dict) -> None:
        with self._lock:
            self._core.llm = (_build_chat_adapter(llm_cfg)
                              if llm_cfg.get("api_key") else None)

    def rebuild_embedder(self, emb_cfg: dict, *, reembed: bool = True) -> None:
        with self._lock:
            emb = (_build_embed_adapter(emb_cfg) if emb_cfg.get("api_key")
                   else _core.StubEmbeddingAdapter(8))
            self._core.set_embedder(emb)
            if reembed:
                self._reembed()

    def _reembed(self) -> None:
        """Clear this tenant's stored vectors (dim/space changed) and re-embed."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("DELETE FROM statement_vectors WHERE tenant_id = ?",
                         (self._core.tenant,))
            conn.commit()
        finally:
            conn.close()
        self._core.worker.tick_one_batch(_now_iso())

    @property
    def llm_configured(self) -> bool:
        return self._core.llm is not None

    def remember(self, text: str, *, holder=None, interlocutor=None, now=None) -> dict:
        with self._lock:
            return self._core.remember(text, holder=holder,
                                       interlocutor=interlocutor, now=now)

    def recall(self, query: str, *, perspective="first_person", k=10, mode="semantic",
               holder=None) -> list:
        with self._lock:
            return self._core.recall(query, perspective=perspective, k=k, mode=mode,
                                     holder=holder)

    def tick(self, now: str) -> dict:
        with self._lock:
            return self._core.tick(now)

    def forget(self, ids, *, now=None) -> dict:
        with self._lock:
            return self._core.forget(ids, now=now)

    def plan_query(self, text: str, *, intent: str, perspective=None,
                   target=None, k: int = 10) -> dict:
        """P3.a1 检索规划(9 意图 + 8 标签 + 拒答);JSON-able 摘要给路由层。"""
        with self._lock:
            r = self._core.plan_query(text, intent=intent,
                                      perspective=perspective, target=target, k=k)
            return {
                "results": [{"subject": e.row.subject_id,
                             "predicate": e.row.predicate,
                             "object": e.row.object_value,
                             "score": e.score, "label": e.label.name}
                            for e in r.entries],
                "context_pack": r.context_pack,
                "abstained": r.abstained,
                "abstention_reason": r.receipt.abstention_reason,
                "plan_steps": [{"step": s.step, "detail": s.detail}
                               for s in r.receipt.plan_steps],
                "scopes_searched": list(r.receipt.scopes_searched),
            }

    def start_background_tick(self, interval_s: float, on_tick=None) -> None:
        """周期维护线程(P2.o 运行时闭环):每 interval_s 秒跑一次 tick
        (嵌入 → 承诺触发 → grounding → 回放巩固 → 投影兜底 → 出箱收敛),
        让 remember 的内容无人工干预地变得可召回。

        - 首次 tick 在一个完整间隔之后(避免启动时与首屏请求抢引擎锁);
        - tick 持引擎 RLock,期间 UI 命令请求排队——与手动 tick 同语义;
        - on_tick(stats) 仅在本轮有实际变化(任一计数非零)时回调,调用方
          用它做 WS 广播;
        - 异常记日志后继续循环(网络嵌入失败不杀线程);
        - interval_s <= 0 或已启动时为 no-op。
        """
        if interval_s <= 0 or self._tick_thread is not None:
            return
        stop = threading.Event()

        def _loop() -> None:
            while not stop.wait(interval_s):
                try:
                    stats = self.tick(_now_iso())
                except Exception:  # noqa: BLE001 — 保活:单轮失败不终结调度
                    logger.exception("background tick failed")
                    continue
                if on_tick is not None and any(stats.values()):
                    try:
                        on_tick(stats)
                    except Exception:  # noqa: BLE001
                        logger.exception("background tick on_tick callback failed")

        self._tick_stop = stop
        self._tick_thread = threading.Thread(
            target=_loop, name="starling-bg-tick", daemon=True)
        self._tick_thread.start()

    def stop_background_tick(self) -> None:
        if self._tick_thread is None:
            return
        self._tick_stop.set()
        # 有界等待:线程可能正阻塞在真模型嵌入网络调用里;daemon 线程随
        # 进程退出,这里只为测试与显式 close 提供确定性收尾。
        self._tick_thread.join(timeout=5.0)
        self._tick_thread = None
        self._tick_stop = None

    def working_set(self, interlocutor, *, goal=None, token_budget=2000, holder=None) -> dict:
        """Like Memory.render_working_set but returns a JSON-able dict (API shape)."""
        with self._lock:
            cb = self._core.build_working_set(interlocutor, goal=goal,
                                              token_budget=token_budget, holder=holder)
            return {"render": cb.render(),
                    "blocks": [{"label": b.label, "content": b.content,
                                "tokens": b.token_estimate} for b in cb.blocks],
                    "truncated": cb.truncated}

    def close(self) -> None:
        self.stop_background_tick()
        self._core.close()


# Back-compat alias: routes and tests import the underscore name from here.
_LLMNotConfigured = LLMNotConfigured
