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

import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from starling import _core
from starling import runtime as _runtime
from starling.evidence.inputs import for_user_input
from starling.extractor.prompts import EXTRACTION_PROMPT


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@contextmanager
def _env_swap(api_key: str, base_url: str, *,
              key_env: str = "OPENAI_API_KEY", base_env: str = "OPENAI_BASE_URL"):
    """Temporarily set <key_env>/<base_env> so the adapter's from_env() captures them.

    Parametric over the env-var names so the Anthropic path can inject
    ANTHROPIC_API_KEY/ANTHROPIC_BASE_URL through the same transient swap.
    """
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

    def remember(self, text: str, *, holder=None, interlocutor=None, now=None) -> dict:
        if self.llm is None:
            raise _LLMNotConfigured()
        holder = holder or self._agent
        payload = text.encode("utf-8")
        created_at = _parse_now(now)
        inp = for_user_input(
            tenant_id=self._tenant, adapter_name="dashboard", adapter_version="1",
            source_item_id="dash-" + hashlib.sha256(payload).hexdigest()[:16], source_version="1",
            payload_bytes=payload, privacy_class=_core.PrivacyClass.INTERNAL,
            retention_mode=_core.EngramRetentionMode.AUDIT_RETAIN, created_at=created_at,
        )
        out = self._rt.bus.append_evidence(inp, None)
        kind = out["kind"]
        if kind not in ("accepted", "idempotent"):
            return {"engram_ref": "", "statement_ids": [], "outcome": kind}
        engram_ref = out["engram_ref"].id
        r = _core.Extractor(self._conn, self.llm, EXTRACTION_PROMPT).run(engram_ref, payload, holder, self._tenant, {}, interlocutor or "")
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
        _core._common_ground_tick(self._rt.adapter, now)   # P2.j: flush grounding 滞后事件（与 Memory.tick 对称）
        embedded = es.embedded if hasattr(es, "embedded") else (es if isinstance(es, int) else 0)
        return {"embedded": embedded, "fired": ps.fired, "broken": ps.broken,
                "auto_withdrawn": ps.auto_withdrawn}

    def working_set(self, interlocutor, *, goal=None, token_budget=2000) -> dict:
        """Like Memory.render_working_set but returns a JSON-able dict (API shape)."""
        from starling import working_set as _ws
        adapter = self._rt.adapter
        sections = {}
        pv = _core.PersonaContainer(adapter).read(self._tenant, self._agent)
        if pv.found and pv.dimensions:
            sections["persona"] = "; ".join(f"{k}: {v}" for k, v in pv.dimensions.items())
        _pair = sorted([self._agent, interlocutor])
        cg = _core.CommonGroundContainer(adapter).read(self._tenant, f"{_pair[0]}::{_pair[1]}")
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
