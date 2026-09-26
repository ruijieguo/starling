#!/usr/bin/env python3
"""归因阶梯 real-mode 的检索装配层(PR-3)。

核心设计:把 real-mode 拆成两层——
  1. **检索装配**(本文件):六台阶各自"喂给 answerer 的记忆块"如何组装。
     这一层可用 StubEmbeddingAdapter **离线验证结构正确性**(无网络、可进 CI):
     S_rag 走 vector_recall、S_star/S_star_oracle 走原生 ObserverRetriever、
     S_full/S_rand/S0 走 SQL/拼接。PR-0 已坐实 planner 全路径离线可达。
  2. **答题 + 抽取**(eval_ladder._real_answer,gated):把记忆块喂给真 backbone
     问 MC index、以及 S_star 台阶用真 Extractor 从 raw_turns 抽 statement。
     这一层需 API key,是 non-CI 的人值守真跑。

分层的意义:检索装配是"S_star 与 S_rag 唯一差异 = 认知层"这条归因命脉所在,
必须可测;而它恰好**不需要真 LLM**——embedder 可换 stub,planner/retriever 是
纯 C++ 计算。所以把它单独拎出来离线测,real-mode 真跑时只有 answerer/Extractor
是未测的网络部分。

seed 契约(与 eval_longmemeval._real_answer 同):raw sqlite 24 列 INSERT 先提交
关闭,再让 C++ EmbeddingWorker 写,保持 WAL 写者严格串行(避免 database is locked)。
"""
from __future__ import annotations

import sqlite3
import json
from typing import Any

# 六台阶的规范记忆块来源(与 eval_ladder.ALL_STAGES 对齐)。
STAGES = ("S0", "S_rand", "S_full", "S_rag", "S_star_oracle", "S_star")


def recall_observer_block(core: Any, *, adapter: Any, embedder: Any, index: Any,
                          question: str, allowed_holders: list[str], mode: str,
                          now_iso: str, k: int = 10, max_context_bytes: int = 8000,
                          include_unknown_time: bool = False,
                          source_strategy: str = "bm25", source_seed_k: int | None = None,
                          source_seed_max_context_bytes: int | None = None,
                          source_dialogue_radius: int | None = None,
                          min_source_items: int | None = None) -> dict:
    """显式观察者范围的数据映射；选择、融合、预算与渲染由C++完成。"""
    semantic = core.SemanticRetriever(adapter, embedder, index)
    observer = core.ObserverRetriever(adapter, semantic)
    query = core.ObserverQuery()
    query.tenant_id = "default"
    query.allowed_holders = allowed_holders
    query.question = question
    query.as_of_iso8601 = now_iso
    query.k = k
    query.max_context_bytes = max_context_bytes
    query.mode = mode
    if source_strategy != "bm25":
        query.source_strategy = source_strategy
    for name, value in (("source_seed_k", source_seed_k),
                        ("source_seed_max_context_bytes", source_seed_max_context_bytes),
                        ("source_dialogue_radius", source_dialogue_radius),
                        ("min_source_items", min_source_items)):
        if value is not None:
            setattr(query, name, value)
    if include_unknown_time:
        query.include_unknown_time = True
    return json.loads(observer.run(query))

