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


def _judge_accept(question, reference, candidate, backbone):
    return True   # default accepting judge → isolates retrieval assembly


def _cfg(answerer=_answerer_correct, judge=_judge_accept):
    return {"core": _core, "make_pipeline": _make_pipeline,
            "extract": _mock_extract, "answerer": answerer, "judge": judge,
            "k": 10, "now_iso": "2026-06-01T00:00:00Z", "backbone": "stub"}


def _run_stage(stage, rec, answerer=_answerer_correct, judge=_judge_accept):
    return ladder._real_answer(stage, rec, 0, _cfg(answerer, judge))


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


def test_star_passes_speaker_owned_memories_to_answerer():
    import eval_ladder_pipeline as pipe

    def extract(adapter, record):
        pipe.seed_gold_statements(str(adapter.db_path), record["item_id"], [
            {"holder": "Mei", "subject": "team", "predicate": "has_status",
             "object": "expanding", "observed_at": "2026-05-01T10:00:00Z"},
        ])

    def answerer(prompt, backbone):
        return "1" if "holder Mei" in prompt else "0"

    config = {**_cfg(answerer), "extract": extract}
    record = dict(REC, question="team has_status expanding")
    assert ladder._real_answer("S_star", record, 0, config) is True


def test_real_answer_diagnostics_expose_memory_and_prediction():
    trace = {}
    config = {**_cfg(), "diagnostics": trace}
    record = dict(REC, question="carol said Extractor-derived attributed statement")
    assert ladder._real_answer("S_star", record, 0, config) is True
    assert Path(trace["db_path"]).is_file()
    assert trace["embedding"]["embedded"] == 1
    assert trace["recall"]["receipts"][0]["holder"] == "alice"
    assert trace["recall"]["abstained"] is False
    assert "Extractor-derived attributed statement" in trace["prompt"]
    assert trace["response"] == "1"
    assert trace["prediction"] == 1
    assert trace["ingest_seconds"] >= 0


def test_query_time_normalizes_offset_for_native_core():
    trace = {}
    config = {**_cfg(), "diagnostics": trace, "now_iso": "2026-09-09T17:00:00+08:00"}
    ladder._real_answer("S_star", REC, 0, config)
    assert trace["recall"]["as_of_iso"] == "2026-09-09T09:00:00Z"


@pytest.mark.parametrize("succeeds", [False, True])
def test_real_extraction_checks_final_core_outcome(monkeypatch, tmp_path, succeeds):
    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "extract.db")
    rt.start()
    llm = _core.FakeLLMAdapter()
    llm.set_default_response("[]", succeeds, "" if succeeds else "provider unavailable")
    monkeypatch.setattr(ladder, "_build_extract_llm", lambda *args: llm)
    extract = ladder.make_real_extract_fn(_core)
    record = dict(REC, history=[{"speaker": "Mei", "text": "A synthetic utterance."}])
    if succeeds:
        receipts = extract(rt.adapter, record, "stub")
        assert receipts[0]["holder"] == "Mei"
        assert receipts[0]["extraction_failed"] is False
    else:
        with pytest.raises(RuntimeError, match="extraction failed.*Mei"):
            extract(rt.adapter, record, "stub")


def test_real_extract_factory_accepts_explicit_native_extraction_config():
    """结构化实验必须能显式传入 ExtractionConfig；默认行为仍由旧调用保持。"""
    import inspect

    parameters = inspect.signature(ladder.make_real_extract_fn).parameters
    assert "extraction_config" in parameters


@pytest.mark.parametrize("with_speakers", [False, True])
def test_rag_speaker_control_reaches_prompt(with_speakers):
    trace = {}
    record = dict(REC, history=[{"speaker": "Mei", "text": "I prefer the train."}])
    config = {**_cfg(), "rag_speaker_labels": with_speakers, "diagnostics": trace}
    assert ladder._real_answer("S_rag", record, 0, config) is True
    assert "I prefer the train." in trace["prompt"]
    assert ("Mei:" in trace["prompt"]) is with_speakers
    assert len(trace["recall"]["statement_ids"]) == 1


