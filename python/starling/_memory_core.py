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

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from starling import _core
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT
from starling.extractor.config import ExtractionConfig


def _build_policy(extraction):
    """Build a _core.ValidationPolicy from an ExtractionConfig."""
    pol = _core.ValidationPolicy()
    pol.extra_core_predicates = list(extraction.extra_core_predicates)
    pol.confidence_drop_floor = extraction.confidence_drop_floor
    pol.weak_inference_floor = extraction.weak_inference_floor
    return pol


def _make_vector_index(backend: str, dim: int, store_path):
    """P3.b1 phase 5 Task 5.3:按 vector_backend 创建向量后端句柄(回滚留好)。

    sqlite(默认):SqliteBlobVectorIndex(暴力 cosine + SQL scope,任意维)。
    zvec:ZvecVectorIndex(HNSW,需 STARLING_VECTOR_ZVEC 构建的 _core);collection
         维度固定,需 store_path + dim。向量数据持久化在 store_path,重建句柄即 reopen。
    """
    if backend == "zvec":
        if not hasattr(_core, "ZvecVectorIndex"):
            raise RuntimeError(
                "vector_backend='zvec' requires a STARLING_VECTOR_ZVEC build of _core")
        path = store_path or os.path.expanduser("~/.starling/vectors")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return _core.ZvecVectorIndex(path, int(dim))
    return _core.SqliteBlobVectorIndex()


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
                 adapter_name: str, source_prefix: str,
                 vector_backend: str = "sqlite", vector_store_path=None,
                 extraction: "ExtractionConfig | None" = None):
        self.rt = rt
        self.agent = agent
        self.tenant = tenant_id
        self.llm = llm
        self.adapter_name = adapter_name
        self.source_prefix = source_prefix
        self._extraction = extraction or ExtractionConfig()
        # Shared connection handle for the extractor (keep-alive in binding).
        self.conn = rt.adapter.connection()
        # 向量后端在 set_embedder 时按 embedder 维度创建(zvec collection 需固定 dim)。
        self._vector_backend = vector_backend
        self._vector_store_path = vector_store_path
        self.idx = None
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
        # 按后端 + embedder 维度创建向量句柄(数据持久化,重建句柄即 reopen)。
        self.idx = _make_vector_index(self._vector_backend, emb.dim(),
                                      self._vector_store_path)
        self.semantic = _core.SemanticRetriever(self.rt.adapter, emb, self.idx)
        self.completor = _core.PatternCompletor(self.rt.adapter, self.semantic)
        self.worker = _core.EmbeddingWorker(self.rt.adapter, emb, self.idx)

    def remember(self, text: str, *, holder=None, interlocutor=None, now=None) -> dict:
        """标准写管线在 C++ `memoryops::remember`(2026-06-11 边界归位):
        幂等键派生(sha256)、入库策略默认值、「先 engram 后抽取、仅
        accepted/idempotent 才抽取」的顺序规则都在核心层,且 LLM 网络期间
        释放 GIL。这里只剩前置校验与 datetime→ISO 签名归一。

        sub-project A phase 5:remember 跑 TWO 条独立抽取管线——belief/会话
        (memory_remember 内的 Extractor)与 episodic(EpisodicExtractor:叙事
        → OCCURRED 事件 + episodic_events 行)。两条互不影响,任一空集都正常。
        episodic 是 best-effort 第二条,复用第一条已(幂等)入库的 engram_ref;
        只有 engram 真入库(accepted/idempotent → engram_ref 非空)时才跑——
        no_store/rejected 时无 engram 可挂证据,跳过。"""
        if self.llm is None:
            raise LLMNotConfigured(
                "remember requires an llm adapter "
                "(make_stub_llm / make_openai_llm / make_anthropic_llm)")
        created_iso = parse_now(now).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        holder_id = holder or self.agent
        out = _core.memory_remember(
            self.rt.adapter, self.llm, self._extraction.belief_prompt,
            tenant_id=self.tenant, holder_id=holder_id,
            interlocutor=interlocutor or "",
            adapter_name=self.adapter_name, source_prefix=self.source_prefix,
            created_at_iso8601=created_iso, payload=text.encode("utf-8"),
            policy=_build_policy(self._extraction))

        # 第二条:episodic 抽取(叙事事件)。挂在第一条返回的同一 engram 上。
        engram_ref = out.get("engram_ref") or ""
        if engram_ref:
            # Pass the adapter (Phase 2 Task 2.2) so the actor + each participant
            # surface resolves to its canonical first-seen cognizer name, grounding
            # name drift ("Xiao Hong"/"XiaoHong") to one entity.
            episodic = _core.EpisodicExtractor(
                self.conn, self.llm, self.rt.adapter, self._extraction.episodic_prompt)
            event_ids = episodic.extract(
                passage=text, engram_ref=engram_ref, tenant=self.tenant,
                agent_self=holder_id, now=created_iso)
            if event_ids:
                # 合并两条管线本次新写的语句 id(belief + episodic 事件)。
                out["statement_ids"] = list(out.get("statement_ids", [])) + list(event_ids)
                # sub-project B: rebuild per-cognizer perception from the events (best-effort).
                # Pass the adapter (Task 5.1) so witnessed-event engrams also land in the
                # KnowledgeFrontier presence_log, making does_X_know() event-aware.
                try:
                    _core.PerceptionReconstructor(
                        self.conn, self.rt.adapter).reconstruct(tenant=self.tenant)
                except Exception:  # noqa: BLE001 — perception is best-effort; never fail remember
                    pass
        return out

    def recall(self, query: str, *, perspective: str = "first_person",
               k: int = 10, mode: str = "semantic", holder: str | None = None) -> list:
        """mode="semantic" — vector cosine via SemanticRetriever.vector_recall;
        mode="completion" — associative spreading via PatternCompletor.

        holder overrides the recall holder dimension (default self.agent). A
        caller that wrote statements under a non-default holder MUST recall with
        the same holder, else the candidate SQL's `s.holder_id = ?` predicate
        excludes them (P3.b2: OpenClaw plugin holder must round-trip)."""
        holder_id = holder or self.agent
        # holder_perspective is stored lowercase (extractor normalizes the enum);
        # normalize the query perspective so a caller passing "FIRST_PERSON" still
        # matches the stored "first_person" instead of silently returning empty.
        perspective = (perspective or "").lower()
        if mode == "completion":
            res = self.completor.complete(_core.PatternCompletionParams(
                tenant_id=self.tenant, holder_id=holder_id,
                holder_perspective=perspective, cue_text=query, result_k=k))
            return [{"row": s.row, "score": s.activation} for s in res.rows]
        res = self.semantic.vector_recall(_core.SemanticRetrieverParams(
            tenant_id=self.tenant, holder_id=holder_id,
            holder_perspective=perspective, query_text=query, k=k))
        return [{"row": s.row, "score": s.score} for s in res.rows]

    def plan_query(self, text: str = "", *, intent: str = "FACT_LOOKUP",
                   perspective: Optional[str] = None, target: Optional[str] = None,
                   subject: Optional[str] = None, predicate: Optional[str] = None,
                   k: int = 10, now=None):
        """P3.a1 检索规划:一行转发 _core.RetrievalPlanner(7 步管线居 C++,
        语义路径网络期间释放 GIL)。"""
        q = _core.PlannerQuery()
        q.tenant_id = self.tenant
        q.querier = self.agent
        q.perspective = perspective or ""
        q.intent = getattr(_core.QueryIntent, intent)
        q.text = text
        q.subject_id = subject or ""
        q.predicate = predicate or ""
        q.target = target or ""
        q.as_of_iso8601 = parse_now(now).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        q.k = k
        q.trace_id = str(uuid.uuid4())
        q.query_id = str(uuid.uuid4())
        planner = _core.RetrievalPlanner(self.rt.adapter, self.semantic)
        return planner.run(q)

    def tick(self, now: str) -> dict:
        """Advance background workers: embed pending + fire due commitments +
        flush grounding 滞后事件 (P2.j)。三连组合在 C++ `memoryops::tick_all`
        (嵌入网络期间释放 GIL);这里只剩绑定转发。"""
        return _core.memory_tick_all(self.rt.adapter, self.worker, self.policy, now)

    def build_working_set(self, interlocutor, *, goal=None, token_budget: int = 2000,
                          holder: str | None = None):
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
            tenant_id=self.tenant, agent_id=holder or self.agent,
            interlocutor=interlocutor, goal=goal or "",
            token_budget=token_budget)

    def latest_event_location(self, theme: str) -> str:
        """sub-project A phase 6:主题 `theme` 最高 seq 的 OCCURRED 事件 location
        (地面真值「当前所在」),无事件返回 ""。薄转发到核心层
        `EpisodicEventStore::latest_event_location`(纯本地 SQLite 读)。"""
        return _core.latest_event_location(self.conn, self.tenant, theme)

    def forget(self, ids: list[str], *, now=None) -> dict:
        """逻辑删除(→forgotten):核心 `memoryops::forget`,这里只签名归一。
        forgotten 立即移出检索;向量/投影清理由 tick 跟进。"""
        now_iso = parse_now(now).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        n = _core.memory_forget(self.rt.adapter, tenant=self.tenant,
                                ids=list(ids), now_iso=now_iso)
        return {"forgotten": n}

    def close(self) -> None:
        # The SqliteAdapter is closed when its runtime/handle is GC'd; nothing
        # to release explicitly in the embedded core.
        self.conn = None
