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


def test_s_star_abstains_on_empty_store(rt):
    """空库时 S_star 结构化弃答——S_rag 无此能力,认识论诚实主张的地基。"""
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    # 不 seed 任何 statement:直接查
    r = pipe.recall_block(_core, "S_star", adapter=rt.adapter, embedder=emb,
                          index=idx, question=QUESTION, history=HISTORY, k=5)
    assert r["abstained"] is True


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
    assert again == {"embedded": 0, "failed": 0, "ticks": 1}


def test_embed_seeded_fails_loud_when_not_drained(rt):
    """max_ticks 兜底:撞顶 fail-loud,绝不静默在残缺向量库上继续。"""
    pipe.seed_history_statements(str(rt.adapter.db_path), "drain-002", _long_history(50))
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    with pytest.raises(RuntimeError, match="仍未抽干"):
        pipe.embed_seeded(_core, rt.adapter, emb, idx,
                          "2026-06-01T00:00:00Z", max_ticks=1)