@pytest.mark.parametrize("mode,visible", [("immediate", False), ("sleep", True)])
def test_star_sleep_exposes_volatile_but_preserves_review_guard(mode, visible):
    import sqlite3
    import eval_ladder_pipeline as pipe

    def extract(adapter, record):
        pipe.seed_gold_statements(str(adapter.db_path), record["item_id"], [
            {"holder": "Mei", "subject": "train", "predicate": "has_status",
             "object": "available"},
            {"holder": "Mei", "subject": "train", "predicate": "has_status",
             "object": "UNREVIEWED"},
        ])
        # Fixture initial conditions; lifecycle transitions below use the native scheduler.
        with sqlite3.connect(str(adapter.db_path)) as conn:
            conn.execute("UPDATE statements SET consolidation_state='volatile'")
            conn.execute("UPDATE statements SET review_status='pending_review' WHERE id='r0-gold1'")

    trace = {}
    record = dict(REC, question="train has_status available")
    config = {**_cfg(), "extract": extract, "star_replay_mode": mode,
              "now_iso": "2026-09-09T09:00:00Z", "diagnostics": trace}
    assert ladder._real_answer("S_star", record, 0, config) is True
    assert ("available" in trace["recall"]["block"]) is visible
    assert "UNREVIEWED" not in trace["recall"]["block"]
    assert trace["recall"]["as_of_iso"] == config["now_iso"]
    assert trace["replay"]["mode"] == mode
    if visible:
        assert trace["replay"]["stats"]["compressed"] == 2
        with sqlite3.connect(trace["db_path"]) as conn:
            assert conn.execute("SELECT review_status FROM statements WHERE id='r0-gold1'").fetchone()[0] == "pending_review"


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


def test_ladder_prompt_never_injects_full_history():
    """归因不变式:阶梯答题 prompt 只喂"该台阶的记忆块"(recalled),绝不无条件
    塞完整 record.history。否则各台阶都能从 always-present history 读到答案:
    S0 地板失真、S_star−S_rag 认知层净贡献信号归零、S_full history 重复。

    钉法:record.history 里放一个 recalled 里绝不会出现的哨兵事实,断言它
    不进 prompt;同时确认 prompt 确实带上了 recalled 的内容。回归此断言即
    重新引入 eval_longmemeval._build_answer_prompt 的长上下文混淆。"""
    sentinel = "SENTINEL-HISTORY-ONLY-FACT-must-not-leak-into-prompt"
    rec = dict(
        REC,
        history=[{"speaker": "alice", "text": sentinel,
                  "observed_at": "2026-04-01T10:00:00Z"}],
    )
    recalled = ["said: Carol has taken over auth from Bob."]
    prompt = ladder._ladder_prompt(rec, recalled)
    assert sentinel not in prompt, "record.history 泄漏进阶梯 prompt(归因混淆回归)"
    assert "Full conversation history" not in prompt, "history 段落不该出现"
    assert recalled[0] in prompt, "该台阶的记忆块必须进 prompt"
    # S_full 的 history 语义不丢:它经 recall_block 进入 block→recalled,而非 prompt 硬编码。
    full_prompt = ladder._ladder_prompt(rec, [f"[t] alice: {sentinel}"])
    assert sentinel in full_prompt, "S_full 台阶经 recalled 传入的 history 必须可达"


# --- 自由文本(long_form/short_answer)打分岔路 ---------------------------------

FREE_REC = dict(
    REC,
    item_id="f0",
    answer_format="long_form",
    options=[],
    answer="Carol currently owns the auth service.",
)


def test_free_text_routes_through_judge_not_index():
    """自由文本题走 judge 路径:answerer 出的是自然语言(非 MC 下标),
    命中与否完全由 judge 决定,而非 _parse_option_index。"""
    calls = {"answerer": 0, "judge": 0}

    def answerer(prompt, backbone):
        calls["answerer"] += 1
        return "Carol owns it now."   # 自然语言,不是下标

    def judge(question, reference, candidate, backbone):
        calls["judge"] += 1
        assert candidate == "Carol owns it now."
        assert reference == FREE_REC["answer"]
        return True

    ok = ladder._real_answer("S_rag", FREE_REC, 0, _cfg(answerer, judge))
    assert ok is True
    assert calls["answerer"] == 1 and calls["judge"] == 1


def test_free_text_judge_rejects_scores_miss():
    """judge 判不等价 → 该题记未命中(与 answerer 文本无关)。"""
    ok = ladder._real_answer("S_rag", FREE_REC, 0,
                             _cfg(answerer=lambda p, b: "wrong answer",
                                  judge=lambda q, r, c, b: False))
    assert ok is False


def test_free_text_all_six_stages_wire_offline():
    for stage in ladder.ALL_STAGES:
        ok = ladder._real_answer(stage, FREE_REC, 0, _cfg())
        assert isinstance(ok, bool)


def test_free_text_prompt_never_injects_full_history():
    """自由文本 prompt 与 MC 同一契约:只喂 recalled,绝不塞完整 record.history。"""
    sentinel = "SENTINEL-FREE-HISTORY-must-not-leak"
    rec = dict(FREE_REC, history=[{"speaker": "alice", "text": sentinel,
                                   "observed_at": "2026-04-01T10:00:00Z"}])
    recalled = ["said: Carol has taken over auth from Bob."]
    prompt = ladder._ladder_prompt_free(rec, recalled)
    assert sentinel not in prompt, "record.history 泄漏进自由文本 prompt(归因混淆回归)"
    assert recalled[0] in prompt, "该台阶的记忆块必须进 prompt"
    assert rec["question"] in prompt, "问题必须进 prompt"
