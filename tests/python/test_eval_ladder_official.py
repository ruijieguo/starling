"""WP0:梯子的官方口径、逐题留痕与网络级库复用的离线测试(无网络)。

用 StubEmbeddingAdapter 与确定性替身驱动 _real_answer / run_cell 的全装配逻辑。
标注「防线」的用例是特征化测试:实现前后都应通过,用来钉住不得改变的既有行为。
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location("eval_ladder", _SCRIPTS / "eval_ladder.py")
ladder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ladder)

import eval_ladder_pipeline as pipe  # noqa: E402  与梯子内部 import 的是同一个模块对象

from starling import _core, runtime  # noqa: E402

_KEEPALIVE = []

HISTORY_A = [
    {"speaker": "Femi", "text": "Residents only parking please", "observed_at": "2025-05-05T11:04:00",
     "session_index": 1, "turn_id": "a_s01_t000"},
    {"speaker": "Marcus", "text": "Fine by me", "observed_at": "2025-05-05T11:20:00",
     "session_index": 1, "turn_id": "a_s01_t001"},
]
HISTORY_B = [dict(HISTORY_A[0], text="A completely different message", turn_id="b_s01_t000"), HISTORY_A[1]]

PROMPTS = {
    "answer": {
        "multiple_choice": "MC-PROMPT\n[MEMORIES]\n{context}\n[QUESTION]\n{question}\n[OPTIONS]\n{options}\n",
        "open_ended": "OE-PROMPT\n[MEMORIES]\n{context}\n[QUESTION]\n{question}\n",
    },
    "llm_answer": {
        "multiple_choice": "LLM-MC\n[CONVERSATION]\n{context}\n[QUESTION]\n{question}\n[OPTIONS]\n{options}\n",
        "open_ended": "LLM-OE\n[CONVERSATION]\n{context}\n[QUESTION]\n{question}\n",
    },
    "llm_judge": {"system_prompt": "SYS", "user_prompt": "Q:{question} G:{golden_answer} C:{generated_answer}"},
}


def _free(item_id="f0", history=None, question="residents only parking please", **over):
    rec = {"item_id": item_id, "subset": "socialmem_free", "question": question, "options": [],
           "answer": "Femi wants residents-only parking.", "answer_format": "long_form",
           "query_type": "Q5", "history": history if history is not None else HISTORY_A,
           "gold_statements": []}
    rec.update(over)
    return rec


def _mc(item_id="m0", **over):
    rec = {"item_id": item_id, "subset": "socialmem_mc", "question": "Who prefers residents only parking?",
           "options": ["Bob", "Carol", "Dana", "Alice"], "answer": 1, "answer_format": "multiple_choice",
           "query_type": "Q4", "history": HISTORY_A, "gold_statements": []}
    rec.update(over)
    return rec


def _make_pipeline(db_path):
    rt = runtime._build_local_store_sqlite_runtime(Path(db_path))
    rt.start()
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    _KEEPALIVE.append((rt, emb, idx))
    return rt.adapter, emb, idx


def _fake_extract(adapter, record, backbone):
    pipe.seed_gold_statements(str(adapter.db_path), record["item_id"], [
        {"holder": "Femi", "subject": "Femi", "predicate": "prefers", "object": "residents only parking",
         "observed_at": "2025-05-05T11:04:00Z"}])


def _cfg(**over):
    cfg = {"core": _core, "make_pipeline": _make_pipeline, "extract": _fake_extract,
           "answerer": lambda prompt, backbone: "A reply", "judge": lambda q, r, c, b: True,
           "k": 10, "now_iso": "2026-06-01T00:00:00Z", "backbone": "stub"}
    cfg.update(over)
    return cfg


def _scoring_judge(score):
    calls = []

    def judge(question, reference, candidate, backbone):
        calls.append({"question": question, "reference": reference, "candidate": candidate, "backbone": backbone})
        return {"score": score, "rationale": "r", "raw": json.dumps({"score": score}), "status": "ok"}

    judge.calls = calls
    return judge


def _strict_judge_must_not_run(*args):
    raise AssertionError("严格裁判不应被调用")


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


# ---------------------------- 逐题留痕 ----------------------------

def test_run_cell_journal_records_trace_and_keeps_the_resume_contract(tmp_path):
    j = tmp_path / "j.jsonl"
    ladder.run_cell("S_rag", "stub", 0, [_free()], False,
                    _cfg(answerer=lambda prompt, backbone: "Femi wants it."), journal=j)
    row = _rows(j)[0]
    for key in ("key", "stage", "backbone", "seed", "item_id", "ok"):
        assert key in row
    assert row["key"] == "S_rag|stub|0|f0" and isinstance(row["ok"], bool)
    assert any("Residents only parking" in line for line in row["recall_block"])
    assert row["recall_abstained"] is False
    assert "residents only parking" in row["prompt"]
    assert row["response"] == "Femi wants it."
    assert ladder.load_journal(j) == {"S_rag|stub|0|f0": row["ok"]}
    assert "score" not in row           # 旧口径下不产出分数字段


def test_journal_trace_tolerates_a_stage_that_fills_no_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(ladder, "_real_answer", lambda stage, rec, seed, cfg: True)
    j = tmp_path / "j.jsonl"
    ladder.run_cell("S_star", "bbA", 0, [_free()], False, {}, journal=j)
    row = _rows(j)[0]
    assert row["ok"] is True
    assert row["recall_block"] is None and row["prompt"] is None and row["response"] is None


def test_journal_rows_never_embed_config_values(tmp_path, monkeypatch):
    """防线:journal 行按白名单构造,不得带出配置或环境里的任何值。"""
    secret = "unit-test-secret-value-123"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    j = tmp_path / "j.jsonl"
    ladder.run_cell("S_rag", "stub", 0, [_free()], False, _cfg(api_key=secret), journal=j)
    assert secret not in j.read_text()


def test_run_cell_reports_scores_only_when_items_produce_them(monkeypatch):
    scores = {"a": 0.9, "b": 0.5, "c": 1.0}

    def fake(stage, rec, seed, cfg):
        cfg["diagnostics"]["score"] = scores[rec["item_id"]]
        return scores[rec["item_id"]] >= 0.7

    monkeypatch.setattr(ladder, "_real_answer", fake)
    corpus = [{"item_id": "a", "subset": "s", "query_type": "Q5"},
              {"item_id": "b", "subset": "s", "query_type": "Q5"},
              {"item_id": "c", "subset": "s", "query_type": "Q2"}]
    cell = ladder.run_cell("S_full", "bb", 0, corpus, False, {})
    assert cell["mean_score"] == pytest.approx((0.9 + 0.5 + 1.0) / 3)
    assert cell["by_query_type"]["Q5"] == {"n": 2, "correct": 1, "mean_score": pytest.approx(0.7)}
    assert cell["by_query_type"]["Q2"]["n"] == 1


def test_fixture_cells_carry_no_score_fields():
    """防线:fixture 产物字节不变。"""
    corpus = [{"item_id": "a0", "subset": "alpha", "options": ["x", "y"], "answer": 0}]
    cell = ladder.run_cell("S0", "bb", 0, corpus, True, {})
    assert "mean_score" not in cell and "by_query_type" not in cell


# ---------------------------- 官方口径 ----------------------------

@pytest.mark.parametrize("score,expected", [(0.9, True), (0.7, True), (0.69, False)])
def test_official_style_free_answer_is_correct_at_the_threshold(score, expected):
    trace = {}
    cfg = _cfg(answer_style="official", official_prompts=PROMPTS, official_judge=_scoring_judge(score),
               judge=_strict_judge_must_not_run, diagnostics=trace)
    assert ladder._real_answer("S_rag", _free(), 0, cfg) is expected
    assert trace["score"] == score and trace["judge_status"] == "ok"
    assert trace["prompt"].startswith("OE-PROMPT")


def test_official_style_multiple_choice_uses_letters():
    trace = {}
    cfg = _cfg(answer_style="official", official_prompts=PROMPTS, answerer=lambda p, b: "B", diagnostics=trace)
    assert ladder._real_answer("S_rag", _mc(), 0, cfg) is True
    assert "A. Bob\nB. Carol" in trace["prompt"] and trace["score"] == 1.0
    cfg2 = _cfg(answer_style="official", official_prompts=PROMPTS, answerer=lambda p, b: "1", diagnostics={})
    assert ladder._real_answer("S_rag", _mc(), 0, cfg2) is False     # 下标写法在官方口径下不计对


def test_official_judge_receives_the_judge_model_when_one_is_set():
    judge = _scoring_judge(1.0)
    ladder._real_answer("S_rag", _free(), 0, _cfg(answer_style="official", official_prompts=PROMPTS,
                                                   official_judge=judge, judge_model="deepseek-v3"))
    ladder._real_answer("S_rag", _free(), 0, _cfg(answer_style="official", official_prompts=PROMPTS,
                                                   official_judge=judge))
    assert [c["backbone"] for c in judge.calls] == ["deepseek-v3", "stub"]


def test_official_style_without_an_official_judge_fails_loudly():
    cfg = _cfg(answer_style="official", official_prompts=PROMPTS)
    with pytest.raises(ValueError, match="official_judge"):
        ladder._real_answer("S_rag", _free(), 0, cfg)


def test_unknown_answer_style_is_rejected():
    with pytest.raises(ValueError, match="answer_style"):
        ladder._real_answer("S_rag", _free(), 0, _cfg(answer_style="bogus"))


def test_strict_corun_records_the_legacy_verdict_next_to_the_official_score():
    trace = {}
    cfg = _cfg(answer_style="official", official_prompts=PROMPTS, official_judge=_scoring_judge(0.9),
               judge=lambda q, r, c, b: False, strict_corun=True, diagnostics=trace)
    assert ladder._real_answer("S_rag", _free(), 0, cfg) is True
    assert trace["strict_verdict"] is False


def test_s_full_official_format_uses_the_llm_answer_template_and_session_headers():
    trace = {}
    cfg = _cfg(answer_style="official", official_prompts=PROMPTS, official_judge=_scoring_judge(1.0),
               full_format="official", diagnostics=trace)
    ladder._real_answer("S_full", _free(), 0, cfg)
    assert trace["prompt"].startswith("LLM-OE")
    assert "--- Session 1, 2025-05-05 ---" in trace["prompt"]
    assert "[Session 1, 11:04am] Femi: Residents only parking please" in trace["prompt"]
    assert "\n- [" not in trace["prompt"]


def test_s_full_default_format_is_unchanged():
    """防线:不开官方口径时 S_full 的提示与现状逐字相同。"""
    trace = {}
    ladder._real_answer("S_full", _free(), 0, _cfg(diagnostics=trace))
    assert "- [2025-05-05T11:04:00] Femi: Residents only parking please" in trace["prompt"]


def test_make_real_answerer_fn_forwards_token_and_thinking_options(monkeypatch):
    import eval_judge_audit as audit_mod
    seen = []
    monkeypatch.setattr(audit_mod, "_chat_completion", lambda prompt, backbone, **kw: seen.append(kw) or "r")
    ladder.make_real_answerer_fn()("p", "m")
    ladder.make_real_answerer_fn(max_tokens=1000, enable_thinking=False)("p", "m")
    assert seen[0] == {"max_tokens": 512}
    assert seen[1] == {"max_tokens": 1000, "enable_thinking": False}


# ---------------------------- 命令行 ----------------------------

def test_cli_rejects_official_style_without_prompts(tmp_path, capsys):
    corpus = tmp_path / "c.jsonl"
    corpus.write_text("{}\n")
    rc = ladder.main(["--benchmark", "x", "--corpus", str(corpus), "--fixture-mode", "--answer-style", "official"])
    assert rc == 1 and "--official-prompts" in capsys.readouterr().err


def test_cli_rejects_official_style_in_fixture_mode(tmp_path, capsys):
    corpus = tmp_path / "c.jsonl"
    corpus.write_text("{}\n")
    rc = ladder.main(["--benchmark", "x", "--corpus", str(corpus), "--fixture-mode",
                      "--answer-style", "official", "--official-prompts", str(tmp_path / "p.yaml")])
    assert rc == 1 and "--real-run" in capsys.readouterr().err


# ---------------------------- 网络级库复用 ----------------------------

def _build_sqlite(path, marker="m"):
    conn = sqlite3.connect(path)
    try:
        conn.execute("create table t(x)")
        conn.execute("insert into t values (?)", (marker,))
        conn.commit()
    finally:
        conn.close()
    return {"marker": marker}


def _values(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("select x from t order by rowid")]
    finally:
        conn.close()


def test_history_key_is_content_addressed():
    a = pipe.history_key(HISTORY_A)
    assert a == pipe.history_key([dict(t) for t in HISTORY_A])
    assert a != pipe.history_key([dict(HISTORY_A[0], text="different")] + HISTORY_A[1:])
    assert len(a) == 10 and set(a) <= set("0123456789abcdef")


def test_library_cache_builds_once_per_stage_and_key(tmp_path):
    cache = pipe.LibraryCache(tmp_path / "cache")
    calls = []

    def build(path):
        calls.append(path)
        return _build_sqlite(path)

    p1, s1, m1 = cache.get_or_build("S_rag", "k1", build)
    p2, s2, m2 = cache.get_or_build("S_rag", "k1", build)
    assert (s1, s2) == ("miss", "hit") and p1 == p2 and len(calls) == 1
    assert m1 == m2 == {"marker": "m"}
    cache.get_or_build("S_star", "k1", build)
    assert len(calls) == 2


def test_checkout_gives_isolated_copies_and_refuses_to_overwrite(tmp_path):
    cache = pipe.LibraryCache(tmp_path / "cache")
    path, _status, _meta = cache.get_or_build("S_rag", "k", _build_sqlite)
    d1, d2 = tmp_path / "q1.db", tmp_path / "q2.db"
    cache.checkout(path, d1)
    cache.checkout(path, d2)
    conn = sqlite3.connect(d1)
    conn.execute("insert into t values ('extra')")
    conn.commit()
    conn.close()
    assert _values(d1) == ["m", "extra"] and _values(d2) == ["m"] and _values(path) == ["m"]
    with pytest.raises(FileExistsError):
        cache.checkout(path, d1)


def test_failed_build_is_not_cached(tmp_path):
    cache = pipe.LibraryCache(tmp_path / "cache")

    def boom(path):
        conn = sqlite3.connect(path)
        conn.execute("create table t(x)")
        conn.commit()
        conn.close()
        raise RuntimeError("extract failed")

    with pytest.raises(RuntimeError, match="extract failed"):
        cache.get_or_build("S_star", "k", boom)
    path, status, _meta = cache.get_or_build("S_star", "k", _build_sqlite)
    assert status == "miss" and _values(path) == ["m"]


def test_s_rag_embeds_each_distinct_history_once(tmp_path, monkeypatch):
    real = pipe.embed_seeded
    embeds = []
    monkeypatch.setattr(pipe, "embed_seeded", lambda *a, **k: embeds.append(1) or real(*a, **k))
    cache = pipe.LibraryCache(tmp_path / "cache")
    traces = [{}, {}, {}]
    for item, trace in zip(("a", "b", "c"), traces):
        ladder._real_answer("S_rag", _free(item), 0, _cfg(library_cache=cache, diagnostics=trace))
    assert len(embeds) == 1
    assert [t["library"]["status"] for t in traces] == ["miss", "hit", "hit"]
    assert "Residents only parking" in traces[2]["recall"]["block"]    # 向量随副本一起可用


def test_s_star_extracts_once_per_history_and_recall_never_touches_the_cached_library(tmp_path):
    extracted = []

    def extract(adapter, record, backbone):
        extracted.append(record["item_id"])
        _fake_extract(adapter, record, backbone)

    def events(db):
        conn = sqlite3.connect(db)
        try:
            return conn.execute("select count(*) from bus_events where event_type='statement.recalled'").fetchone()[0]
        finally:
            conn.close()

    cache = pipe.LibraryCache(tmp_path / "cache")
    question = "Femi prefers residents only parking"
    t1, t2, t3 = {}, {}, {}
    ladder._real_answer("S_star", _free("f0", question=question), 0, _cfg(extract=extract, library_cache=cache, diagnostics=t1))
    ladder._real_answer("S_star", _free("f1", question=question), 0, _cfg(extract=extract, library_cache=cache, diagnostics=t2))
    ladder._real_answer("S_star", _free("f2", history=HISTORY_B, question=question), 0,
                        _cfg(extract=extract, library_cache=cache, diagnostics=t3))
    assert extracted == ["f0", "f2"]
    assert [t["library"]["status"] for t in (t1, t2, t3)] == ["miss", "hit", "miss"]
    cached = t1["library"]["path"]
    assert t1["db_path"] != cached and t2["db_path"] != cached
    assert events(t1["db_path"]) >= 1 and events(t2["db_path"]) >= 1     # 召回写进了各自的副本
    assert events(cached) == 0                                         # 共享库从未被召回写过


def test_cache_mode_builds_no_library_for_s0_and_s_full(tmp_path):
    made = []

    def make(db):
        made.append(db)
        return _make_pipeline(db)

    cache = pipe.LibraryCache(tmp_path / "cache")
    for stage in ("S0", "S_full"):
        ladder._real_answer(stage, _free(), 0, _cfg(make_pipeline=make, library_cache=cache, diagnostics={}))
    assert made == []


def test_without_a_cache_every_stage_still_builds_its_own_library():
    """防线:库缓存默认关闭,行为与现状相同。"""
    made = []

    def make(db):
        made.append(db)
        return _make_pipeline(db)

    for stage in ("S0", "S_full", "S_rag"):
        ladder._real_answer(stage, _free(), 0, _cfg(make_pipeline=make, diagnostics={}))
    assert len(made) == 3


# ---------------------------- 续跑与报告序列化(新增红测) ----------------------------

def test_run_cell_resume_restores_scores_from_the_journal(tmp_path, monkeypatch):
    j = tmp_path / "j.jsonl"
    corpus = [{"item_id": "a", "subset": "s", "query_type": "Q5"},
              {"item_id": "b", "subset": "s", "query_type": "Q5"}]
    scores = {"a": 0.9, "b": 0.5}
    calls = []

    def fake(stage, rec, seed, cfg):
        calls.append(rec["item_id"])
        cfg["diagnostics"]["score"] = scores[rec["item_id"]]
        return scores[rec["item_id"]] >= 0.7

    monkeypatch.setattr(ladder, "_real_answer", fake)
    ladder.run_cell("S_rag", "bb", 0, corpus, False, {}, journal=j)
    done = ladder.load_journal(j)
    calls.clear()
    cell = ladder.run_cell("S_rag", "bb", 0, corpus, False, {}, journal=j, done=done)
    assert calls == []                                   # 续跑不重判
    assert cell["mean_score"] == pytest.approx(0.7)     # 分数从 journal 恢复
    assert cell["by_query_type"]["Q5"]["n"] == 2


def test_report_config_serializes_official_prompts_and_cache_without_leaking_text(tmp_path):
    cache = pipe.LibraryCache(tmp_path / "cache")
    config = {"mode": "real", "answer_style": "official", "official_prompts": PROMPTS,
              "library_cache": cache, "judge": lambda *a: True}
    text = json.dumps(ladder._serializable_config(config), ensure_ascii=False)
    assert "OE-PROMPT" not in text
    assert str(tmp_path / "cache") in text