# 与 eval_longmemeval._real_answer 逐字一致的 24 列 statements INSERT。
_INSERT = (
    "INSERT INTO statements("
    "id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,"
    "predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,"
    "salience,affect_json,activation,last_accessed,provenance,"
    "consolidation_state,review_status,created_at,updated_at) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


def seed_gold_statements(db_path: str, item_id: str,
                         gold_statements: list[dict]) -> int:
    """oracle 台阶(S_star_oracle):把 gold statement 直接写库,绕开 Extractor。

    gold_statements 每项:{holder, subject, predicate, object, observed_at,
    perspective?, modality?, confidence?}。返回写入行数。

    这是"抽取税"隔离的关键:S_star_oracle 用 gold 喂入,S_star 用真 Extractor,
    二者差 = 抽取质量的税(impl-spec §2.1)。raw INSERT 先提交关闭再交给 C++,
    保持 WAL 写者串行。"""
    n = 0
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        for i, g in enumerate(gold_statements):
            observed = g.get("observed_at", "1970-01-01T00:00:00Z")
            conn.execute(_INSERT, (
                f"{item_id}-gold{i}", "default",
                g.get("holder", "alice"), g.get("perspective", "first_person"),
                g.get("subject_kind", "cognizer"), g.get("subject", "subject"),
                g.get("predicate", "said"), g.get("object_kind", "str"),
                g.get("object", ""), "a" * 64, "v1",
                g.get("modality", "believes"), g.get("polarity", "pos"),
                float(g.get("confidence", 0.9)), observed,
                0.5, "{}", 0.0, observed, "user_input",
                "consolidated", "approved", observed, observed,
            ))
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def seed_history_statements(db_path: str, item_id: str,
                            history: list[dict], holder: str = "alice", *,
                            speaker_labels: bool = False) -> int:
    """S_rag/S0/S_rand/S_full 台阶的库内容:把每条 history turn 落成一条
    'said' statement(与 eval_longmemeval._real_answer 一致的扁平 seed)。

    注意:这是 real-mode 里 **非 S_star** 台阶用的 seed（无归属结构，纯扁平），
    刻意保持与现有 eval_longmemeval 一致，作为 S_rag 对照物。S_star 台阶另走
    真 Extractor 从 raw_turns 抽带归属的 statement（在 eval_ladder 侧）。
    speaker_labels=True 在文本中保留说话人,同时影响 embedding 与答题上下文;
    默认 False 保留历史协议。两者仍使用同一个扁平检索 scope。"""
    n = 0
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        for i, turn in enumerate(history):
            observed = turn.get("observed_at", "1970-01-01T00:00:00Z")
            text = turn.get("text", "")
            if speaker_labels:
                speaker = str(turn.get("speaker") or "unknown").strip() or "unknown"
                text = f"{speaker}: {text}"
            conn.execute(_INSERT, (
                f"{item_id}-h{i}", "default", holder, "first_person",
                "cognizer", "subject", "said", "str", text,
                "a" * 64, "v1", "believes", "pos", 0.9, observed,
                0.5, "{}", 0.0, observed, "user_input",
                "consolidated", "approved", observed, observed,
            ))
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def embed_seeded(core: Any, adapter: Any, embedder: Any, index: Any,
                 now_iso: str, max_ticks: int = 200) -> dict:
    """把已写入的 statement **全部**嵌入。embedder 由调用方注入:
    离线测试传 StubEmbeddingAdapter,real-mode 传 OpenAIEmbeddingAdapter——
    **写入侧与检索侧必须同一 embedder 实例**(DashboardEngine rebuild_embedder 纪律)。

    **必须循环抽干,不能只 tick 一批**:WorkerConfig.batch_size=32,而真实语料
    一题 50~302 turns。只调一次 tick_one_batch 会让超出 32 的 statement 永远没有
    向量,S_rag/S_star 就在**残缺库**上检索——防守判据 S_star−S_rag 建立在两个都
    残缺的库上,分数与题目无关地偏低,归因结论被污染(2026-08 冒烟实测:50 条
    只嵌入 32 条,18 条无向量)。

    判停:空 tick 后由 C++ 最终健康快照确认；重试耗尽不能视作完成。max_ticks 兜底防呆,
    避免 worker 永不返回 0 时无限循环;撞顶 fail-loud,不静默截断。
    返回 {embedded, failed, ticks, final_health}；failed 保留累计失败尝试，不能当最终失败数。"""
    worker = core.EmbeddingWorker(adapter, embedder, index)
    total_embedded = 0
    total_failed = 0
    for tick in range(1, max_ticks + 1):
        stats = worker.tick_one_batch(now_iso)
        total_embedded += int(stats.embedded)
        total_failed += int(stats.failed)
        if int(stats.embedded) == 0 and int(stats.failed) == 0:
            health = json.loads(worker.health_json())
            if health['complete'] is not True:
                raise RuntimeError(f"final embedding health incomplete: {health}; failed_attempts={total_failed}")
            return {"embedded": total_embedded, "failed": total_failed, "ticks": tick, "final_health": health}
    raise RuntimeError(
        f"embed_seeded: {max_ticks} 批仍未抽干(embedded={total_embedded}, "
        f"failed={total_failed});拒绝在残缺向量库上继续检索")


def recall_block(core: Any, stage: str, *, adapter: Any, embedder: Any,
                 index: Any, question: str, history: list[dict],
                 holder: str | None = None, k: int = 10, seed: int = 0,
                 now_iso: str = "2026-06-01T00:00:00Z") -> dict:
    """六台阶的"喂给 answerer 的记忆块"组装。返回 {block, abstained, labels}。

    这是归因阶梯的命脉:S_rag 与 S_star 的唯一差异必须是认知层(planner)。
    可用 StubEmbeddingAdapter 离线验证结构（无网络）。

      S0            → 空块
      S_rand        → 全库随机 k 行（同一 seed 确定性）
      S_full        → 全 history 行拼接（长上下文上限对照）
      S_rag         → SemanticRetriever.vector_recall(k)（防守对照物）
      S_star/oracle → ObserverRetriever(mode="statements")（视角遮蔽先于排序 + context_pack + 弃答）

    Planner 默认查询本题临时库 default tenant 内的实际 holder,逐 scope 调用内核,
    按内核 final_score 合并到总计 k 条。显式 holder 始终只查询该 scope。
    这是全会话观察者评测协议,不代表特定参与者的 KnowledgeFrontier 评测。
    """
    if stage == "S0":
        return {"block": "", "abstained": False, "labels": []}

    if stage == "S_full":
        lines = [f"[{t.get('observed_at','')}] {t.get('speaker','?')}: {t.get('text','')}"
                 for t in history]
        return {"block": "\n".join(lines), "abstained": False, "labels": []}

    if stage == "S_rand":
        # 全库随机 k 行(同一 seed 确定性):用 SQL 的确定性排序 + Python 取样,
        # 避免依赖 sqlite RANDOM() 的不可复现。
        conn = sqlite3.connect(str(adapter.db_path), timeout=30)
        try:
            rows = conn.execute(
                "SELECT predicate, object_value FROM statements "
                "WHERE tenant_id='default' ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
        import random
        rng = random.Random(seed)
        picked = rng.sample(rows, min(k, len(rows))) if rows else []
        block = "\n".join(f"- {p}: {o}".strip(": ") for p, o in picked)
        return {"block": block, "abstained": False, "labels": []}

    if stage == "S_rag":
        sr = core.SemanticRetriever(adapter, embedder, index)
        res = sr.vector_recall(core.SemanticRetrieverParams(
            tenant_id="default", holder_id=holder or "alice", query_text=question, k=k))
        recalled = [
            f"{getattr(s.row,'predicate','')}: {getattr(s.row,'object_value','')}".strip(": ")
            for s in res.rows
        ]
        return {"block": "\n".join(f"- {r}" for r in recalled),
                "abstained": False, "labels": [],
                "statement_ids": [s.row.id for s in res.rows]}

    if stage in ("S_star", "S_star_oracle"):
        if k <= 0:
            raise ValueError("planner recall requires k > 0")
        # Holder discovery, per-scope planning, score fusion, deduplication,
        # and rendering all remain in the native ObserverRetriever. Python
        # only supplies the explicit allowlist required by its scope contract.
        holders = ([holder] if holder is not None
                   else core.observer_holders(adapter, "default"))
        # An empty store still goes through the core abstention path.
        holders = holders or ["alice"]
        return recall_observer_block(
            core, adapter=adapter, embedder=embedder, index=index,
            question=question, allowed_holders=holders, mode="statements",
            now_iso=now_iso, k=k, max_context_bytes=8000)

    raise ValueError(f"unknown stage: {stage!r}; valid={STAGES}")
