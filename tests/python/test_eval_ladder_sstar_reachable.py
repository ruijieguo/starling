"""PR-0 parity 钉测:归因阶梯的 S_star 台阶(RetrievalPlanner 7 步管线)从
Python 全路径可达,且离线(StubEmbeddingAdapter)确定性可跑。

背景(评测组合归因阶梯,docs/eval/2026-07-19-starling-eval-portfolio.md §2):
S_star 是阶梯里唯一注入 Starling 认知层(视角遮蔽先于排序 + 8 标签
context_pack + 四条件结构化弃答)的台阶。它相对 S_rag(裸 vector_recall)的差
= 认知层净贡献,是整套「大幅提升」主张的度量支点。这个测试把「S_star 能从
Python 跑通、且产出 context_pack / 弃答」这一可达性钉死,避免 harness 悄悄退回
只调 vector_recall(=S_rag)却自称测了 S_star。

覆盖两条 S_star 的结构性行为:
  1. 有证据 → 返回带 8 标签的 context_pack,7 步 plan 全部执行,不弃答。
  2. 空库 → 结构化弃答(abstained=True, reason=low_score),这正是 S_rag
     无法表达、而 S_star 在 abstention 子集上强于 S_rag 的结构来源。

离线管线装配沿用 test_semantic_retrieve_e2e.py 的既有 pattern(同一 emb/idx
喂 worker + retriever,raw sqlite3 seed 到已迁移的同一 db 文件)。
"""
from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime

_SEVEN_STEPS = ["parse", "mask", "plan", "fetch", "fuse", "ground", "abstain"]


@pytest.fixture
def rt(tmp_path):
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_statement(rt, stmt_id, obj):
    """render_text = "bob knows <obj>"; distinct obj → distinct stub embedding.

    Same 24-col INSERT + committed-before-worker discipline as
    test_semantic_retrieve_e2e.py (keeps WAL writers sequential).
    """
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", obj, "a" * 64, "v1", "believes", "pos", 0.9,
             "2026-05-30T09:00:00Z", 0.5, "{}", 0.0, "2026-05-30T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-30T09:00:00Z", "2026-05-30T09:00:00Z"))
        c.commit()


def _planner(rt):
    """Offline S_star pipeline: shared stub emb/idx feed worker + retriever +
    planner. Returns (planner, emb, idx) — caller holds emb/idx so keep_alive
    keeps the C++ refs alive for the planner's lifetime."""
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    _core.EmbeddingWorker(rt.adapter, emb, idx).tick_one_batch(
        "2026-05-30T10:00:00Z")
    semantic = _core.SemanticRetriever(rt.adapter, emb, idx)
    return _core.RetrievalPlanner(rt.adapter, semantic), emb, idx


def _query(text):
    q = _core.PlannerQuery()
    q.tenant_id = "default"
    q.querier = "alice"
    q.perspective = ""
    q.intent = _core.QueryIntent.FACT_LOOKUP
    q.text = text
    q.as_of_iso8601 = "2026-06-01T00:00:00Z"
    q.k = 5
    q.trace_id = "trace-sstar"
    q.query_id = "query-sstar"
    return q


def test_sstar_returns_labelled_context_pack(rt):
    _seed_statement(rt, "s1", "cats")
    _seed_statement(rt, "s2", "stocks")
    planner, _emb, _idx = _planner(rt)

    res = planner.run(_query("bob knows cats"))

    assert res.abstained is False
    assert len(res.entries) >= 1
    # top entry is the exact-text match (stub embedding is deterministic).
    assert res.entries[0].row.id == "s1"
    # 8-label context_pack is populated and machine-labelled (not raw text).
    assert res.entries[0].label == _core.ContextPackLabel.FACT
    assert "[FACT]" in res.context_pack
    # all 7 planner steps ran, in order — this is the S_star discriminator.
    assert [s.step for s in res.receipt.plan_steps] == _SEVEN_STEPS
    # perspective mask ran with querier's own view.
    assert res.receipt.perspective == "alice"


def test_sstar_abstains_on_empty_store(rt):
    # no seed, no embed → nothing recallable.
    planner, _emb, _idx = _planner(rt)

    res = planner.run(_query("who owns the auth module"))

    # structured abstention — the epistemic-honesty behaviour S_rag cannot express.
    assert res.abstained is True
    assert res.receipt.abstention_reason == "low_score"
    assert res.entries == []
    assert "[ABSTAIN]" in res.context_pack
