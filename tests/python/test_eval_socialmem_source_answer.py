"""WP1.B:来源路径答题读数(参照臂分派、逐题留痕与续跑、按网络配对区间、读法判定)的离线测试。

无网络、无模型;原生来源库用桩嵌入在临时目录里现建。官方提示用带占位符的最小桩模板。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_KEEP: list = []
NOW = "2026-12-08T00:00:00Z"

TURNS = [
    {"speaker": "Ada", "text": "Copper lantern in Kyoto.", "turn_id": "s1_t2", "session_id": "s1",
     "turn_index": 2, "observed_at": "2025-01-01T10:00:00Z"},
    {"speaker": "Bob", "text": "I prefer green tea.", "turn_id": "s1_t3", "session_id": "s1",
     "turn_index": 3, "observed_at": "2025-01-01T10:05:00Z"},
]
PROMPTS = {
    "answer": {
        "multiple_choice": "MC-PROMPT\n[MEMORIES]\n{context}\n[QUESTION]\n{question}\n[OPTIONS]\n{options}\n",
        "open_ended": "OE-PROMPT\n[MEMORIES]\n{context}\n[QUESTION]\n{question}\n",
    },
    "llm_answer": {"multiple_choice": "x {context} {question} {options}", "open_ended": "x {context} {question}"},
    "llm_judge": {"system_prompt": "SYS", "user_prompt": "Q:{question} G:{golden_answer} C:{generated_answer}"},
}
RECALL = {
    "block": '[SOURCE] {"speaker":"Ada"} text="Copper lantern in Kyoto."\n[SOURCE] {"speaker":"Bob"} text="I prefer green tea."',
    "source_refs": [{"turn_id": "s1_t2"}, {"turn_id": "s1_t3"}], "context_bytes": 120, "source_count": 2,
}


def _load():
    path = _SCRIPTS / "eval_socialmem_source_answer.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_source_answer.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location("eval_socialmem_source_answer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free(item="f0", gold=("s1_t2",), **over):
    rec = {"item_id": item, "query_type": "Q5", "answer_format": "long_form", "question": "copper lantern Kyoto",
           "answer": "Ada knows about the copper lantern.", "options": [], "history": TURNS,
           "gold_statements": [{"turn_id": t, "object": "x"} for t in gold], "source": {"network_id": "n1"}}
    rec.update(over)
    return rec


def _mc(item="m0", **over):
    rec = _free(item, query_type="Q4", answer_format="multiple_choice", answer=1,
                options=["Bob", "Carol", "Dana", "Alice"], question="Who prefers green tea?")
    rec.update(over)
    return rec


def _library(tmp_path):
    from starling import _core, runtime
    lib = tmp_path / "lib.db"
    rt = runtime._build_local_store_sqlite_runtime(lib)
    rt.start()
    _KEEP.append(rt)
    _core.retain_source_turns(rt.adapter, "default", ["Ada", "Bob"], json.dumps(TURNS), "2026-01-01T00:00:00Z")
    return lib


def _judge(score):
    calls = []

    def judge(question, reference, candidate, backbone):
        calls.append((question, reference, candidate, backbone))
        return {"score": score, "rationale": "r", "raw": json.dumps({"score": score}), "status": "ok"}

    judge.calls = calls
    return judge


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------- 臂的定义与召回分派 ----------------------------

def test_arm_specs_follow_the_registration():
    mod = _load()
    assert mod.ARMS == ("src_base", "src_gold", "src_gold_ctx")
    assert mod.arm_spec("src_base") == {"kind": "replay", "strategy": "focused_window", "k": 30,
                                        "max_context_bytes": 8000}
    assert mod.arm_spec("src_gold") == {"kind": "oracle", "radius": 0}
    assert mod.arm_spec("src_gold_ctx") == {"kind": "oracle", "radius": 2}
    with pytest.raises(ValueError, match="arm"):
        mod.arm_spec("nope")


def test_build_recall_dispatches_to_the_native_replay_and_the_gold_reference(tmp_path):
    mod = _load()
    lib = _library(tmp_path)
    rec = _free()
    base = mod.build_recall("src_base", rec, lib, tmp_path / "w", now_iso=NOW)
    assert "s1_t2" in [r["turn_id"] for r in base["source_refs"]]
    gold = mod.build_recall("src_gold", rec, lib, tmp_path / "w", now_iso=NOW)
    assert [r["turn_id"] for r in gold["source_refs"]] == ["s1_t2"]
    ctx = mod.build_recall("src_gold_ctx", rec, lib, tmp_path / "w", now_iso=NOW)
    assert [r["turn_id"] for r in ctx["source_refs"]] == ["s1_t2", "s1_t3"]
    for out in (base, gold, ctx):
        assert out["context_bytes"] == len(out["block"].encode("utf-8"))
    assert list((tmp_path / "w").glob("*")) == []


# ---------------------------- 单题作答与判分 ----------------------------

@pytest.mark.parametrize("score,expected", [(0.9, True), (0.7, True), (0.69, False)])
def test_answer_item_scores_open_ended_at_the_official_threshold(score, expected):
    mod = _load()
    judge = _judge(score)
    row = mod.answer_item(_free(), RECALL, prompts=PROMPTS, answerer=lambda p, b: "Ada knows.", judge=judge,
                          strict_judge=None, backbone="stub", judge_model="")
    assert row["ok"] is expected and row["score"] == score and row["judge_status"] == "ok"
    assert row["prompt"].startswith("OE-PROMPT")
    assert '- [SOURCE] {"speaker":"Ada"}' in row["prompt"]
    assert row["response"] == "Ada knows." and row["strict_verdict"] is None
    assert row["recall_block"] == RECALL["block"].split("\n")
    assert row["source_turn_ids"] == ["s1_t2", "s1_t3"]
    assert judge.calls == [("copper lantern Kyoto", "Ada knows about the copper lantern.", "Ada knows.", "stub")]


def test_answer_item_routes_the_judge_model_and_records_the_strict_verdict():
    mod = _load()
    judge = _judge(1.0)
    row = mod.answer_item(_free(), RECALL, prompts=PROMPTS, answerer=lambda p, b: "A", judge=judge,
                          strict_judge=lambda q, r, c, b: False, backbone="stub", judge_model="judge-m")
    assert judge.calls[0][3] == "judge-m" and row["strict_verdict"] is False and row["ok"] is True


def test_answer_item_multiple_choice_uses_letters_and_never_calls_the_judge():
    mod = _load()
    judge = _judge(1.0)
    row = mod.answer_item(_mc(), RECALL, prompts=PROMPTS, answerer=lambda p, b: "B", judge=judge,
                          strict_judge=None, backbone="stub", judge_model="")
    assert row["ok"] is True and row["score"] == 1.0 and "A. Bob\nB. Carol" in row["prompt"]
    assert row["judge_status"] is None and row["judge_raw"] is None and judge.calls == []
    wrong = mod.answer_item(_mc(), RECALL, prompts=PROMPTS, answerer=lambda p, b: "1", judge=judge,
                            strict_judge=None, backbone="stub", judge_model="")
    assert wrong["ok"] is False and wrong["score"] == 0.0


def test_answer_item_states_an_empty_recall_explicitly():
    mod = _load()
    empty = {"block": "", "source_refs": [], "context_bytes": 0, "source_count": 0}
    row = mod.answer_item(_free(), empty, prompts=PROMPTS, answerer=lambda p, b: "none", judge=_judge(0.0),
                          strict_judge=None, backbone="stub", judge_model="")
    assert "[No memories retrieved]" in row["prompt"] and row["recall_block"] == []


# ---------------------------- 逐题留痕与续跑 ----------------------------

def test_run_arm_journals_every_item_and_resumes_without_recomputing(tmp_path):
    mod = _load()
    recs = [_free("a"), _free("b", query_type="Q9")]
    journal = tmp_path / "j.jsonl"
    calls = []

    def recall_for(r):
        calls.append(("recall", r["item_id"]))
        return RECALL

    def answer_for(r, recall):
        calls.append(("answer", r["item_id"]))
        good = r["item_id"] == "a"
        return {"ok": good, "score": 1.0 if good else 0.0, "response": "x", "query_type": r["query_type"]}

    rows = mod.run_arm("src_base", recs, recall_for, answer_for, journal=journal)
    assert [r["item_id"] for r in rows] == ["a", "b"]
    lines = _rows(journal)
    assert [row["key"] for row in lines] == ["src_base|a", "src_base|b"]
    assert all({"arm", "item_id", "ok", "score"} <= set(row) for row in lines)
    calls.clear()
    again = mod.run_arm("src_base", recs, recall_for, answer_for, journal=journal)
    assert calls == [] and [r["item_id"] for r in again] == ["a", "b"] and again[0]["score"] == 1.0


def test_run_arm_isolates_a_failing_item_and_retries_it_on_the_next_run(tmp_path):
    mod = _load()
    recs = [_free("a"), _free("b")]
    journal = tmp_path / "j.jsonl"

    def broken(r, recall):
        if r["item_id"] == "a":
            raise RuntimeError("boom")
        return {"ok": True, "score": 1.0}

    rows = mod.run_arm("src_base", recs, lambda r: RECALL, broken, journal=journal)
    assert [r["item_id"] for r in rows] == ["b"]
    first = _rows(journal)[0]
    assert first["item_id"] == "a" and "error" in first and "ok" not in first
    seen = []

    def fixed(r, recall):
        seen.append(r["item_id"])
        return {"ok": True, "score": 0.5}

    rows = mod.run_arm("src_base", recs, lambda r: RECALL, fixed, journal=journal)
    assert seen == ["a"] and [r["item_id"] for r in rows] == ["a", "b"]


def test_load_rows_lets_a_later_good_row_win_and_ignores_error_rows(tmp_path):
    mod = _load()
    journal = tmp_path / "j.jsonl"
    journal.write_text("\n".join(json.dumps(r) for r in [
        {"key": "src_base|a", "arm": "src_base", "item_id": "a", "error": "x"},
        {"key": "src_base|a", "arm": "src_base", "item_id": "a", "ok": False, "score": 0.1},
        {"key": "src_base|a", "arm": "src_base", "item_id": "a", "ok": True, "score": 0.9},
        {"key": "src_base|a", "arm": "src_base", "item_id": "a", "error": "later failure"},
    ]) + "\n{broken\n", encoding="utf-8")
    assert mod.load_rows(journal)["a"]["score"] == 0.9
    assert mod.load_rows(tmp_path / "missing.jsonl") == {}


# ---------------------------- 按网络配对区间与读法 ----------------------------

def test_bootstrap_is_deterministic_and_collapses_on_constant_differences():
    mod = _load()
    items = [("n1", 0.5, 0.7), ("n1", 0.1, 0.3), ("n2", 0.9, 1.1), ("n3", 0.0, 0.2)]
    out = mod.paired_network_bootstrap(items, seed=1, draws=500)
    assert out["n"] == 4 and out["delta"] == pytest.approx(0.2)
    assert out["lo"] == pytest.approx(0.2) and out["hi"] == pytest.approx(0.2)
    assert out == mod.paired_network_bootstrap(items, seed=1, draws=500)


def test_bootstrap_resamples_whole_networks():
    mod = _load()
    out = mod.paired_network_bootstrap([("n1", 1.0, 0.0), ("n2", 0.0, 0.0)], seed=7, draws=5000)
    assert out["delta"] == pytest.approx(-0.5)
    assert out["lo"] == pytest.approx(-1.0) and out["hi"] == pytest.approx(0.0)
    assert out["mean_a"] == pytest.approx(0.5) and out["mean_b"] == pytest.approx(0.0)


def test_bootstrap_rejects_an_empty_item_list():
    mod = _load()
    with pytest.raises(ValueError, match="items"):
        mod.paired_network_bootstrap([], seed=1, draws=10)


@pytest.mark.parametrize("delta,lo,label", [
    (-0.02, -0.08, "来源路径已接近全历史"), (-0.02, -0.15, "无法区分"),
    (-0.11, -0.2, "来源路径落后全历史"), (-0.07, -0.12, "无法区分")])
def test_rule_one_reads_the_source_path_against_the_full_history(delta, lo, label):
    assert _load().read_base_vs_full(delta, lo) == label


@pytest.mark.parametrize("delta,lo,label", [
    (0.12, 0.01, "召回有可挖空间"), (0.12, 0.0, "无法区分"),
    (0.04, -0.1, "召回不是主要限制"), (0.07, -0.05, "无法区分")])
def test_rule_two_reads_the_gold_reference_against_the_source_path(delta, lo, label):
    assert _load().read_gold_vs_base(delta, lo) == label


# ---------------------------- 二裁选取 ----------------------------

def test_second_judge_selection_is_hash_ordered_and_open_ended_only():
    mod = _load()
    rows = [{"item_id": f"q{i}", "arm": "src_base", "answer_format": "long_form", "response": "r"} for i in range(6)]
    rows += [{"item_id": "m", "arm": "src_base", "answer_format": "multiple_choice", "response": "B"},
             {"item_id": "e", "arm": "src_base", "answer_format": "long_form", "response": "  "}]
    got = mod.second_judge_selection(rows, 3)
    eligible = [r for r in rows if r["answer_format"] != "multiple_choice" and r["response"].strip()]
    expected = sorted(eligible, key=lambda r: hashlib.sha256(f"{r['item_id']}|{r['arm']}".encode()).hexdigest())[:3]
    assert [(r["item_id"], r["arm"]) for r in got] == [(r["item_id"], r["arm"]) for r in expected]
    assert len(mod.second_judge_selection(rows, 40)) == len(eligible)


# ---------------------------- 命令行与汇总 ----------------------------

def _run_args(tmp_path, *extra):
    return ["run", "--arm", "src_base", "--out", str(tmp_path / "o"), "--prompts", str(tmp_path / "p.yaml"),
            "--prompts-sha256", "0" * 64, "--judge-model", "m", *extra]


def test_main_run_refuses_without_real_run_and_touches_nothing(tmp_path, capsys):
    mod = _load()
    assert mod.main(_run_args(tmp_path)) == 1
    assert "--real-run" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


def test_main_rejects_an_unknown_arm(tmp_path):
    mod = _load()
    args = _run_args(tmp_path)
    args[2] = "nope"
    with pytest.raises(SystemExit):
        mod.main(args)


def _brec(item, qt, net, fmt="long_form"):
    return {"item_id": item, "query_type": qt, "answer_format": fmt, "source": {"network_id": net}}


def _srow(score, ok=None):
    return {"score": score, "ok": (score >= 0.7) if ok is None else ok}


def _report_inputs():
    recs = [_brec("a", "Q5", "n1"), _brec("b", "Q5", "n2"), _brec("c", "Q9", "n3"),
            _brec("d", "Q2", "n1", "multiple_choice")]
    full = {"a": _srow(0.9), "b": _srow(0.8), "c": _srow(1.0), "d": _srow(1.0)}
    base = {"a": _srow(0.9), "b": _srow(0.75), "c": _srow(1.0), "d": _srow(0.0, False)}
    ctx = {"a": _srow(1.0), "b": _srow(1.0), "c": _srow(1.0), "d": _srow(1.0)}
    return recs, {"src_base": base, "src_gold": dict(ctx), "src_gold_ctx": ctx}, full


def test_build_report_pairs_arms_by_item_and_applies_the_registered_reads():
    mod = _load()
    recs, arms, full = _report_inputs()
    rep = mod.build_report(recs, arms, full, seed=1, draws=5000)
    prim = rep["arms"]["src_base"]["q5q9"]
    assert prim["n"] == 3 and prim["ge07"] == 3 and prim["mean_score"] == pytest.approx((0.9 + 0.75 + 1.0) / 3)
    assert rep["arms"]["S_full"]["q5q9"]["mean_score"] == pytest.approx((0.9 + 0.8 + 1.0) / 3)
    bf = rep["paired"]["base_vs_full"]
    assert bf["n"] == 3 and bf["delta"] == pytest.approx((0.9 + 0.75 + 1.0) / 3 - (0.9 + 0.8 + 1.0) / 3)
    assert bf["read"] == mod.read_base_vs_full(bf["delta"], bf["lo"])
    gb = rep["paired"]["gold_ctx_vs_base"]
    assert gb["n"] == 3 and gb["delta"] == pytest.approx(1.0 - (0.9 + 0.75 + 1.0) / 3)
    assert gb["read"] == mod.read_gold_vs_base(gb["delta"], gb["lo"])
    assert rep["paired"]["gold_ctx_vs_gold"]["delta"] == pytest.approx(0.0)
    assert "read" not in rep["paired"]["gold_ctx_vs_gold"]
    assert rep["mc"]["Q2"] == {"n": 1, "src_base": 0, "src_gold": 1, "src_gold_ctx": 1, "S_full": 1}


def test_build_report_excludes_items_an_arm_has_no_row_for():
    mod = _load()
    recs, arms, full = _report_inputs()
    del arms["src_base"]["c"]
    rep = mod.build_report(recs, arms, full, seed=1, draws=500)
    assert rep["arms"]["src_base"]["q5q9"]["n"] == 2 and rep["arms"]["src_base"]["missing"] == 1
    assert rep["paired"]["base_vs_full"]["n"] == 2
    assert rep["arms"]["src_gold"]["missing"] == 0


# ---------------------------- regex_fallback 的分数不进汇总、计入中止线(WP1.B 事后修订) ----------------------------

def _fallback_answer(n_bad):
    state = {"i": 0}

    def answer_for(record, recall):
        state["i"] += 1
        return {"ok": True, "score": 1.0, "judge_status": "regex_fallback" if state["i"] <= n_bad else "ok"}

    return answer_for


def test_build_report_excludes_regex_fallback_scores_and_lists_them():
    mod = _load()
    recs, arms, full = _report_inputs()
    arms["src_gold_ctx"]["b"] = dict(arms["src_gold_ctx"]["b"], judge_status="regex_fallback")
    rep = mod.build_report(recs, arms, full, seed=1, draws=500)
    ctx = rep["arms"]["src_gold_ctx"]
    assert ctx["q5q9"]["n"] == 2 and ctx["regex_fallback"] == ["b"]
    assert rep["arms"]["src_base"]["regex_fallback"] == []
    assert rep["paired"]["gold_ctx_vs_base"]["n"] == 2
    assert rep["paired"]["gold_ctx_vs_gold"]["n"] == 2


def test_run_arm_aborts_when_regex_fallback_replies_exceed_the_parse_limit(tmp_path):
    mod = _load()
    recs = [_free(f"i{n}") for n in range(31)]
    with pytest.raises(RuntimeError, match="abort"):
        mod.run_arm("src_base", recs, lambda r: RECALL, _fallback_answer(3), journal=tmp_path / "j.jsonl")


def test_run_arm_tolerates_a_single_regex_fallback_reply(tmp_path):
    """防线:低于 5% 的偶发回退不中止(实现前后都应通过)。"""
    mod = _load()
    recs = [_free(f"i{n}") for n in range(31)]
    rows = mod.run_arm("src_base", recs, lambda r: RECALL, _fallback_answer(1), journal=tmp_path / "j.jsonl")
    assert len(rows) == 31


# ---------------------------- WP1.E:放大 k 的来源臂与噪声基线 ----------------------------

def _wp1e_need(name):
    fn = getattr(_load(), name, None)
    if fn is None:
        pytest.fail(f"scripts/eval_socialmem_source_answer.py 尚无 {name}(功能缺失)")
    return fn


def test_answer_arms_extend_the_wp1b_arms_without_touching_them():
    mod = _load()
    assert mod.ARMS == ("src_base", "src_gold", "src_gold_ctx")          # 防线:WP1.B 的臂不变
    assert getattr(mod, "ANSWER_ARMS", None) == mod.ARMS + ("src_cov60", "src_base_rerun")
    assert mod.arm_spec("src_cov60") == {"kind": "replay", "strategy": "focused_coverage", "k": 60,
                                         "max_context_bytes": 16000}
    assert mod.arm_spec("src_base_rerun") == mod.arm_spec("src_base")


def test_build_recall_runs_the_extended_k_arm_and_the_rerun_arm_on_the_native_replay(tmp_path):
    mod = _load()
    lib, rec = _library(tmp_path), _free()
    cov = mod.build_recall("src_cov60", rec, lib, tmp_path / "w", now_iso=NOW)
    assert "s1_t2" in [r["turn_id"] for r in cov["source_refs"]]
    assert cov["context_bytes"] == len(cov["block"].encode("utf-8"))
    base = mod.build_recall("src_base", rec, lib, tmp_path / "w", now_iso=NOW)
    rerun = mod.build_recall("src_base_rerun", rec, lib, tmp_path / "w", now_iso=NOW)
    assert rerun["block"] == base["block"] and rerun["source_refs"] == base["source_refs"]
    assert list((tmp_path / "w").glob("*")) == []


@pytest.mark.parametrize("delta,lo,label", [
    (0.12, 0.01, "放大 k 有可确认的选择题增益"), (0.10, 0.02, "放大 k 有可确认的选择题增益"),
    (0.12, 0.0, "无法区分"), (0.05, 0.01, "无法区分"),
    (0.04, -0.10, "放大 k 对选择题没有增益"), (-0.08, -0.20, "放大 k 对选择题没有增益")])
def test_rule_three_reads_the_extended_k_arm_on_multiple_choice(delta, lo, label):
    assert _wp1e_need("read_cov_mc_vs_base")(delta, lo) == label


def _wp1e_inputs():
    recs = [_brec("a", "Q5", "n1"), _brec("b", "Q9", "n2"), _brec("c", "Q2", "n1", "multiple_choice"),
            _brec("d", "Q6", "n2", "multiple_choice"), _brec("e", "Q4", "n3", "multiple_choice")]
    base = {"a": _srow(0.5), "b": _srow(0.7), "c": _srow(0.0, False), "d": _srow(0.0, False), "e": _srow(1.0)}
    cov = {"a": _srow(0.9), "b": _srow(0.7), "c": _srow(1.0), "d": _srow(1.0), "e": _srow(0.0, False)}
    rerun = {"a": _srow(0.6), "b": _srow(0.7), "c": _srow(0.0, False), "d": _srow(1.0), "e": _srow(1.0)}
    full = {"a": _srow(0.9), "b": _srow(0.8), "c": _srow(1.0), "d": _srow(0.0, False), "e": _srow(1.0)}
    arms = {"src_base": base, "src_gold": dict(base), "src_gold_ctx": dict(base),
            "src_cov60": cov, "src_base_rerun": rerun}
    return recs, arms, full


def test_build_report_pairs_the_extended_arm_and_measures_the_rerun_noise():
    mod = _load()
    recs, arms, full = _wp1e_inputs()
    rep = mod.build_report(recs, arms, full, seed=1, draws=2000)
    assert rep["arms"]["src_cov60"]["q5q9"]["n"] == 2
    assert rep["arms"]["src_cov60"]["q5q9"]["mean_score"] == pytest.approx(0.8)
    assert rep["mc"]["Q2"]["src_cov60"] == 1 and rep["mc"]["Q6"]["src_base_rerun"] == 1
    assert rep["mc"]["Q4"] == {"n": 1, "src_base": 1, "src_gold": 1, "src_gold_ctx": 1, "src_cov60": 0,
                               "src_base_rerun": 1, "S_full": 1}
    mc = rep["paired"]["cov60_vs_base_mc"]
    assert mc["n"] == 2 and mc["delta"] == pytest.approx(1.0)
    assert mc["read"] == mod.read_cov_mc_vs_base(mc["delta"], mc["lo"])
    op = rep["paired"]["cov60_vs_base_open"]
    assert op["n"] == 2 and op["delta"] == pytest.approx(0.2) and "read" not in op
    fo = rep["paired"]["cov60_vs_full_open"]
    assert fo["n"] == 2 and fo["delta"] == pytest.approx(0.8 - (0.9 + 0.8) / 2)
    assert fo["read"] == mod.read_base_vs_full(fo["delta"], fo["lo"])
    assert rep["noise"] == {"mc_q2q6_n": 2, "mc_q2q6_flips": 1, "open_n": 2,
                            "open_mean_abs_diff": pytest.approx(0.05)}


def test_build_report_without_extended_arms_is_unchanged():
    """防线:只有 WP1.B 的三个臂时,报告结构与此前相同。"""
    mod = _load()
    recs, arms, full = _report_inputs()
    rep = mod.build_report(recs, arms, full, seed=1, draws=500)
    assert "src_cov60" not in rep["arms"] and "noise" not in rep
    assert set(rep["paired"]) == {"base_vs_full", "gold_ctx_vs_base", "gold_ctx_vs_gold"}


def test_build_report_adds_each_extension_only_when_its_arm_has_rows():
    mod = _load()
    recs, arms, full = _wp1e_inputs()
    only_cov = {k: v for k, v in arms.items() if k != "src_base_rerun"}
    rep = mod.build_report(recs, only_cov, full, seed=1, draws=500)
    assert "cov60_vs_base_mc" in rep["paired"] and "noise" not in rep
    only_rerun = {k: v for k, v in arms.items() if k != "src_cov60"}
    rep = mod.build_report(recs, only_rerun, full, seed=1, draws=500)
    assert "cov60_vs_base_mc" not in rep["paired"] and "noise" in rep


def test_main_run_accepts_the_extended_arm_names(tmp_path, capsys):
    mod = _load()
    args = _run_args(tmp_path)
    args[2] = "src_cov60"
    assert mod.main(args) == 1
    assert "--real-run" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


def _journal(path, arm, rows):
    path.write_text("".join(json.dumps({"item_id": i, "arm": arm, **row}) + "\n" for i, row in rows.items()),
                    encoding="utf-8")


def test_main_report_includes_extended_arms_only_when_their_journal_exists(tmp_path):
    mod = _load()
    recs, arms, full = _wp1e_inputs()
    corpus, full_path, out, result = tmp_path / "c.jsonl", tmp_path / "full.jsonl", tmp_path / "o", tmp_path / "r.json"
    corpus.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    full_path.write_text("".join(json.dumps({"item_id": i, "stage": "S_full", "backbone": "m", "seed": 0, **row})
                                 + "\n" for i, row in full.items()), encoding="utf-8")   # 真梯子 journal 带 stage
    out.mkdir()
    for arm in ("src_base", "src_gold", "src_gold_ctx"):
        _journal(out / f"{arm}_journal.jsonl", arm, arms[arm])
    argv = ["report", "--out", str(out), "--corpus", str(corpus), "--full-journal", str(full_path),
            "--result", str(result)]
    assert mod.main(argv) == 0
    first = json.loads(result.read_text(encoding="utf-8"))
    assert "src_cov60" not in first["arms"] and "noise" not in first
    _journal(out / "src_cov60_journal.jsonl", "src_cov60", arms["src_cov60"])
    _journal(out / "src_base_rerun_journal.jsonl", "src_base_rerun", arms["src_base_rerun"])
    assert mod.main(argv) == 0
    second = json.loads(result.read_text(encoding="utf-8"))
    assert "src_cov60" in second["arms"] and "cov60_vs_base_mc" in second["paired"] and "noise" in second


def test_build_report_excludes_parse_failed_scores_like_regex_fallback():
    mod = _load()
    recs, arms, full = _report_inputs()
    arms["src_gold_ctx"]["b"] = dict(arms["src_gold_ctx"]["b"], judge_status="parse_failed", score=0.0, ok=False)
    rep = mod.build_report(recs, arms, full, seed=1, draws=500)
    ctx = rep["arms"]["src_gold_ctx"]
    assert ctx["q5q9"]["n"] == 2 and ctx["regex_fallback"] == ["b"]
    assert rep["paired"]["gold_ctx_vs_base"]["n"] == 2


def test_load_full_rows_keeps_only_the_s_full_stage_and_refuses_a_mixed_or_ambiguous_journal(tmp_path):
    mod = _load()
    path = tmp_path / "ladder.jsonl"

    def row(stage, item, score, backbone="m", seed=0):
        return {"key": f"{stage}|{backbone}|{seed}|{item}", "stage": stage, "backbone": backbone, "seed": seed,
                "item_id": item, "ok": score >= 0.7, "score": score, "judge_status": "ok"}

    # 多台阶 journal:S_full 之后还有 S_star 的同题行,旧逻辑会用最后一行覆盖
    path.write_text("".join(json.dumps(r) + "\n" for r in (
        row("S_full", "a", 1.0), row("S_full", "b", 0.9), row("S_star", "a", 0.0), row("S_star", "b", 0.0))),
        encoding="utf-8")
    full = mod.load_full_rows(path)
    assert {i: r["score"] for i, r in full.items()} == {"a": 1.0, "b": 0.9}
    # 同一题在 S_full 下有两个 backbone 或 seed:基线不唯一,拒绝
    path.write_text("".join(json.dumps(r) + "\n" for r in (
        row("S_full", "a", 1.0), row("S_full", "a", 0.5, backbone="other"))), encoding="utf-8")
    with pytest.raises(ValueError, match="S_full"):
        mod.load_full_rows(path)
    # 没有任何 S_full 行:拒绝,而不是静默空基线
    path.write_text(json.dumps(row("S_star", "a", 0.0)) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S_full"):
        mod.load_full_rows(path)


def test_append_terminates_a_half_written_last_line_so_the_new_row_is_not_lost(tmp_path):
    mod = _load()
    path = tmp_path / "j.jsonl"
    path.write_text(json.dumps({"key": "a|1", "arm": "a", "item_id": "1", "ok": True, "score": 1.0}) + "\n"
                    + '{"key": "a|2", "arm"', encoding="utf-8")      # 被 kill:第二行只写了一半,没有换行
    mod._append(path, {"key": "a|3", "arm": "a", "item_id": "3", "ok": True, "score": 0.0})
    assert sorted(mod.load_rows(path, "a")) == ["1", "3"]


def test_append_adds_no_blank_line_to_a_complete_or_missing_journal(tmp_path):
    mod = _load()
    path = tmp_path / "sub" / "j.jsonl"
    mod._append(path, {"key": "a|1", "arm": "a", "item_id": "1", "ok": True, "score": 1.0})
    mod._append(path, {"key": "a|2", "arm": "a", "item_id": "2", "ok": True, "score": 0.0})
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    assert sorted(mod.load_rows(path, "a")) == ["1", "2"]
