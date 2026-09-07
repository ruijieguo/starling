#!/usr/bin/env python3
"""归因阶梯 real-mode 的检索装配层(PR-3)。

核心设计:把 real-mode 拆成两层——
  1. **检索装配**(本文件):六台阶各自"喂给 answerer 的记忆块"如何组装。
     这一层可用 StubEmbeddingAdapter **离线验证结构正确性**(无网络、可进 CI):
     S_rag 走 vector_recall、S_star/S_star_oracle 走 RetrievalPlanner、
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
from typing import Any

# 六台阶的规范记忆块来源(与 eval_ladder.ALL_STAGES 对齐)。
STAGES = ("S0", "S_rand", "S_full", "S_rag", "S_star_oracle", "S_star")

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
                            history: list[dict], holder: str = "alice") -> int:
    """S_rag/S0/S_rand/S_full 台阶的库内容:把每条 history turn 落成一条
    'said' statement(与 eval_longmemeval._real_answer 一致的扁平 seed)。

    注意:这是 real-mode 里 **非 S_star** 台阶用的 seed（无归属结构，纯扁平），
    刻意保持与现有 eval_longmemeval 一致，作为 S_rag 对照物。S_star 台阶另走
    真 Extractor 从 raw_turns 抽带归属的 statement（在 eval_ladder 侧）。"""
    n = 0
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        for i, turn in enumerate(history):
            observed = turn.get("observed_at", "1970-01-01T00:00:00Z")
            conn.execute(_INSERT, (
                f"{item_id}-h{i}", "default", holder, "first_person",
                "cognizer", "subject", "said", "str", turn.get("text", ""),
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

    判停:embedded+failed==0 即本批无待嵌入项(抽干)。max_ticks 兜底防呆,
    避免 worker 永不返回 0 时无限循环;撞顶 fail-loud,不静默截断。
    返回 {embedded, failed, ticks} 供调用方核验。"""
    worker = core.EmbeddingWorker(adapter, embedder, index)
    total_embedded = 0
    total_failed = 0
    for tick in range(1, max_ticks + 1):
        stats = worker.tick_one_batch(now_iso)
        total_embedded += int(stats.embedded)
        total_failed += int(stats.failed)
        if int(stats.embedded) == 0 and int(stats.failed) == 0:
            return {"embedded": total_embedded, "failed": total_failed, "ticks": tick}
    raise RuntimeError(
        f"embed_seeded: {max_ticks} 批仍未抽干(embedded={total_embedded}, "
        f"failed={total_failed});拒绝在残缺向量库上继续检索")


def recall_block(core: Any, stage: str, *, adapter: Any, embedder: Any,
                 index: Any, question: str, history: list[dict],
                 holder: str = "alice", k: int = 10, seed: int = 0) -> dict:
    """六台阶的"喂给 answerer 的记忆块"组装。返回 {block, abstained, labels}。

    这是归因阶梯的命脉:S_rag 与 S_star 的唯一差异必须是认知层(planner)。
    可用 StubEmbeddingAdapter 离线验证结构（无网络）。

      S0            → 空块
      S_rand        → 全库随机 k 行（同一 seed 确定性）
      S_full        → 全 history 行拼接（长上下文上限对照）
      S_rag         → SemanticRetriever.vector_recall(k)（防守对照物）
      S_star/oracle → RetrievalPlanner.run（视角遮蔽先于排序 + context_pack + 弃答）
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
            tenant_id="default", holder_id=holder, query_text=question, k=k))
        recalled = [
            f"{getattr(s.row,'predicate','')}: {getattr(s.row,'object_value','')}".strip(": ")
            for s in res.rows
        ]
        return {"block": "\n".join(f"- {r}" for r in recalled),
                "abstained": False, "labels": []}

    if stage in ("S_star", "S_star_oracle"):
        sr = core.SemanticRetriever(adapter, embedder, index)
        planner = core.RetrievalPlanner(adapter, sr)
        q = core.PlannerQuery()
        q.tenant_id = "default"
        q.querier = holder
        q.perspective = ""
        q.intent = core.QueryIntent.FACT_LOOKUP
        q.text = question
        q.as_of_iso8601 = "2026-06-01T00:00:00Z"
        q.k = k
        q.trace_id = f"{stage}-{seed}"
        q.query_id = f"{stage}-{seed}-q"
        res = planner.run(q)
        return {"block": res.context_pack, "abstained": res.abstained,
                "labels": [e.label.name for e in res.entries]}

    raise ValueError(f"unknown stage: {stage!r}; valid={STAGES}")
