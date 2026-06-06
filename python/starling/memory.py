"""Starling Memory — public application-surface facade (P2.e).

`Memory.open` builds a local-store SQLite runtime (after relaxing the M0.3
preflight gate), and `remember(text)` runs the production write path:

    BusFacade.append_evidence(EngramInput)   # creates/dedupes the engram
        -> _core.Extractor(connection, llm, EXTRACTION_PROMPT).run(...)  # extracts statements

Offline determinism comes from `make_stub_llm` (`_core.FakeLLMAdapter` with a
canned JSON-array default response — no network). `make_openai_llm` builds the
real `_core.OpenAIAdapter`; its API key is sourced from the environment only
(`OPENAI_API_KEY`), never a function parameter, log line, or hardcoded value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from starling import _core
from starling import runtime as _runtime
from starling.evidence.inputs import for_user_input
from starling.extractor.prompts import EXTRACTION_PROMPT


def make_stub_llm(*, default_response: str, responses: Optional[dict] = None):
    """Offline deterministic LLM adapter.

    `default_response` is a canned JSON array response answering any prompt
    whose hash is not explicitly mapped in `responses` (hash -> canned JSON
    array response). The FakeLLMAdapter ignores the prompt, so tests drive
    behavior purely via the canned response content. Drives `_core.Extractor`
    with zero network calls. Example `default_response`::

        '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
        '"subject":"cog-self","predicate":"responsible_for","object":"auth",'
        '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
    """
    llm = _core.FakeLLMAdapter()
    # binding: set_default_response(raw_xml, ok=True, error="")
    llm.set_default_response(default_response, True, "")
    for h, resp in (responses or {}).items():
        # binding: set_response(hash, raw_xml, ok=True, error="")
        llm.set_response(h, resp, True, "")
    return llm


def make_openai_llm(*, model: str = "gpt-4o-mini", base_url: str = "",
                    timeout_ms: int = 0, max_retries: int = 0):
    """Production LLM adapter (`_core.OpenAIAdapter`).

    The API key is read from the environment (`OPENAI_API_KEY`) by the C++
    adapter — it is never accepted as a parameter, logged, or hardcoded here.
    Starts from `OpenAIAdapterConfig.from_env()` so env-provided defaults
    (base_url / model / timeouts) are honoured, then overrides only the
    fields the caller explicitly set.
    """
    cfg = _core.OpenAIAdapterConfig.from_env()
    if model:
        cfg.model = model
    if base_url:
        cfg.base_url = base_url
    if timeout_ms:
        cfg.timeout_ms = timeout_ms
    if max_retries:
        cfg.max_retries = max_retries
    return _core.OpenAIAdapter(cfg)


@dataclass
class RememberResult:
    engram_ref: str
    statement_ids: list = field(default_factory=list)
    outcome: str = ""


@dataclass
class TickStats:
    embedded: int = 0
    fired: int = 0
    broken: int = 0
    auto_withdrawn: int = 0


class Memory:
    """Public facade over the Starling write path."""

    def __init__(self, rt, *, agent: str, tenant_id: str, llm):
        self._rt = rt
        self._agent = agent
        self._tenant = tenant_id
        self._llm = llm
        # Shared connection handle for the extractor (keep-alive in binding).
        self._conn = rt.adapter.connection()
        # Retrieval / embedding components (shared embedder + index for consistency).
        self._emb = _core.StubEmbeddingAdapter(8)
        self._idx = _core.SqliteBlobVectorIndex()
        self._semantic = _core.SemanticRetriever(rt.adapter, self._emb, self._idx)
        self._completor = _core.PatternCompletor(rt.adapter, self._semantic)
        self._worker = _core.EmbeddingWorker(rt.adapter, self._emb, self._idx)
        self._policy = _core.PolicyEngine(rt.adapter)

    @classmethod
    def open(cls, db_path, *, agent: str = "self", tenant_id: str = "default",
             llm=None) -> "Memory":
        # The embedded single-process facade can't satisfy the full local-store
        # preflight (testing_helper_marker is test-only; engram_per_record_key is
        # deferred to M0.4+KMS); relax to the embedded subset so it reaches READY.
        _runtime.relax_preflight_for_embedded()
        rt = _runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        return cls(rt, agent=agent, tenant_id=tenant_id, llm=llm)

    def remember(self, text: str, *, holder: Optional[str] = None,
                 interlocutor: Optional[str] = None,
                 now: Optional[str] = None) -> RememberResult:
        if self._llm is None:
            raise RuntimeError(
                "Memory.remember requires an llm adapter "
                "(make_stub_llm / make_openai_llm)"
            )
        holder = holder or self._agent
        payload = text.encode("utf-8")
        created_at = _parse_now(now)

        inp = for_user_input(
            tenant_id=self._tenant,
            adapter_name="facade",
            adapter_version="1",
            source_item_id="mem-" + str(abs(hash(text))),
            source_version="1",
            payload_bytes=payload,
            privacy_class=_core.PrivacyClass.INTERNAL,        # enum member (no NORMAL)
            retention_mode=_core.EngramRetentionMode.AUDIT_RETAIN,  # enum member (no VERBATIM)
            created_at=created_at,
        )
        out = self._rt.bus.append_evidence(inp, None)
        kind = out["kind"]
        if kind not in ("accepted", "idempotent"):
            return RememberResult(engram_ref="", statement_ids=[], outcome=kind)

        engram_ref = out["engram_ref"].id
        ext = _core.Extractor(self._conn, self._llm, EXTRACTION_PROMPT)
        r = ext.run(engram_ref, payload, holder, self._tenant, {}, interlocutor or "")
        return RememberResult(
            engram_ref=engram_ref,
            statement_ids=list(r.accepted_statement_ids),
            outcome=kind,
        )

    def recall(self, query: str, *, perspective: str = "first_person",
               k: int = 10, mode: str = "semantic") -> list:
        """Retrieve memories by semantic similarity or pattern completion.

        mode="semantic"    — vector cosine search via SemanticRetriever.vector_recall
        mode="completion"  — associative spreading via PatternCompletor.complete
        """
        if mode == "completion":
            res = self._completor.complete(_core.PatternCompletionParams(
                tenant_id=self._tenant,
                holder_id=self._agent,
                holder_perspective=perspective,
                cue_text=query,
                result_k=k,
            ))
            return [{"row": s.row, "score": s.activation} for s in res.rows]
        # Default: semantic vector recall
        res = self._semantic.vector_recall(_core.SemanticRetrieverParams(
            tenant_id=self._tenant,
            holder_id=self._agent,
            holder_perspective=perspective,
            query_text=query,
            k=k,
        ))
        return [{"row": s.row, "score": s.score} for s in res.rows]

    def tick(self, now: str = "2026-06-01T10:00:00Z") -> TickStats:
        """Advance background workers: embed pending statements + fire due commitments.

        Returns a TickStats aggregating results from EmbeddingWorker.tick_one_batch
        and PolicyEngine.tick.
        """
        es = self._worker.tick_one_batch(now)
        ps = self._policy.tick(now)
        _core._common_ground_tick(self._rt.adapter, now)   # P2.j: flush grounding 滞后事件
        # EmbeddingWorker.tick_one_batch returns EmbeddingStats (has .embedded int)
        embedded = es.embedded if hasattr(es, "embedded") else (es if isinstance(es, int) else 0)
        return TickStats(
            embedded=embedded,
            fired=ps.fired,
            broken=ps.broken,
            auto_withdrawn=ps.auto_withdrawn,
        )

    def render_working_set(self, interlocutor, *, goal=None, token_budget: int = 2000):
        """Assemble a prompt-ready ContextBlock from memory (P2.e).

        Composes five sections — persona / common_ground / relevant_memories /
        pending_commitments / affect — under an approximate token budget. A
        `fired` commitment surfaces as a ⚠ DUE reminder (B3 closure).
        """
        from starling import working_set as _ws
        adapter = self._rt.adapter
        sections = {}
        # persona
        pv = _core.PersonaContainer(adapter).read(self._tenant, self._agent)
        if pv.found and pv.dimensions:
            sections["persona"] = "; ".join(f"{k}: {v}" for k, v in pv.dimensions.items())
        # common ground
        _pair = sorted([self._agent, interlocutor])
        cg = _core.CommonGroundContainer(adapter).read(self._tenant, f"{_pair[0]}::{_pair[1]}")
        if cg.found and cg.grounded:
            sections["common_ground"] = "\n".join("- " + g for g in cg.grounded)
        # relevant memories
        hits = self.recall(goal, mode="semantic", k=5) if goal else []
        if hits:
            sections["relevant_memories"] = "\n".join(
                "- " + f"{h['row'].subject_id} {h['row'].predicate} {h['row'].object_value}" for h in hits)
        # pending commitments (fired → ⚠)
        pend = _core.CommitmentEngine(adapter).pending(self._tenant, self._agent, interlocutor)
        if pend:
            lines = []
            for c in pend:
                tag = "⚠ DUE: " if c.fired else ""
                base = f"- {tag}{c.subject_id} {c.predicate} {c.object_value}"
                lines.append(base + (f" (by {c.deadline})" if c.deadline else ""))
            sections["pending_commitments"] = "\n".join(lines)
        # affect (peak salience among relevant memories)
        peak = 0.0
        have = False
        for h in hits:
            aj = h["row"].affect_json
            if aj and aj != "{}":
                av = _core.affect_parse_json(aj)
                s = _core.affect_salience(av, 1.0)
                if s > peak:
                    peak, have = s, True
        if have:
            sections["affect"] = f"salience {peak:.2f}"
        return _ws.assemble(sections, token_budget)

    def close(self) -> None:
        # The SqliteAdapter is closed when its runtime/handle is GC'd; nothing
        # to release explicitly in the embedded facade.
        self._conn = None


def _parse_now(now: Optional[str]) -> datetime:
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
