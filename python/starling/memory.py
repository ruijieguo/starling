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
from starling._memory_core import MemoryCore


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


def make_anthropic_llm(*, model: str = "", base_url: str = "",
                       timeout_ms: int = 0, max_retries: int = 0):
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
    return _core.AnthropicAdapter(cfg)


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
    # P2.o 周期维护:回放巩固 + 投影兜底 + 出箱收敛(memoryops::tick_all)。
    replay_sampled: int = 0
    consolidated: int = 0
    ttl_archived: int = 0
    projected: int = 0
    dispatched: int = 0


class Memory:
    """Public facade over the Starling write path."""

    def __init__(self, rt, *, agent: str, tenant_id: str, llm):
        # `_rt` stays addressable: examples/quickstart.py and tests use
        # `mem._rt.adapter` as the single WAL adapter for C++ engine calls.
        self._rt = rt
        self._core = MemoryCore(rt, agent=agent, tenant_id=tenant_id, llm=llm,
                                adapter_name="facade", source_prefix="mem-")
        # Embedded facade: deterministic stub embedder (no network).
        self._core.set_embedder(_core.StubEmbeddingAdapter(8))

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
        return RememberResult(**self._core.remember(
            text, holder=holder, interlocutor=interlocutor, now=now))

    def recall(self, query: str, *, perspective: str = "first_person",
               k: int = 10, mode: str = "semantic") -> list:
        """Retrieve memories by semantic similarity or pattern completion.

        mode="semantic"    — vector cosine search via SemanticRetriever.vector_recall
        mode="completion"  — associative spreading via PatternCompletor.complete
        """
        return self._core.recall(query, perspective=perspective, k=k, mode=mode)

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
        return {
            "entries": [{"row": e.row, "score": e.score,
                         "label": e.label.name} for e in r.entries],
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
