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

Phase 5 (P3.c1): a backpressure sampler (HealthSampler + MetricsGatherer) runs
after each background tick.  The C++ sampler is pure; debounce + DRAINING-
suppress live in the host (_sample_backpressure).  Lock order (L8): engine-
RLock → supervisor-mutex; NEVER the reverse.
"""
from __future__ import annotations

import collections
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from starling import _core
from starling import runtime as _runtime
from starling._memory_core import LLMNotConfigured, MemoryCore
from starling.dashboard.ingest_filter import chunk_dialogue, clean_turns


# ── Phase 5 backpressure sampler defaults (L1 / L2) ─────────────────────────
#
# c1 enables outbox_lag + runtime_event_loop_lag_ms ONLY.  The other 5 metrics
# stay DISABLED (zero ≠ healthy; the sampler skips them).
#
# Recommended defaults (documented here as the single source of truth):
#   outbox_lag.threshold              = 100  (sequences)
#   runtime_event_loop_lag_ms.threshold = 200 (ms; proxy for background-tick overload, L6)
_DEFAULT_OUTBOX_LAG_THRESHOLD: int = 100
_DEFAULT_LOOP_LAG_THRESHOLD_MS: float = 200.0
# Flapping damping (L3): how many CONSECUTIVE same-verdict evaluate() results
# must accumulate before note_health is called.
_DEFAULT_DEBOUNCE_TICKS: int = 3


def _build_default_sampler_config(
    *,
    outbox_lag_threshold: int = _DEFAULT_OUTBOX_LAG_THRESHOLD,
    loop_lag_threshold_ms: float = _DEFAULT_LOOP_LAG_THRESHOLD_MS,
) -> "_core.HealthSamplerConfig":
    """Construct a HealthSamplerConfig enabling outbox_lag + runtime_event_loop_lag_ms."""
    cfg = _core.HealthSamplerConfig()
    cfg.outbox_lag.enabled = True
    cfg.outbox_lag.threshold = outbox_lag_threshold
    cfg.runtime_event_loop_lag_ms.enabled = True
    cfg.runtime_event_loop_lag_ms.threshold = loop_lag_threshold_ms
    # subscriber_failure_rate, extraction_queue_depth, projection_lag_seconds,
    # vector_delete_lag, erased_evidence — all DISABLED in c1 (L1).
    return cfg


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
        # Embedded facade runs the reduced capability set (testing_helper_marker
        # test-only; engram_per_record_key deferred M0.4+KMS); the C++ supervisor
        # is built with embedded=True (in _build_local_store_sqlite_runtime), so
        # preflight reaches READY without any Python-side global relaxation.
        # Serializes all engine entry points: routes call them from worker
        # threads (anyio to_thread) and SQLite has a single writer connection.
        # RLock because working_set() re-enters recall().
        self._lock = threading.RLock()
        self._cfg = config
        self._db_path = config.db_path
        rt = _runtime._build_local_store_sqlite_runtime(Path(config.db_path))
        rt.start()
        self._rt = rt   # the live Runtime (holds the C++ RuntimeSupervisor); the
                        # host drain reaches the supervisor through begin_drain().
        self._core = MemoryCore(rt, agent=config.agent, tenant_id=config.tenant,
                                adapter_name="dashboard", source_prefix="dash-",
                                vector_backend=config.vector_backend,
                                vector_store_path=(config.vector_store_path or None))
        # P2.o 后台维护 tick(写→读闭环的离线半边);start_background_tick 启动。
        self._tick_thread: threading.Thread | None = None
        self._tick_stop: threading.Event | None = None
        # Phase 5 — backpressure sampler (L1/L2): created once, process-lifetime.
        # outbox_lag + runtime_event_loop_lag_ms ONLY in c1 (other 5 DISABLED).
        # Debounce state (L3): a deque of the last `_debounce_ticks` verdicts.
        # Lock order (L8): engine-RLock → supervisor-mutex (via note_health). NEVER reverse.
        self._sampler = _core.HealthSampler(_build_default_sampler_config())
        self._gatherer = _core.MetricsGatherer()
        self._debounce_ticks: int = _DEFAULT_DEBOUNCE_TICKS
        self._debounce_window: collections.deque = collections.deque(
            maxlen=self._debounce_ticks)
        # Roles → adapters. Only extraction (the chat/LLM adapter MemoryCore
        # uses for remember) and embedding have live consumers today; chat is
        # wired in Phase 2c (converse). Unbound role → {} → no api_key → None /
        # stub, matching the pre-registry "no key configured" behaviour.
        self.set_llm(config.resolve_role("extraction") or {})
        self.set_chat(config.chat() or {})   # chat role (2c); falls back to extraction
        self.set_consolidation(config.resolve_role("consolidation") or {})  # #38-C role consumer
        self.set_gist_thresholds(config.gist_thresholds or {})              # #38-C v2 threshold surface
        self.rebuild_embedder(config.embedding() or {}, reembed=False)
        # dogfood sub-project A (Task 3): spool ingest worker — drains
        # ~/.starling/ingest-spool/ (jobs written by the SessionEnd hook via
        # scripts/ingest_session.py) into remember() calls. Tests inject a
        # tmp spool dir via `eng._ingest_spool = tmp_path / "spool"`.
        self._ingest_spool = Path.home() / ".starling" / "ingest-spool"
        self._ingest_thread: threading.Thread | None = None
        self._ingest_stop: threading.Event | None = None
        self._ingest_remember_ms_total = 0      # observability: see _ingest_drain_once
        self._ingest_throttle_s = 5.0           # gap after each processed job (dashboard breathing room)
        self._ingest_max_attempts = 5           # bounded retry before dead-lettering to failed/

        # dogfood 子项 B:embed 深度采样序列。HOST 独立 sqlite(唯一写者=采样器,
        # 天然单写者;与 core 的 dashboard.db 无共享写连接)。非记忆 schema,不进
        # C++ MigrationRunner。
        self._metrics_db_path = Path(self._db_path).parent / "metrics.db"
        self._metrics_retention_days = 30

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

    def set_chat(self, chat_cfg: dict) -> None:
        """Build the chat-role adapter (converse). Unbound chat falls back to
        the extraction provider's config (DashboardConfig.chat()), so this is
        O(1) reference swap like set_llm — no re-embed."""
        with self._lock:
            self._core.chat_llm = (_build_chat_adapter(chat_cfg)
                                   if chat_cfg.get("api_key") else None)

    def set_consolidation(self, cons_cfg: dict) -> None:
        """#38-C: build the consolidation-role adapter that judges NORM gists in
        offline replay. Unbound (no api_key) → None → deterministic gist (no LLM
        judge). O(1) reference swap; the NORM-gist prompt + orchestration live in
        the C++ core, this only injects the adapter."""
        with self._lock:
            self._core.consolidation_llm = (_build_chat_adapter(cons_cfg)
                                            if cons_cfg.get("api_key") else None)

    def set_gist_thresholds(self, thresholds: dict) -> None:
        """#38-C v2 threshold surface: override the NORM-gist K / T / confidence floor /
        semantic similarity_threshold (0 = off) / entity_gist_enabled (1 = on) used by
        offline replay (run_idle/run_sleep). Empty/missing keys → the C++ defaults. O(1)
        value swap; the clustering + gating logic lives in the C++ core — this only
        injects the knobs."""
        with self._lock:
            self._core.gist_thresholds = {
                k: thresholds[k]
                for k in ("min_holders", "min_replay_count", "min_confidence",
                          "similarity_threshold", "entity_gist_enabled")
                if thresholds.get(k) is not None
            } if thresholds else {}

    def rebuild_embedder(self, emb_cfg: dict, *, reembed: bool = True) -> str | None:
        """Swap the embedder; if reembed, re-process the backlog. Returns a
        human-readable warning when the immediate re-embed was rejected (the
        embedder is still swapped + rows deferred to the background tick), else
        None — so the config-save handler can tell the user instead of silently
        succeeding with broken embeddings."""
        with self._lock:
            emb = (_build_embed_adapter(emb_cfg) if emb_cfg.get("api_key")
                   else _core.StubEmbeddingAdapter(8))
            self._core.set_embedder(emb)
            if reembed:
                return self._reembed()
        return None

    def _replace_sampler(self, *,
                          outbox_lag_threshold: int = _DEFAULT_OUTBOX_LAG_THRESHOLD,
                          loop_lag_threshold_ms: float = _DEFAULT_LOOP_LAG_THRESHOLD_MS,
                          debounce_ticks: int = _DEFAULT_DEBOUNCE_TICKS) -> None:
        """Test seam: replace the sampler + gatherer with a custom config.

        Called from tests to inject low thresholds without rebuilding the engine.
        Not thread-safe (call before start_background_tick).
        """
        self._sampler = _core.HealthSampler(
            _build_default_sampler_config(
                outbox_lag_threshold=outbox_lag_threshold,
                loop_lag_threshold_ms=loop_lag_threshold_ms,
            )
        )
        self._gatherer = _core.MetricsGatherer()
        self._debounce_ticks = debounce_ticks
        self._debounce_window = collections.deque(maxlen=debounce_ticks)

    def _sample_backpressure(self, tick_started_at: float,
                              scheduled_interval: float) -> None:
        """Run the backpressure sample cycle under the engine lock (L3/L6/L7/L8).

        Steps (LOCKED block authoritative):
          L7 suppress  — skip entirely if health is DRAINING or UNREADY.
          gather        — read outbox_lag_sequence from the live DB.  On failure,
                          log + return (leave health unchanged; no spurious transition).
          L6 tick-delay — set snapshot.runtime_event_loop_lag_ms to the actual
                          elapsed time since the tick was scheduled (a host-overload
                          proxy; NOT asyncio loop lag — L6).
          evaluate      — pure C++ sampler produces a HealthDecision.
          L3 debounce   — enqueue the verdict; call note_health ONLY when the last
                          `_debounce_ticks` consecutive verdicts agree on the same
                          target_status.  Resets when the verdict changes.

        Lock order (L8): self._lock (engine-RLock) → _rt._sup mutex (via note_health).
        The reverse order NEVER occurs: note_health/begin_drain hold no engine lock.
        """
        with self._lock:
            # L7: suppress when DRAINING or UNREADY — don't fight the state machine.
            current_health = self._rt.health()
            if (current_health == _core.RuntimeHealth.DRAINING
                    or current_health == _core.RuntimeHealth.UNREADY):
                return

            # gather — wrap in try/except (DB busy, missing table, etc.).
            try:
                snapshot = self._gatherer.gather(self._rt.adapter)
            except Exception:  # noqa: BLE001 — gather failure leaves health unchanged
                logger.exception("backpressure gather failed; health unchanged")
                return

            # L6: background-tick-delay as the loop-lag proxy.
            # actual_elapsed = now - tick_started_at (seconds); convert to ms.
            # Subtract scheduled_interval to get the *over* delay (clamped >=0).
            # Example: if interval=60s and tick fires after 60.5s, delay=500ms.
            now_mono = time.monotonic()
            actual_elapsed_ms = (now_mono - tick_started_at) * 1000.0
            loop_lag_ms = max(0.0, actual_elapsed_ms - scheduled_interval * 1000.0)
            snapshot.runtime_event_loop_lag_ms = loop_lag_ms

            # evaluate — pure C++ function (no I/O, no mutex).
            decision = self._sampler.evaluate(snapshot)

            # L3 debounce: track last N verdicts; fire only when all N agree.
            verdict = decision.target_status
            # Reset deque if the verdict changed (maxlen handles window trimming).
            if self._debounce_window and self._debounce_window[-1] != verdict:
                self._debounce_window.clear()
            self._debounce_window.append(verdict)
            if (len(self._debounce_window) == self._debounce_ticks
                    and all(v == verdict for v in self._debounce_window)):
                # N consecutive same verdicts → apply to the supervisor.
                self._rt.note_health(decision)

    def sample_embed_depth(self) -> None:
        """采一个 embed 队列深度样本 → metrics.db(host,append-only + retention)。
        由后台 tick `_loop` 每轮无条件调用(紧邻 _sample_backpressure,不经
        did_work 门控——backlog/embedded 是绝对状态快照,空闲/卡死轮也要采,
        否则恰好在「backlog 卡住/增长」这个要回答的场景丢样本)。异常吞掉记
        log,绝不杀 tick(保活)。"""
        try:
            # 只读 dashboard.db 算 backlog(未 embed 的 statement 数)+ embedded 数
            with sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True) as ro:
                backlog = ro.execute(
                    "SELECT COUNT(*) FROM statements s LEFT JOIN statement_vectors v "
                    "ON v.stmt_id=s.id WHERE s.tenant_id=? AND v.stmt_id IS NULL",
                    (self._core.tenant,)).fetchone()[0]
                embedded = ro.execute(
                    "SELECT COUNT(*) FROM statement_vectors WHERE tenant_id=? AND status='embedded'",
                    (self._core.tenant,)).fetchone()[0]
            with sqlite3.connect(str(self._metrics_db_path)) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS embed_depth_samples ("
                    " ts TEXT NOT NULL, backlog INTEGER NOT NULL, embedded INTEGER NOT NULL)")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_embed_depth_ts ON embed_depth_samples(ts)")
                conn.execute("INSERT INTO embed_depth_samples(ts,backlog,embedded) VALUES(?,?,?)",
                             (_now_iso(), backlog, embedded))
                # cutoff 必须与插入的 ts 同一格式(isoformat + 微秒)——之前用
                # strftime 整秒会在同一墙钟秒内和 _now_iso() 的微秒串做字典序
                # 比较（"."排在"Z"之前），把边界行提前删掉一点点。
                cutoff = (datetime.now(timezone.utc)
                          - timedelta(days=self._metrics_retention_days)
                          ).isoformat().replace("+00:00", "Z")
                conn.execute("DELETE FROM embed_depth_samples WHERE ts < ?", (cutoff,))
                conn.commit()
        except Exception:  # noqa: BLE001 — 保活:采样失败不杀 tick
            logger.exception("embed-depth sampler failed")

    def _reembed(self) -> str | None:
        """Clear this tenant's stored vectors (dim/space changed) and re-embed.

        The re-embed makes live embedding-provider calls. A rejected/unreachable
        provider (e.g. a chat model bound to the embedding role → permanent_400)
        must NOT fail the config save with a 500: the new embedder is already
        swapped in, and the cleared rows stay in the embedding backlog for the
        background tick (with its own retry/failure tracking) to re-process once
        a valid embedding role is configured. So a failure here is logged and
        swallowed, mirroring the background tick's own non-fatal handling — and
        returned as a warning string so the save can surface it (silent success
        with broken embeddings is worse than a clear heads-up)."""
        if not self._rt.adapter.write_admitted():
            # 前台写门 follow-up(P3.c write-gate):这个 config-save 重嵌是绕过 C++ 核心的
            # 裸 sqlite 写(DELETE statement_vectors + tick_one_batch),核心门管不到 → host-side
            # gate,复用 PR #45 的 adapter 钩子。DRAINING/UNREADY 时跳过(不 DELETE),返回
            # warning(贴合本方法 str|None 契约,config-save 展示)。
            return ("re-embed skipped: runtime is draining; vectors NOT cleared "
                    "(writes are rejected during shutdown)")
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("DELETE FROM statement_vectors WHERE tenant_id = ?",
                         (self._core.tenant,))
            conn.commit()
        finally:
            conn.close()
        try:
            self._core.worker.tick_one_batch(_now_iso())
        except Exception as exc:
            logger.exception("config re-embed failed; deferred to the background tick")
            return (f"embedding provider rejected the config ({exc}); embeddings "
                    "will not generate until a valid embedding model is bound to "
                    "the embedding role (embedding models differ from chat models)")
        return None

    @property
    def llm_configured(self) -> bool:
        return self._core.llm is not None

    def _resolve_extraction(self, provider: str | None):
        """锁内调用:解析本轮抽取 adapter 为局部引用(锁外 extract 段使用)。
        取代旧 _role_override('llm', …) 的全局 slot 换入换出——拆锁后换全局
        slot 会被并发轮/后台 tick 读到错误模型(同 _resolve_chat)。"""
        if provider:
            cfg = self._cfg.resolve_provider(provider)
            if not cfg or not cfg.get("api_key"):
                raise _LLMNotConfigured(
                    f"selected provider '{provider}' is not configured")
            return _build_chat_adapter(cfg)
        return self._core.llm

    def remember(self, text: str, *, holder=None, interlocutor=None, now=None,
                 provider: str | None = None) -> dict:
        """三相落锁(方案2 + option B 收尾):belief+gf+episodic extraction 段全在
        锁外,prepare/commit 持锁。episodic LLM 已出锁(commit 内 episodic 只做纯
        DB persist)。provider 解析为局部 adapter 传入 extract/commit(避拆锁后全局
        slot 竞态,同 _converse_phased)。"""
        now = now or datetime.now(timezone.utc)
        with self._lock:                                    # ① 短:写门 + engram
            extraction = self._resolve_extraction(provider)
            if extraction is None:   # #1:fail-fast 在写 engram 前(provider 未给且抽取角色未绑)
                raise _LLMNotConfigured(
                    "remember requires an llm adapter (bind the extraction role "
                    "or pass a configured provider)")
            bundle = self._core.remember_prepare(
                text, holder=holder, interlocutor=interlocutor, now=now)
        extracted = self._core.remember_extract(bundle, llm=extraction)  # ② 锁外 LLM
        with self._lock:                                    # ③ persist + episodic + 写
            return self._core.remember_commit(bundle, extracted, llm=extraction)

    def _resolve_chat(self, provider: str | None):
        """锁内调用:解析本轮 chat 适配器为局部引用(锁外使用)。取代旧
        _role_override('chat_llm', …) 的全局 slot 换入换出——锁外生成期间
        换 slot 会被并发轮读到错误模型。"""
        if provider:
            cfg = self._cfg.resolve_provider(provider)
            if not cfg or not cfg.get("api_key"):
                raise _LLMNotConfigured(
                    f"selected provider '{provider}' is not configured")
            return _build_chat_adapter(cfg)
        return self._core.chat_llm or self._core.llm

    def _converse_phased(self, message: str, *, on_token=None, holder=None,
                         interlocutor=None, k: int = 6, now=None,
                         provider: str | None = None) -> dict:
        """converse/converse_stream 共享实现:三段化落锁,与 remember(也在
        LLM 调用期间持锁)不同——生成段(网络/延时)现在在锁外运行,只有
        prepare(recall + 组 prompt)和 commit(抽取 + 写)持锁,后台 tick 等
        并发调用不再被一次生成段整体阻塞。C++ 侧 no-write-txn-across-generate
        的结构保证不变(remember 的写事务仍是 commit 阶段,在 generate 之后)。

        prepare 与 commit 必须共用同一时刻(幂等键/召回哈希含 created_at)。"""
        now = now or datetime.now(timezone.utc)
        with self._lock:                                    # ① 短:读 + prompt
            chat = self._resolve_chat(provider)
            prepared = self._core.converse_prepare(
                message, holder=holder, interlocutor=interlocutor, k=k, now=now)
        gen_resp = self._core.generate_stream(chat, prepared.prompt, on_token)  # ② 锁外
        with self._lock:                                    # ③ 抽取 + 写
            return self._core.converse_commit(
                message, prepared, gen_resp, holder=holder,
                interlocutor=interlocutor, k=k, now=now)

    def converse(self, message: str, *, holder=None, interlocutor=None,
                 k: int = 6, now=None, provider: str | None = None) -> dict:
        return self._converse_phased(message, holder=holder,
                                     interlocutor=interlocutor, k=k, now=now,
                                     provider=provider)

    def converse_stream(self, message: str, *, on_token, holder=None,
                        interlocutor=None, k: int = 6, now=None,
                        provider: str | None = None) -> dict:
        """Streaming converse: on_token(delta:str) fires per token during the
        generation phase (WS token stream, running outside the lock). Returns
        the same dict shape as converse() (reply / statement_ids / remember_ok /
        gen_* cost); on_token only relays the reply incrementally.

        on_token runs on the C++ worker thread (the binding re-acquires the GIL
        per delta), so it must be cheap and thread-safe — the WS bridge hands
        each delta to the event loop via call_soon_threadsafe and never touches
        the DB or socket from inside the callback."""
        return self._converse_phased(message, on_token=on_token, holder=holder,
                                     interlocutor=interlocutor, k=k, now=now,
                                     provider=provider)

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

    # 片 6 干预集:全经 self._lock 串行(对单写者 + 后台 tick)。
    def approve_review(self, stmt_id: str, *, now=None) -> dict:
        with self._lock:
            return self._core.approve_review(stmt_id, now=now)

    def fulfill_commitment(self, stmt_id: str, *, now=None) -> dict:
        with self._lock:
            return self._core.fulfill_commitment(stmt_id, now=now)

    def withdraw_commitment(self, stmt_id: str, *, now=None) -> dict:
        with self._lock:
            return self._core.withdraw_commitment(stmt_id, now=now)

    def run_replay(self, mode: str, *, now=None) -> dict:
        with self._lock:
            if not self._rt.adapter.write_admitted():
                # host-side gate(P3.c write-gate follow-up):手动 replay 是重 DB 写。
                # DRAINING/UNREADY 时拒(不跑 ReplayScheduler)。返回带标记 dict —— route
                # (replay_trigger)只透传广播/返回,不访问 dict 的 key,故安全。
                return {"mode": mode, "rejected": "draining"}
            return self._core.run_replay(mode, now=now)

    def request_reconsolidation(self, stmt_id: str, *, request_id: str, now=None) -> dict:
        with self._lock:
            return self._core.request_reconsolidation(stmt_id, request_id=request_id, now=now)

    def plan_query(self, text: str, *, intent: str, perspective=None,
                   target=None, k: int = 10) -> dict:
        """P3.a1 检索规划(9 意图 + 8 标签 + 拒答);JSON-able 摘要给路由层。"""
        with self._lock:
            r = self._core.plan_query(text, intent=intent,
                                      perspective=perspective, target=target, k=k)
            rc = r.receipt
            cc = rc.candidate_counts
            # Existing 6 keys stay byte-identical (the interact page depends on
            # them — regression-pinned). Everything below is purely additive:
            # the attribution/receipt fields that were previously dropped. Only
            # fields that are actually populated are surfaced — `runtime_health`
            # is deliberately omitted (callers never set q.runtime_health, so it
            # is always the default, and showing it would violate the live-vs-
            # roadmap honesty rule).
            out = {
                "results": [{"subject": e.row.subject_id,
                             "predicate": e.row.predicate,
                             "object": e.row.object_value,
                             "score": e.score, "label": e.label.name}
                            for e in r.entries],
                "context_pack": r.context_pack,
                "abstained": r.abstained,
                "abstention_reason": rc.abstention_reason,
                "plan_steps": [{"step": s.step, "detail": s.detail}
                               for s in rc.plan_steps],
                "scopes_searched": list(rc.scopes_searched),
            }
            out["receipt"] = {
                "trace_id": rc.trace_id,
                "query_id": rc.query_id,
                "sufficiency_status": getattr(rc.sufficiency_status, "name",
                                              str(rc.sufficiency_status)),
                "filters_applied": [{"name": f.name, "value": f.value}
                                    for f in rc.filters_applied],
                "candidate_counts": {
                    "fetched": cc.fetched,
                    "returned": cc.returned,
                    "dropped_by_review": cc.dropped_by_review,
                    "dropped_by_state": cc.dropped_by_state,
                    "dropped_by_time_anchor": cc.dropped_by_time_anchor,
                    "dropped_by_evidence_erasure": cc.dropped_by_evidence_erasure,
                },
                "frontier_masked_count": rc.frontier_masked_count,
                "evidence_erased_count": rc.evidence_erased_count,
                "projection_lag_events": rc.projection_lag_events,
                "degraded_paths": [{"path": d.path, "reason": d.reason,
                                    "fallback": d.fallback}
                                   for d in rc.degraded_paths],
                "score_breakdown": [{"statement_id": s.statement_id,
                                     "base": s.base, "recency": s.recency,
                                     "salience": s.salience, "activation": s.activation,
                                     "affect_consistency": s.affect_consistency,
                                     "temporal_penalty": s.temporal_penalty,
                                     "final_score": s.final_score}
                                    for s in rc.score_breakdown],
                "skipped_scopes": [{"scope": s.scope, "reason": s.reason}
                                   for s in rc.skipped_scopes],
                "stop_reason": rc.stop_reason,
            }
            return out

    def start_background_tick(self, interval_s: float, on_tick=None) -> None:
        """周期维护线程(P2.o 运行时闭环):每 interval_s 秒跑一次 tick
        (嵌入 → 承诺触发 → grounding → 回放巩固 → 投影兜底 → 出箱收敛),
        让 remember 的内容无人工干预地变得可召回。

        - 首次 tick 在一个完整间隔之后(避免启动时与首屏请求抢引擎锁);
        - tick 持引擎 RLock,期间 UI 命令请求排队——与手动 tick 同语义;
        - on_tick(stats) 仅在本轮有实际变化(任一计数非零)时回调,调用方
          用它做 WS 广播;
        - sample_embed_depth()/_sample_backpressure() 每轮都跑,不受 on_tick
          的 did_work 门控(它们采的是绝对状态快照,空闲/卡死轮也要采);
        - 异常记日志后继续循环(网络嵌入失败不杀线程);
        - interval_s <= 0 或已启动时为 no-op。
        """
        if interval_s <= 0 or self._tick_thread is not None:
            return
        stop = threading.Event()

        def _loop() -> None:
            while not stop.wait(interval_s):
                # Record when this iteration actually started (L6: tick-delay
                # measurement).  The scheduled wake was `interval_s` after the
                # previous iteration; any surplus is the background-tick overload.
                tick_started_at = time.monotonic()
                try:
                    stats = self.tick(_now_iso())
                except Exception:  # noqa: BLE001 — 保活:单轮失败不终结调度
                    logger.exception("background tick failed")
                    continue
                # stage_timings_ms is always present (9 entries) and stages_skipped is
                # non-empty under DEGRADED — exclude both from the work-check, else
                # every idle DEGRADED tick spuriously fires a WS heartbeat (3b L8).
                did_work = any(v for k, v in stats.items()
                               if k not in ("stage_timings_ms", "stages_skipped"))
                if on_tick is not None and did_work:
                    try:
                        on_tick(stats)
                    except Exception:  # noqa: BLE001
                        logger.exception("background tick on_tick callback failed")
                # dogfood 子项 B: embed-depth 采样——UNCONDITIONAL, not did_work-gated
                # (review fix: previously only ran from app.py's did_work-gated
                # on_tick, which silently dropped exactly the "embedder stalled /
                # backlog stuck" samples this series exists to show). backlog/
                # embedded are absolute state snapshots, independent of whether
                # this round's maintenance stack did anything — sample every
                # round, same rationale as _sample_backpressure below.
                # sample_embed_depth already keeps its own try/except keepalive;
                # wrapped again here so it can never take the loop down either.
                try:
                    self.sample_embed_depth()
                except Exception:  # noqa: BLE001
                    logger.exception("embed-depth sample failed")
                # Phase 5: backpressure sample after each tick (L3/L6/L7).
                # tick_started_at was recorded before tick() so the delay includes
                # tick duration; that is intentional — a slow tick means the loop
                # is overloaded.  Failures are caught inside _sample_backpressure.
                try:
                    self._sample_backpressure(tick_started_at, interval_s)
                except Exception:  # noqa: BLE001
                    logger.exception("backpressure sample failed")

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

    # ── dogfood 子项 A(Task 3):spool ingest worker ──────────────────────
    #
    # `scripts/ingest_session.py`(Task 2)把 SessionEnd hook 的 transcript
    # 摄入 job 原子落到 `<spool>/*.json`;这里在 dashboard 进程内轮询消化:
    # claim(rename → .json.processing)→ 读 transcript → clean_turns/
    # chunk_dialogue(ingest_filter,Task 1)→ 逐块 self.remember()(持锁,见
    # 下方 docstring)→ done/ 或 failed/,可重试的失败留在 spool 根下等下一
    # 轮重试(有界,见 _ingest_max_attempts;opus review 2026-07-12 fix wave)。

    def ingest_status(self) -> dict:
        """Spool queue depths for the ingest worker — pure directory listing,
        no engine lock needed (pending/processing/done/failed are just glob
        counts; ingest_remember_ms_total is an in-memory counter, see
        _ingest_drain_once)."""
        sp = self._ingest_spool
        cnt = lambda p, pat: len(list(p.glob(pat))) if p.exists() else 0
        return {"pending": cnt(sp, "*.json"),
                "processing": cnt(sp, "*.json.processing"),
                "done": cnt(sp / "done", "*.json"),
                "failed": cnt(sp / "failed", "*.json"),
                "ingest_remember_ms_total": self._ingest_remember_ms_total}

    def _ingest_reap_stale_processing(self) -> None:
        """Startup reaper (opus review Hazard — crash strands the claim): a
        single worker means any `*.json.processing` file found here was
        claimed by a PRIOR process that died before routing it to
        done/failed/spool (claim-rename and done/failed/spool-rename are the
        only ways a `.processing` file is created or removed, and both
        happen inside _ingest_drain_once in this same process). Rename it
        back to `*.json` so the very next poll re-claims and reprocesses it
        — restores the "no data loss on crash" property. Must run once,
        BEFORE the poll loop starts (see start_ingest_worker), so it never
        races the live worker's own in-flight claim."""
        sp = self._ingest_spool
        if not sp.exists():
            return
        for stale in sp.glob("*.json.processing"):
            stale.rename(stale.with_suffix(""))    # strip the trailing ".processing"

    def _ingest_drain_once(self) -> str:
        """Drain ONE spool job: claim (atomic rename to .json.processing) ->
        read transcript -> clean/chunk -> self.remember() each chunk -> done/
        on success or once retries are exhausted, or back to the spool root
        (unclaimed, attempts incremented) on a still-retryable failure so a
        LATER poll retries it with no data loss. Returns "empty" (nothing to
        claim), "done" (the job left the spool this round — succeeded or was
        dead-lettered), or "deferred" (left back in the spool for a later
        poll — never hot-reclaimed within this call). Callers (see
        start_ingest_worker) must not busy-loop on "deferred"/"empty".

        Lock discipline (opus review Hazard 1, single-writer VIOLATION —
        user-adjudicated fix): this calls `self.remember(...)`, the
        ENGINE-wrapped method that holds `self._lock` across the ENTIRE
        call including the extraction LLM network call — same as every
        other engine writer (tick/forget/approve_review/converse_commit).
        A prior version of this worker called `self._core.remember(...)`
        directly to avoid serializing behind the lock, reasoning that the
        shared sqlite3 connection is opened SQLITE_OPEN_FULLMUTEX so a race
        could not corrupt it. That reasoning was wrong: FULLMUTEX only
        serializes individual C-API calls, not a BEGIN…COMMIT span (SQLite
        transaction state is per-*connection*, not per-thread), and
        remember's `BEGIN IMMEDIATE` (extractor.cpp TransactionGuard) stays
        open across the full multi-second extraction retry loop — a
        concurrent writer on the same connection (background tick, an HTTP
        /api/converse) hitting BEGIN while that transaction is open throws
        "cannot start a transaction within a transaction", silently
        dropping a whole maintenance tick or surfacing a spurious 500 to a
        user. That is exactly the single-writer serialization `self._lock`
        exists to enforce (this class's docstring: "SQLite has a single
        writer connection"), so bypassing it was a genuine violation, not a
        safe optimization. Holding the lock here means the worker's writes
        correctly queue behind every other engine caller (the whole point
        of a single-writer DB) — the cost is that ingest is serialized with
        the rest of the dashboard for the duration of each chunk's
        extraction. That cost is deliberately accepted and mitigated by a
        heavy throttle (`_ingest_throttle_s`, applied in start_ingest_
        worker's _loop): after every job this worker actually processes, it
        sleeps a multi-second gap so tick/HTTP get guaranteed windows even
        while churning a large backlog, instead of chaining remember() call
        after remember() call with zero gap between them.

        Failure classification (opus review Hazard 2, "zero statements ==
        failure" — WRONG): a legitimate no-facts chunk (most pure-coding
        Claude Code turns: "run the tests" / "ok" / "done") extracts zero
        statements via a successful `ok=True` empty `[]` response —
        indistinguishable, at the old binding surface, from a systemic
        extraction outage. `RememberOutcome.extraction_failed`
        (src/memory/memory_ops.cpp:78, derived from Extractor::run's
        Status::FAILED — set only when the LLM adapter/JSON-parse failed on
        EVERY retry attempt, never for a successful-but-empty extraction) is
        now surfaced through the `memory_remember` binding (bindings/python/
        bind_13_memory_ops.cpp) and passed through untouched by
        MemoryCore.remember() (python/starling/_memory_core.py) to this
        worker. NOTE (verified, not just assumed): MemoryCore.remember()
        runs belief extraction (the call whose dict this worker reads) and
        a SEPARATE general-fact `_core.memory_remember` call whose own
        extraction_failed is discarded (never merged into the returned
        dict) — so this signal reflects the belief pipeline only, not
        general-fact. Documented as a residual gap, not fixed here (fixing
        it would touch the core aggregation in _memory_core.py, out of this
        fix wave's bindings-only scope).

        A chunk with extraction_failed=False is success REGARDLESS of
        statement count (an all-chitchat job legitimately produces zero
        statements and is NOT an error). extraction_failed=True on any
        chunk, or ANY raised exception (bad job/transcript data,
        WriteGateRejected, LLMNotConfigured, network errors, a same-
        connection race, …), is a retryable failure: no more keyword-
        guessing about which errors are "transient" — every failure gets
        the same bounded number of chances (_ingest_max_attempts, tracked
        via an `attempts` counter persisted on the job JSON). Below the
        cap it is left back in the spool for a later poll; at or above it,
        the job is dead-lettered to failed/ with a `.error` sidecar
        recording the last error.
        """
        sp = self._ingest_spool
        jobs = sorted(sp.glob("*.json")) if sp.exists() else []
        if not jobs:
            return "empty"
        job_path = jobs[0]
        claimed = job_path.with_suffix(".json.processing")
        try:
            job_path.rename(claimed)               # 原子 claim
        except OSError:
            return "deferred"                       # 被别的消费者抢走(单 worker 下罕见/防御性),下轮再试
        try:
            job = json.loads(claimed.read_text())
        except Exception:                           # noqa: BLE001 — 损坏的 job 文件按空 job 处理,下方统一走有界重试
            job = {}
        try:
            tp = Path(job["transcript_path"])
            lines = tp.read_text(errors="replace").splitlines()
            project = os.path.basename((job.get("cwd") or "").rstrip("/")) or "unknown"
            chunks = chunk_dialogue(clean_turns(lines))
            extraction_failed = False
            for chunk in chunks:
                t0 = time.monotonic()
                out = self.remember(chunk, holder="self",
                                    interlocutor=f"claude-code:{project}", now=None)
                self._ingest_remember_ms_total += int((time.monotonic() - t0) * 1000)
                if out.get("extraction_failed"):
                    extraction_failed = True
            if extraction_failed:
                raise RuntimeError(
                    f"extraction_failed: extraction LLM failed on one or "
                    f"more of {len(chunks)} chunk(s)")
            (sp / "done").mkdir(exist_ok=True)
            claimed.rename(sp / "done" / job_path.name)
            return "done"
        except Exception as exc:                    # noqa: BLE001 — classify + route, never crash the worker
            attempts = int(job.get("attempts") or 0) + 1
            if attempts < self._ingest_max_attempts:
                job["attempts"] = attempts
                claimed.write_text(json.dumps(job))
                claimed.rename(job_path)            # 留 spool,下轮重扫自动重试(本次不 hot-reclaim)
                return "deferred"
            (sp / "failed").mkdir(exist_ok=True)
            claimed.rename(sp / "failed" / job_path.name)
            (sp / "failed" / (job_path.name + ".error")).write_text(str(exc)[:1000])
            return "done"

    def start_ingest_worker(self, poll_interval_s: float = 2.0) -> None:
        """Background poller (mirrors start_background_tick's thread
        template, engine.py:559): first reaps any crash-stranded
        `.processing` claim (see _ingest_reap_stale_processing), then drains
        the spool every poll_interval_s. The inner loop keeps going ONLY
        while jobs keep completing ("done") so a burst doesn't wait a full
        poll interval between jobs — throttled by `_ingest_throttle_s`
        between each, since "done" means this worker just held `self._lock`
        across a remember() call and an unthrottled hot loop could pin the
        rest of the dashboard behind a large backlog. A "deferred"/"empty"
        result falls straight through to the normal poll_interval_s sleep —
        no busy-spin on a persistently-retryable job. daemon thread; an
        exception from one job never kills the loop (caught + logged, next
        poll continues)."""
        if self._ingest_thread is not None:
            return
        self._ingest_reap_stale_processing()
        stop = threading.Event()

        def _loop() -> None:
            while not stop.wait(poll_interval_s):
                try:
                    while self._ingest_drain_once() == "done":
                        if stop.wait(self._ingest_throttle_s):
                            break
                except Exception:  # noqa: BLE001 — 保活:单个 job 失败不终结调度
                    logger.exception("ingest worker failed")

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

    def working_set(self, interlocutor, *, goal=None, token_budget=2000, holder=None) -> dict:
        """Like Memory.render_working_set but returns a JSON-able dict (API shape)."""
        with self._lock:
            cb = self._core.build_working_set(interlocutor, goal=goal,
                                              token_budget=token_budget, holder=holder)
            return {"render": cb.render(),
                    "blocks": [{"label": b.label, "content": b.content,
                                "tokens": b.token_estimate} for b in cb.blocks],
                    "truncated": cb.truncated}

    def health(self):
        """Current RuntimeHealth (read-only; forwards to the live supervisor)."""
        return self._rt.health()

    def events(self) -> list:
        """Snapshot of the supervisor transition log (read-only passthrough)."""
        return self._rt.events()

    def begin_drain(self, trigger: str = "admin_drain") -> None:
        """OV-5 / D-P2-6: enter DRAINING on host shutdown. Forwards to the live
        C++ supervisor through the Runtime handle. Acquires NOTHING extra — the
        supervisor self-locks (D3); taking self._lock here would let a slow
        in-flight converse/tick block shutdown drain."""
        self._rt.begin_drain(trigger)

    def close(self) -> None:
        self.stop_ingest_worker()
        self.stop_background_tick()
        self._core.close()


# Back-compat alias: routes and tests import the underscore name from here.
_LLMNotConfigured = LLMNotConfigured
