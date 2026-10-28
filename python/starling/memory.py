"""Starling Memory — public application-surface facade (P2.e).

`Memory.open` builds a local-store SQLite runtime (after relaxing the M0.3
preflight gate). The remember / recall / tick / working-set command logic lives
in `starling._memory_core.MemoryCore` — a single implementation shared with the
dashboard's `DashboardEngine`, so the two surfaces cannot drift. This facade
keeps only construction policy (deterministic stub embedder, llm injected by
the caller) and the dataclass/ContextBlock output shapes.

Offline determinism comes from `make_stub_llm` (`_core.FakeLLMAdapter` with a
canned JSON-array default response — no network). `make_openai_llm` builds the
real `_core.OpenAIAdapter`; its API key is sourced from the environment only
(`OPENAI_API_KEY`), never a function parameter, log line, or hardcoded value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from starling import _core
from starling import runtime as _runtime
from starling._memory_core import MemoryCore, RecallDegradedError


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
                    timeout_ms: int = 0, max_retries: Optional[int] = None,
                    max_tokens: int = 0):
    """Production LLM adapter (`_core.OpenAIAdapter`).

    The API key is read from the environment (`OPENAI_API_KEY`) by the C++
    adapter — it is never accepted as a parameter, logged, or hardcoded here.
    Starts from `OpenAIAdapterConfig.from_env()` so env-provided defaults
    (base_url / model / timeouts) are honoured, then overrides only the
    fields the caller explicitly set. `max_retries` is judged by `is None`,
    not truthiness: `None` (omitted) keeps the C++ default (3), while any int,
    including 0 ("never retry"), is applied as given.
    """
    cfg = _core.OpenAIAdapterConfig.from_env()
    if model:
        cfg.model = model
    if base_url:
        cfg.base_url = base_url
    if timeout_ms:
        cfg.timeout_ms = timeout_ms
    if max_retries is not None:
        cfg.max_retries = max_retries
    if max_tokens:
        cfg.max_tokens = max_tokens
    return _core.OpenAIAdapter(cfg)


def make_openai_embedder(*, model: str, base_url: str, dim: int,
                         timeout_ms: int, max_retries: Optional[int] = None):
    """Production embedder (`_core.OpenAIEmbeddingAdapter`) for `Memory.open`.

    Built like `make_openai_llm`: the API key is read from the environment
    (`OPENAI_API_KEY`) by the C++ config and is never a parameter. Starts from
    `OpenAIEmbeddingConfig.from_env()`, then sets `model`, `base_url`, `dim`
    and `timeout_ms` unconditionally. `max_retries` is judged by `is None`, not
    truthiness: `None` (omitted) keeps the C++ default (3), while any int,
    including 0 ("never retry"), is applied as given.
    """
    cfg = _core.OpenAIEmbeddingConfig.from_env()
    cfg.model = model
    cfg.base_url = base_url
    cfg.dim = dim
    cfg.timeout_ms = timeout_ms
    if max_retries is not None:
        cfg.max_retries = max_retries
    return _core.OpenAIEmbeddingAdapter(cfg)


def make_anthropic_llm(*, model: str = "", base_url: str = "",
                       timeout_ms: int = 0, max_retries: int = 0,
                       max_tokens: int = 0):
    """Production Anthropic LLM adapter (`_core.AnthropicAdapter`).

    The API key is read from the environment (`ANTHROPIC_API_KEY`) by the C++
    adapter — never accepted as a parameter, logged, or hardcoded here. Starts
    from `AnthropicAdapterConfig.from_env()`, then overrides only the fields the
    caller explicitly set.
    """
    cfg = _core.AnthropicAdapterConfig.from_env()
    if model:
        cfg.model = model
    if base_url:
        cfg.base_url = base_url
    if timeout_ms:
        cfg.timeout_ms = timeout_ms
    if max_retries:
        cfg.max_retries = max_retries
    if max_tokens:
        cfg.max_tokens = max_tokens
    return _core.AnthropicAdapter(cfg)


@dataclass
class RememberResult:
    engram_ref: str
    statement_ids: list = field(default_factory=list)
    outcome: str = ""
    # opus review fix wave (2026-07-12, dashboard ingest worker Task 3): the
    # memory_remember binding now surfaces RememberOutcome.extraction_failed
    # (src/memory/memory_ops.cpp:78) so callers can distinguish a genuine
    # extraction-LLM failure from a legitimate zero-statement extraction —
    # add the field here too so this facade's RememberResult(**dict) forward
    # doesn't reject the new key (same landmine as TickStats/TickOutcome).
    extraction_failed: bool = False
    failure_category: str = ""
    failure_detail: str = ""
    catalog_version: str = ""
    source_preserved: bool = False
    structured_claims_persisted: bool = False
    accepted_by_predicate: dict = field(default_factory=dict)
    rejected_by_predicate: dict = field(default_factory=dict)


@dataclass
class TickStats:
    embedded: int = 0
    fired: int = 0
    broken: int = 0
    auto_withdrawn: int = 0
    # P2.o 周期维护:回放巩固 + 投影兜底 + 出箱收敛(memoryops::tick_all)。
    replay_sampled: int = 0
    consolidated: int = 0
    ttl_archived: int = 0
    projected: int = 0
    dispatched: int = 0
    # P3.c1 Phase 3b: per-stage wall-clock timings — list of {"stage": str, "ms": int}.
    stage_timings_ms: list = field(default_factory=list)
    # P3.c LW.3: stages skipped by load-shedding this tick (same labels as
    # stage_timings_ms); EXCLUDED from the engine idle-heartbeat work-check.
    stages_skipped: list = field(default_factory=list)


@dataclass(frozen=True)
class PendingEvent:
    """One `events` row still in state 'pending': a keyed write that was recorded
    but not yet committed. `seq` is the per-tenant sequence number (starts at 0);
    `failure_category` is '' until a failed attempt records one."""
    key: str
    text: str
    interlocutor: str
    seq: int
    failure_category: str


@dataclass
class EmbedStats:
    """Counts from `Memory.embed_pending`: statements embedded / statements whose
    embedding failed (a later call retries failed rows, up to the retry cap)."""
    embedded: int = 0
    failed: int = 0


class Memory:
    """Public facade over the Starling write path."""

    def __init__(self, rt, *, agent: str, tenant_id: str, llm, extraction=None,
                 embedder=None):
        # `_rt` stays addressable: examples/quickstart.py and tests use
        # `mem._rt.adapter` as the single WAL adapter for C++ engine calls.
        self._rt = rt
        self._core = MemoryCore(rt, agent=agent, tenant_id=tenant_id, llm=llm,
                                adapter_name="facade", source_prefix="mem-",
                                extraction=extraction)
        # Default: deterministic stub embedder (no network). A caller-supplied
        # embedder (e.g. `make_openai_embedder(...)`) replaces it wholesale via
        # `set_embedder`, so the writing worker and the reading retriever are
        # built from the same instance.
        self._core.set_embedder(
            _core.StubEmbeddingAdapter(8) if embedder is None else embedder)

    @classmethod
    def open(cls, db_path, *, agent: str = "self", tenant_id: str = "default",
             llm=None, extraction=None, embedder=None) -> "Memory":
        # The embedded single-process facade runs the reduced capability set
        # (testing_helper_marker is test-only; engram_per_record_key is deferred
        # to M0.4+KMS). _build_local_store_sqlite_runtime builds the C++
        # RuntimeSupervisor with embedded=True, which waives those deferred caps
        # so preflight reaches READY — no Python-side global relaxation needed.
        rt = _runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        return cls(rt, agent=agent, tenant_id=tenant_id, llm=llm,
                   extraction=extraction, embedder=embedder)

    def remember(self, text: str, *, holder: Optional[str] = None,
                 interlocutor: Optional[str] = None,
                 now: Optional[str] = None) -> RememberResult:
        return RememberResult(**self._core.remember(
            text, holder=holder, interlocutor=interlocutor, now=now))

    def recall(self, query: str, *, perspective: str = "first_person",
               k: int = 10, mode: str = "semantic", holder: str | None = None,
               strict: bool = False, include_volatile: bool = False) -> list:
        """Retrieve memories by semantic similarity or pattern completion.

        mode="semantic"    — vector cosine search via SemanticRetriever.vector_recall
        mode="completion"  — associative spreading via PatternCompletor.complete

        holder: whose memory to recall (default: this Memory's agent). Must match
        the holder the statements were written under.
        strict: raise RecallDegradedError when the query embedding failed
        (semantic mode) instead of silently returning lexical-only results.
        strict=True with mode="completion" raises ValueError.
        include_volatile: also return statements still in consolidation_state
        'volatile' (embedded via embed_pending but not yet promoted by tick),
        at the cost of possible near-duplicates. Widens only the consolidation
        state; the review guard and holder/perspective predicates are unchanged.
        include_volatile=True with mode="completion" raises ValueError.
        """
        return self._core.recall(query, perspective=perspective, k=k, mode=mode,
                                 holder=holder, strict=strict,
                                 include_volatile=include_volatile)

    def query(self, text: str = "", *, intent: str = "FACT_LOOKUP",
              perspective: str | None = None, target: str | None = None,
              subject: str | None = None, predicate: str | None = None,
              k: int = 10, now=None) -> dict:
        """检索规划入口(P3.a1):9 种意图 + Context Pack 8 标签 + 可审计回执。

        返回 dict:entries(row/score/label)、context_pack(LLM-ready 文本)、
        abstained、abstention_reason、receipt(完整回执对象)。
        """
        r = self._core.plan_query(text, intent=intent, perspective=perspective,
                                  target=target, subject=subject,
                                  predicate=predicate, k=k, now=now)
        # 左脑原文条目（形态 S §4.6）：与语句条目并列返回，用 kind 区分。
        # 语句条目补 kind="statement" 保持向后兼容——旧调用方读 row/score/label
        # 不受影响。lane 关闭时 source_entries 为空，结构与本改动前等价。
        return {
            "entries": [{"row": e.row, "score": e.score,
                         "label": e.label.name, "kind": "statement"}
                        for e in r.entries],
            "source_entries": [{"kind": "source",
                                "engram_ref": s.engram_ref,
                                "clause_id": s.clause_id,
                                "speaker": s.speaker,
                                "session_id": s.session_id,
                                "observed_at": s.observed_at,
                                "text": s.text,
                                "provenance": s.provenance,
                                "score": s.score,
                                "rrf_score": s.rrf_score,
                                "rrf_rank": s.rrf_rank}
                               for s in getattr(r, "source_entries", ())],
            "context_pack": r.context_pack,
            "abstained": r.abstained,
            "abstention_reason": r.receipt.abstention_reason,
            "receipt": r.receipt,
        }

    def latest_event_location(self, theme: str) -> str:
        """Ground-truth current location of `theme` (sub-project A, episodic).

        Returns the location of the highest-seq OCCURRED event about `theme`,
        or "" if no event mentions it. After remembering "Sally puts her ball
        in the basket … Anne moves the ball to the box", this returns "box".
        """
        return self._core.latest_event_location(theme)

    def tick(self, now: str = "2026-06-01T10:00:00Z") -> TickStats:
        """Advance background workers: embed pending statements + fire due commitments."""
        return TickStats(**self._core.tick(now))

    def embed_pending(self, now: str) -> EmbedStats:
        """Run only the embedding stage so new statements become recallable.

        Unlike `tick`, this skips commitments, replay/consolidation, projection
        and outbox dispatch, and ignores health gating. Embedding failures are
        counted in `EmbedStats.failed`, not raised.
        """
        return EmbedStats(**self._core.embed_pending(now))

    def next_seq(self) -> int:
        """Next free event sequence number for this tenant.

        0 on an empty library, so the first event's `seq` is 0. Abandoned events
        count, so a number is never reused.
        """
        return self._core.next_seq()

    def pending_events(self) -> list[PendingEvent]:
        """Events recorded in state 'pending', ordered by `seq` ascending."""
        return [PendingEvent(**row) for row in self._core.pending_events()]

    def render_working_set(self, interlocutor, *, goal=None, token_budget: int = 2000):
        """Assemble a prompt-ready ContextBlock from memory (P2.e).

        Five sections — persona / common_ground / relevant_memories /
        pending_commitments / affect — under an approximate token budget. A
        `fired` commitment surfaces as a ⚠ DUE reminder (B3 closure).
        """
        return self._core.build_working_set(interlocutor, goal=goal,
                                            token_budget=token_budget)

    def close(self) -> None:
        self._core.close()
