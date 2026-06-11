"""Shared embedded-runtime command core for `starling.Memory` and
`starling.dashboard.DashboardEngine`.

Both surfaces previously carried near-identical copies of remember / recall /
tick / working-set assembly (~115 duplicated lines) and had already drifted
twice: the engine's working set lost the affect section, and the facade used a
non-deterministic idempotency key. This module is the single implementation;
the two wrappers keep only their construction policy (stub vs config-driven
adapters) and output shapes (dataclasses/ContextBlock vs JSON dicts).

NOT thread-safe by itself — DashboardEngine serializes calls with its own lock;
the embedded facade is single-user by contract.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from starling import _core
from starling.evidence.inputs import for_user_input
from starling.extractor.prompts import EXTRACTION_PROMPT


class LLMNotConfigured(RuntimeError):
    """remember() requires an llm adapter (make_stub_llm / make_openai_llm /
    make_anthropic_llm, or the dashboard provider factory)."""


def parse_now(now: Optional[str]) -> datetime:
    """Coerce an optional ISO-8601 string into a tz-aware datetime.

    `for_user_input` expects a datetime (it formats via `_iso`). Default to
    the current UTC time when no override is given.
    """
    if now is None:
        return datetime.now(timezone.utc)
    s = now.replace("Z", "+00:00") if now.endswith("Z") else now
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class MemoryCore:
    """Command core over ONE runtime/WAL writer.

    `adapter_name`/`source_prefix` parametrize the engram source identity so
    the facade ("facade"/"mem-") and the dashboard ("dashboard"/"dash-") keep
    their historical idempotency namespaces.
    """

    def __init__(self, rt, *, agent: str, tenant_id: str, llm=None,
                 adapter_name: str, source_prefix: str):
        self.rt = rt
        self.agent = agent
        self.tenant = tenant_id
        self.llm = llm
        self.adapter_name = adapter_name
        self.source_prefix = source_prefix
        # Shared connection handle for the extractor (keep-alive in binding).
        self.conn = rt.adapter.connection()
        self.idx = _core.SqliteBlobVectorIndex()
        self.policy = _core.PolicyEngine(rt.adapter)
        self.emb = None
        self.semantic = None
        self.completor = None
        self.worker = None

    def set_embedder(self, emb) -> None:
        """(Re)build the embedder-dependent components as one consistent set,
        so the embedder that WRITES vectors (EmbeddingWorker) and the one that
        READS them (SemanticRetriever) never diverge."""
        self.emb = emb
        self.semantic = _core.SemanticRetriever(self.rt.adapter, emb, self.idx)
        self.completor = _core.PatternCompletor(self.rt.adapter, self.semantic)
        self.worker = _core.EmbeddingWorker(self.rt.adapter, emb, self.idx)

    def remember(self, text: str, *, holder=None, interlocutor=None, now=None) -> dict:
        if self.llm is None:
            raise LLMNotConfigured(
                "remember requires an llm adapter "
                "(make_stub_llm / make_openai_llm / make_anthropic_llm)")
        holder = holder or self.agent
        payload = text.encode("utf-8")
        created_at = parse_now(now)
        inp = for_user_input(
            tenant_id=self.tenant,
            adapter_name=self.adapter_name,
            adapter_version="1",
            # sha256 (not Python hash()): hash() is randomized per process via
            # PYTHONHASHSEED — the idempotency key derived from source_item_id
            # must be content-deterministic across processes.
            source_item_id=self.source_prefix + hashlib.sha256(payload).hexdigest()[:16],
            source_version="1",
            payload_bytes=payload,
            privacy_class=_core.PrivacyClass.INTERNAL,
            retention_mode=_core.EngramRetentionMode.AUDIT_RETAIN,
            created_at=created_at,
        )
        out = self.rt.bus.append_evidence(inp, None)
        kind = out["kind"]
        if kind not in ("accepted", "idempotent"):
            return {"engram_ref": "", "statement_ids": [], "outcome": kind}
        engram_ref = out["engram_ref"].id
        r = _core.Extractor(self.conn, self.llm, EXTRACTION_PROMPT).run(
            engram_ref, payload, holder, self.tenant, {}, interlocutor or "")
        return {"engram_ref": engram_ref,
                "statement_ids": list(r.accepted_statement_ids),
                "outcome": kind}

    def recall(self, query: str, *, perspective: str = "first_person",
               k: int = 10, mode: str = "semantic") -> list:
        """mode="semantic" — vector cosine via SemanticRetriever.vector_recall;
        mode="completion" — associative spreading via PatternCompletor."""
        if mode == "completion":
            res = self.completor.complete(_core.PatternCompletionParams(
                tenant_id=self.tenant, holder_id=self.agent,
                holder_perspective=perspective, cue_text=query, result_k=k))
            return [{"row": s.row, "score": s.activation} for s in res.rows]
        res = self.semantic.vector_recall(_core.SemanticRetrieverParams(
            tenant_id=self.tenant, holder_id=self.agent,
            holder_perspective=perspective, query_text=query, k=k))
        return [{"row": s.row, "score": s.score} for s in res.rows]

    def tick(self, now: str) -> dict:
        """Advance background workers: embed pending + fire due commitments +
        flush grounding 滞后事件 (P2.j)."""
        es = self.worker.tick_one_batch(now)
        ps = self.policy.tick(now)
        _core._common_ground_tick(self.rt.adapter, now)
        embedded = es.embedded if hasattr(es, "embedded") else (es if isinstance(es, int) else 0)
        return {"embedded": embedded, "fired": ps.fired, "broken": ps.broken,
                "auto_withdrawn": ps.auto_withdrawn}

    def build_working_set(self, interlocutor, *, goal=None, token_budget: int = 2000):
        """Assemble the prompt-ready ContextBlock (P2.e): persona /
        common_ground / relevant_memories / pending_commitments / affect under
        an approximate token budget. A `fired` commitment surfaces as a ⚠ DUE
        reminder (B3 closure).

        核心逻辑(五源汇集 + 预算分配 + 截断 + 渲染)在 C++
        `starling::hippocampus::build_working_set`(2026-06-11 边界归位);
        这里只是绑定转发——Python 层不持有 Working Set 语义。
        """
        return _core.build_working_set(
            self.rt.adapter, self.semantic,
            tenant_id=self.tenant, agent_id=self.agent,
            interlocutor=interlocutor, goal=goal or "",
            token_budget=token_budget)

    def close(self) -> None:
        # The SqliteAdapter is closed when its runtime/handle is GC'd; nothing
        # to release explicitly in the embedded core.
        self.conn = None
