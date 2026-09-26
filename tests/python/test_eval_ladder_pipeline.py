"""PR-3: 归因阶梯 real-mode 检索装配层(scripts/eval_ladder_pipeline.py)的离线测试。

用 StubEmbeddingAdapter 离线验证六台阶 recall-block 组装的结构正确性(无网络、
进 CI):这一层是"S_rag 与 S_star 唯一差异 = 认知层"这条归因命脉,必须可测。
答题 + 抽取(真 backbone / 真 Extractor)是 gated 真跑,不在此测。
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from starling import _core, runtime

_PIPE = Path(__file__).resolve().parents[2] / "scripts" / "eval_ladder_pipeline.py"
_spec = importlib.util.spec_from_file_location("eval_ladder_pipeline", _PIPE)
pipe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pipe)


@pytest.fixture
def rt(tmp_path):
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


# 一条 knowledge-update 风格的 history:auth 服务从 Bob 转到 Carol。
HISTORY = [
    {"speaker": "alice", "text": "Bob owns the auth service.",
     "observed_at": "2026-04-01T10:00:00Z"},
    {"speaker": "alice", "text": "Carol has taken over the auth service from Bob.",
     "observed_at": "2026-05-01T10:00:00Z"},
]
QUESTION = "Who currently owns the auth service?"


def _pipeline(rt):
    """离线管线:seed history → stub embed → 返回 (emb, idx) 供检索台阶复用。"""
    pipe.seed_history_statements(str(rt.adapter.db_path), "lme-ku-000", HISTORY)
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    pipe.embed_seeded(_core, rt.adapter, emb, idx, "2026-06-01T00:00:00Z")
    return emb, idx


def test_s0_is_empty_block(rt):
    emb, idx = _pipeline(rt)
    r = pipe.recall_block(_core, "S0", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY)
    assert r["block"] == "" and r["abstained"] is False


def test_s_full_contains_all_history(rt):
    emb, idx = _pipeline(rt)
    r = pipe.recall_block(_core, "S_full", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY)
    # 长上下文上限:全部 history 行都在块里
    assert "Bob owns the auth service" in r["block"]
    assert "Carol has taken over" in r["block"]


def test_s_rand_is_deterministic_per_seed(rt):
    emb, idx = _pipeline(rt)
    a = pipe.recall_block(_core, "S_rand", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY, seed=7)
    b = pipe.recall_block(_core, "S_rand", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY, seed=7)
    assert a["block"] == b["block"]      # 同 seed 可复现


def test_s_rag_returns_recalled_lines(rt):
    emb, idx = _pipeline(rt)
    r = pipe.recall_block(_core, "S_rag", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY, k=5)
    # 裸向量召回:非空、无标签(S_rag 无认知层)
    assert r["block"] and r["labels"] == []


def test_s_star_carries_context_pack_labels(rt):
    """S_star 走 RetrievalPlanner → context_pack 带标签(S_rag 拿不到)。
    这是 S_star 与 S_rag 唯一差异 = 认知层的直接证据。

    探针 query 逐字命中一条语句被 embed 的文本(EmbeddingWorker 的
    render_text = "<subject_id> <predicate> <object_value>",见
    src/embedding/embedding_worker.cpp:47)。这样做的原因是可复现性,
    与测试意图无关:StubEmbeddingAdapter 用 std::hash<string_view> 做 RNG
    种子(implementation-defined),同一 stub 实例对**同一字符串**必产
    逐字节相同向量 → cosine(v,v)=1.0 是唯一跨平台成立的不变量;而两个
    **不同**字符串在 8 维里是独立随机单位向量,cosine 期望≈0、跨 stdlib
    (libc++ vs libstdc++)随机过/不过 planner 的 tau_recall=0.25 弃答阈值
    → 曾致本测试在 CI(ubuntu)上偶发 assert []。命中串让"planner 产
    labels"这个结构事实在任何平台确定性显现。自然问句的语义召回质量属于
    real-mode(真 embedder)的关注点,不压在离线 stub 结构测试上。"""
    emb, idx = _pipeline(rt)
    # 逐字 = HISTORY[1] 的 render_text("subject" + " said " + text)。
    hit = "subject said " + HISTORY[1]["text"]
    r = pipe.recall_block(_core, "S_star", adapter=rt.adapter, embedder=emb,
                          index=idx, question=hit, history=HISTORY, k=5)
    assert r["labels"]                          # 有标签(FACT/BELIEF/...)
    assert "[" in r["block"]                    # context_pack 带 [LABEL] 前缀


def test_s_star_delegates_scope_discovery_and_fusion_to_native_observer():
    source = _PIPE.read_text(encoding="utf-8")
    assert "core.observer_holders(adapter, \"default\")" in source
    assert "SELECT DISTINCT holder_id" not in source
    assert "sorted(candidates" not in source


@pytest.mark.parametrize("polarity,relation", [
    ("neg", "NOT (permanence prefers permanence)"),
    ("unknown", "UNKNOWN (permanence prefers permanence)"),
])
def test_planner_context_preserves_stored_polarity(rt, polarity, relation):
    pipe.seed_gold_statements(str(rt.adapter.db_path), "polarity", [
        {"holder": "Claudette", "subject": "permanence", "predicate": "prefers",
         "object": "permanence", "modality": "desires", "polarity": polarity},
    ])
    emb, idx = _core.StubEmbeddingAdapter(8), _core.SqliteBlobVectorIndex()
    pipe.embed_seeded(_core, rt.adapter, emb, idx, "2026-06-01T00:00:00Z")
    q = _core.PlannerQuery()
    q.tenant_id, q.querier = "default", "Claudette"
    q.text = "permanence prefers permanence"
    q.as_of_iso8601 = "2026-06-01T00:00:00Z"
    q.trace_id, q.query_id = "polarity", "polarity-q"
    sr = _core.SemanticRetriever(rt.adapter, emb, idx)
    result = _core.RetrievalPlanner(rt.adapter, sr).run(q)
    assert not result.abstained
    assert relation in result.context_pack
    assert relation in _core.render_context_line(result.entries[0].row, result.entries[0].label)
    recalled = pipe.recall_block(_core, "S_star", adapter=rt.adapter, embedder=emb,
                                 index=idx, question=q.text, history=[], k=1)
    assert relation in recalled["block"]


def test_s_star_abstains_on_empty_store(rt):
    """空库时 S_star 结构化弃答——S_rag 无此能力,认识论诚实主张的地基。"""
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    # 不 seed 任何 statement:直接查
    r = pipe.recall_block(_core, "S_star", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY, k=5)
    assert r["abstained"] is True


def _multi_holder_pipeline(rt):
    gold = [
        {"holder": holder, "subject": "team", "predicate": "has_status",
         "object": "expanding", "observed_at": "2026-05-01T10:00:00Z"}
        for holder in ("Mei", "Leon")
    ]
    pipe.seed_gold_statements(str(rt.adapter.db_path), "multi", gold)
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM statements WHERE id='multi-gold0'").fetchone())
        row.update(tenant_id="private", holder_id="private-holder")
        conn.execute(
            f"INSERT INTO statements ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",
            tuple(row.values()))
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    pipe.embed_seeded(_core, rt.adapter, emb, idx, "2026-06-01T00:00:00Z")
    return emb, idx


@pytest.mark.parametrize("stage", ["S_star", "S_star_oracle"])
def test_planner_recalls_actual_holders_within_eval_tenant(rt, stage):
    emb, idx = _multi_holder_pipeline(rt)
    result = pipe.recall_block(
        _core, stage, adapter=rt.adapter, embedder=emb, index=idx,
        question="team has_status expanding", history=[], k=10)
    assert result["abstained"] is False
    assert "holder Mei" in result["block"]
    assert "holder Leon" in result["block"]
    assert "private-holder" not in result["block"]


def test_planner_multi_holder_recall_keeps_total_k_budget(rt):
    emb, idx = _multi_holder_pipeline(rt)
    result = pipe.recall_block(
        _core, "S_star", adapter=rt.adapter, embedder=emb, index=idx,
        question="team has_status expanding", history=[], k=1)
    assert result["abstained"] is False
    assert len(result["labels"]) == 1
    assert len(result["block"].splitlines()) == 1


def test_planner_multi_holder_selects_later_holder_with_higher_score(rt):
    emb, idx = _multi_holder_pipeline(rt)
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("UPDATE statements SET salience=0.1 WHERE tenant_id='default' AND holder_id='Leon'")
        conn.execute("UPDATE statements SET salience=0.9 WHERE tenant_id='default' AND holder_id='Mei'")
    result = pipe.recall_block(
        _core, "S_star", adapter=rt.adapter, embedder=emb, index=idx,
        question="team has_status expanding", history=[], k=1)
    assert "holder Mei" in result["block"]
    assert "holder Leon" not in result["block"]


def test_planner_keeps_successful_scope_when_another_holder_abstains(rt):
    emb, idx = _multi_holder_pipeline(rt)
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute("UPDATE statements SET review_status='rejected' WHERE tenant_id='default' AND holder_id='Mei'")
    result = pipe.recall_block(
        _core, "S_star", adapter=rt.adapter, embedder=emb, index=idx,
        question="team has_status expanding", history=[], k=10)
    assert result["abstained"] is False
    assert "holder Leon" in result["block"]
    assert "holder Mei" not in result["block"]
    assert {r["holder"]: r["abstained"] for r in result["receipts"]} == {
        "Leon": False, "Mei": True}


def test_planner_explicit_holder_does_not_expand_scope(rt):
    emb, idx = _multi_holder_pipeline(rt)
    result = pipe.recall_block(
        _core, "S_star", adapter=rt.adapter, embedder=emb, index=idx,
        question="team has_status expanding", history=[], holder="Mei", k=10)
    assert "holder Mei" in result["block"]
    assert "holder Leon" not in result["block"]
    assert "private-holder" not in result["block"]


def test_oracle_seed_bypasses_extractor(rt):
    """S_star_oracle 用 gold 直插(绕开 Extractor)→ 抽取税隔离的地基。"""
    gold = [{"holder": "alice", "subject": "carol", "predicate": "owns",
             "object": "the auth service", "observed_at": "2026-05-01T10:00:00Z"}]
    n = pipe.seed_gold_statements(str(rt.adapter.db_path), "lme-ku-000", gold)
    assert n == 1
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        row = c.execute(
            "SELECT holder_id, predicate, object_value FROM statements "
            "WHERE id='lme-ku-000-gold0'").fetchone()
    assert row == ("alice", "owns", "the auth service")


def test_unknown_stage_rejected(rt):
    emb, idx = _pipeline(rt)
    with pytest.raises(ValueError, match="unknown stage"):
        pipe.recall_block(_core, "S_bogus", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY)


# ---- embed_seeded 必须抽干(2026-08 冒烟实测的真 bug 回归钉)------------------
# WorkerConfig.batch_size=32,而真实语料一题 50~302 turns。只 tick 一批会让超出
# 32 的 statement 永远没有向量,S_rag/S_star 便在**残缺库**上检索——防守判据
# S_star−S_rag 建立在两个都残缺的库上,分数与题目无关地偏低,归因结论被污染。


def _long_history(n: int) -> list[dict]:
    return [{"speaker": "alice", "text": f"fact number {i} about the auth service",
             "observed_at": "2026-04-01T10:00:00Z"} for i in range(n)]


def test_embed_seeded_drains_beyond_one_batch(rt):
    """50 条(>batch_size=32)必须全部拿到向量,且用了多批。"""
    pipe.seed_history_statements(str(rt.adapter.db_path), "drain-000", _long_history(50))
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    stats = pipe.embed_seeded(_core, rt.adapter, emb, idx, "2026-06-01T00:00:00Z")

    assert stats["embedded"] == 50          # 全部嵌入,不止首批 32
    assert stats["failed"] == 0
    assert stats["ticks"] >= 2              # 确实抽干了多批(单批必然漏)

    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        vectors = c.execute("SELECT COUNT(*) FROM statement_vectors").fetchone()[0]
        missing = c.execute(
            "SELECT COUNT(*) FROM statements s WHERE NOT EXISTS ("
            "SELECT 1 FROM statement_vectors v WHERE v.stmt_id = s.id)").fetchone()[0]
    assert vectors == 50
    assert missing == 0                     # 一条都不许漏(否则检索库残缺)


def test_embed_seeded_idempotent_second_call_is_noop(rt):
    """已抽干后再调:0 新增、1 批即判停(不重复烧 embedding API)。"""
    pipe.seed_history_statements(str(rt.adapter.db_path), "drain-001", _long_history(40))
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    pipe.embed_seeded(_core, rt.adapter, emb, idx, "2026-06-01T00:00:00Z")

    again = pipe.embed_seeded(_core, rt.adapter, emb, idx, "2026-06-01T00:00:00Z")
    assert {k: again[k] for k in ('embedded', 'failed', 'ticks')} == {"embedded": 0, "failed": 0, "ticks": 1}
    assert again['final_health']['complete'] is True and again['final_health']['embedded'] == 40


def test_embed_seeded_fails_loud_when_not_drained(rt):
    """max_ticks 兜底:撞顶 fail-loud,绝不静默在残缺向量库上继续。"""
    pipe.seed_history_statements(str(rt.adapter.db_path), "drain-002", _long_history(50))
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    with pytest.raises(RuntimeError, match="仍未抽干"):
        pipe.embed_seeded(_core, rt.adapter, emb, idx,
                          "2026-06-01T00:00:00Z", max_ticks=1)


def test_embed_seeded_recovers_without_erasing_failed_attempts(rt):
    pipe.seed_history_statements(str(rt.adapter.db_path), "recover", _long_history(40))
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        row = c.execute('SELECT subject_id,predicate,object_value FROM statements LIMIT 1').fetchone()
    emb = _core.StubEmbeddingAdapter(8)
    emb.fail_next(' '.join(row))
    result = pipe.embed_seeded(_core, rt.adapter, emb, _core.SqliteBlobVectorIndex(), "2026-06-01T00:00:00Z")
    assert result['failed'] == 32
    assert result['embedded'] == 40
    assert result.get('final_health', {}).get('complete') is True
    assert result['final_health']['embedded'] == 40


def test_embed_seeded_rejects_exhausted_rows_even_after_idle_tick(rt):
    pipe.seed_history_statements(str(rt.adapter.db_path), "exhaust", _long_history(1))
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute("INSERT INTO statement_vectors(stmt_id,tenant_id,dim,model,status,retry_count) "
                  "SELECT id,tenant_id,8,'stub','failed',3 FROM statements")
    with pytest.raises(RuntimeError, match='final embedding health'):
        pipe.embed_seeded(_core, rt.adapter, _core.StubEmbeddingAdapter(8),
                          _core.SqliteBlobVectorIndex(), "2026-06-01T00:00:00Z")


@pytest.mark.parametrize('assignment', ["dim=9", "model='wrong'", "raw_embedding=x'00000000'",
                                      "index_vector=zeroblob(32)", "retry_count=1"])
def test_embed_seeded_rejects_corrupt_embedded_rows(rt, assignment):
    emb, idx = _pipeline(rt)
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute('UPDATE statement_vectors SET '+assignment)
    with pytest.raises(RuntimeError, match='final embedding health'):
        pipe.embed_seeded(_core, rt.adapter, emb, idx, "2026-06-01T00:00:00Z")
