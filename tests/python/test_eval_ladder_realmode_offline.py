"""PR-3: 归因阶梯 real-mode 接线的**离线**测试(scripts/eval_ladder._real_answer)。

real-mode 被拆成两层:检索装配(离线可测)+ 答题/抽取(gated 网络)。本测试
用注入的 stub 工厂(StubEmbeddingAdapter + 确定性 mock answerer + mock extractor)
驱动 _real_answer 的**全装配逻辑**,证明六台阶接线端到端可跑而无需任何网络。
真跑时未测的只剩 answerer/Extractor 的网络部分。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_LADDER = _SCRIPTS / "eval_ladder.py"
_spec = importlib.util.spec_from_file_location("eval_ladder", _LADDER)
ladder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ladder)

from starling import _core, runtime  # noqa: E402

_KEEPALIVE = []  # hold emb/idx/rt refs alive (C++ keep_alive needs them)


REC = {
    "item_id": "r0", "subset": "knowledge-update",
    "question": "Who currently owns the auth service?",
    "options": ["Bob", "Carol", "Dana", "Alice"], "answer": 1,
    "history": [
        {"speaker": "alice", "text": "Bob owns the auth service.",
         "observed_at": "2026-04-01T10:00:00Z"},
        {"speaker": "alice", "text": "Carol has taken over auth from Bob.",
         "observed_at": "2026-05-01T10:00:00Z"},
    ],
    "gold_statements": [
        {"holder": "alice", "subject": "carol", "predicate": "owns",
         "object": "gold-injected fact", "observed_at": "2026-05-01T10:00:00Z"},
    ],
}


def _make_pipeline(db_path):
    rt = runtime._build_local_store_sqlite_runtime(Path(db_path))
    rt.start()
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    _KEEPALIVE.append((rt, emb, idx))  # keep alive for the test's lifetime
    return rt.adapter, emb, idx


def _mock_extract(adapter, record):
    # stand in for the real Extractor: seed one attributed statement
    import eval_ladder_pipeline as pipe
    pipe.seed_gold_statements(str(adapter.db_path), record["item_id"], [
        {"holder": "alice", "subject": "carol", "predicate": "said",
         "object": "Extractor-derived attributed statement",
         "observed_at": "2026-05-01T10:00:00Z"},
    ])


def _answerer_correct(prompt, backbone):
    return "1"   # always the correct index → isolates retrieval assembly


def _cfg(answerer=_answerer_correct):
    return {"core": _core, "make_pipeline": _make_pipeline,
            "extract": _mock_extract, "answerer": answerer,
            "k": 10, "now_iso": "2026-06-01T00:00:00Z", "backbone": "stub"}


def _run_stage(stage, rec, answerer=_answerer_correct):
    return ladder._real_answer(stage, rec, 0, _cfg(answerer))


def test_all_six_stages_wire_end_to_end_offline():
    for stage in ladder.ALL_STAGES:
        ok = _run_stage(stage, REC)
        assert isinstance(ok, bool)


def test_correct_answerer_scores_hit_when_memory_present():
    # with the correct-index answerer, non-empty-recall stages score a hit
    assert _run_stage("S_rag", REC) is True
    assert _run_stage("S_star", REC) is True
    assert _run_stage("S_star_oracle", REC) is True


def test_wrong_answerer_scores_miss():
    assert _run_stage("S_rag", REC, answerer=lambda p, b: "0") is False


def test_star_oracle_seeds_gold_not_history():
    # oracle stage's recall block must reflect the gold-injected statement
    rb = ladder._real_answer  # sanity: callable
    assert callable(rb)
    # drive the assembly directly via the pipeline to inspect the block
    import eval_ladder_pipeline as pipe
    import tempfile
    d = tempfile.mkdtemp(prefix="ladder_oracle_")
    dbp = f"{d}/o.db"
    adapter, emb, idx = _make_pipeline(dbp)
    pipe.seed_gold_statements(dbp, REC["item_id"], REC["gold_statements"])
    pipe.embed_seeded(_core, adapter, emb, idx, "2026-06-01T00:00:00Z")
    rbk = pipe.recall_block(_core, "S_star_oracle", adapter=adapter, embedder=emb,
                            index=idx, question=REC["question"],
                            history=REC["history"], k=10, seed=0)
    assert "gold-injected fact" in rbk["block"]


def test_abstain_item_scores_on_abstention():
    abstain_rec = dict(REC, is_abstain=True, history=[], gold_statements=[])
    # empty store → planner abstains → is_abstain item scored correct
    assert _run_stage("S_star", abstain_rec) is True
