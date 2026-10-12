"""WP3 全上下文参照臂(开发切分 Q1 Q3 Q7 Q8)的离线测试。无网络、无模型。
登记见 build/prereg_wp3_fullctx.md。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

PROMPTS = {
    "llm_answer": {"open_ended": "FULL<<{context}>> Q={question}",
                   "multiple_choice": "FULLMC<<{context}>> Q={question} O={options}"},
    "answer": {"open_ended": "MEM<<{context}>> Q={question}",
               "multiple_choice": "MEMMC<<{context}>> Q={question} O={options}"},
}


def _load():
    path = _SCRIPTS / "eval_socialmem_wp3_fullctx.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_wp3_fullctx.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location("eval_socialmem_wp3_fullctx", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hist():
    return [
        {"session_index": 1, "observed_at": "2025-10-06T12:08:00", "speaker": "Josh", "text": "hello", "turn_id": "t1"},
        {"session_index": 1, "observed_at": "2025-10-06T14:41:00", "speaker": "Leon", "text": "hi", "turn_id": "t2"},
        {"session_index": 2, "observed_at": "2025-10-07T09:05:00", "speaker": "Josh", "text": "again", "turn_id": "t3"},
    ]


def _rec(item, qt, net, fmt="long_form"):
    return {"item_id": item, "query_type": qt, "answer_format": fmt, "question": f"Q {item}?",
            "answer": "gold", "options": [], "history": _hist(), "source": {"network_id": net}}


def _row(score, status="ok"):
    return {"score": score, "ok": score >= 0.7, "judge_status": status}


def test_arm_label_and_spec_are_fixed():
    mod = _load()
    assert mod.ARM == "wp3_full_ctx"
    assert mod.arm_spec() == {"mode": "full_context", "format": "official", "template": "llm_answer",
                              "history": "whole_history_per_question"}


def test_prompt_is_the_official_full_context_template_not_the_memory_template():
    mod = _load()
    import eval_official_protocol as proto

    rec = _rec("a", "Q1", "n1")
    prompt = mod.build_prompt(PROMPTS, rec)
    assert prompt.startswith("FULL<<--- Session 1, 2025-10-06 ---")
    assert "[Session 1, 12:08pm] Josh: hello" in prompt
    assert "[Session 2, 9:05am] Josh: again" in prompt
    assert prompt.endswith("Q=" + rec["question"])
    assert "MEM<<" not in prompt
    assert prompt == proto.official_answer_prompt(
        PROMPTS, rec, [proto.official_full_context(rec["history"])], full_context=True)


def test_prompt_gate_needs_every_question_built_and_the_registered_total():
    mod = _load()
    recs = [_rec("a", "Q1", "n1"), _rec("b", "Q8", "n2")]
    sizes = [len(mod.build_prompt(PROMPTS, r).encode("utf-8")) for r in recs]
    gate = mod.prompt_gate(recs, PROMPTS, expected_questions=2, expected_total_bytes=sum(sizes))
    assert gate["ready"] is True and gate["problems"] == []
    assert gate["questions"] == 2 and gate["total_bytes"] == sum(sizes) and gate["max_bytes"] == max(sizes)

    off = mod.prompt_gate(recs, PROMPTS, expected_questions=2, expected_total_bytes=sum(sizes) + 1)
    assert off["ready"] is False and any("total_bytes" in p for p in off["problems"])
    short = mod.prompt_gate(recs[:1], PROMPTS, expected_questions=2, expected_total_bytes=sum(sizes))
    assert short["ready"] is False and any("questions" in p for p in short["problems"])
    empty = mod.prompt_gate([dict(recs[0], history=[]), recs[1]], PROMPTS,
                            expected_questions=2, expected_total_bytes=sum(sizes))
    assert empty["ready"] is False and any("empty_history" in p for p in empty["problems"])


def test_answer_row_carries_prompt_response_and_official_judge_fields():
    mod = _load()
    import eval_official_protocol as proto

    seen = {}

    def answerer(prompt, backbone):
        seen["call"] = (prompt, backbone)
        return "the answer"

    def judge(question, reference, response, model):
        seen["judge"] = (question, reference, response, model)
        return {"score": 0.8, "raw": "{}", "status": "ok", "rationale": "r"}

    rec = _rec("a", "Q1", "n1")
    row = mod.answer_row(rec, prompts=PROMPTS, answerer=answerer, judge=judge, backbone="bb", judge_model="jj")
    assert row["item_id"] == "a" and row["query_type"] == "Q1" and row["ok"] is True and row["score"] == 0.8
    assert row["judge_status"] == "ok" and row["response"] == "the answer"
    assert row["prompt"] == mod.build_prompt(PROMPTS, rec)
    assert row["context_bytes"] == len(proto.official_full_context(rec["history"]).encode("utf-8"))
    assert seen["call"] == (row["prompt"], "bb") and seen["judge"] == (rec["question"], "gold", "the answer", "jj")

    low = mod.answer_row(rec, prompts=PROMPTS, answerer=answerer, judge=lambda *a: {
        "score": 0.69, "raw": "{}", "status": "ok", "rationale": "r"}, backbone="bb", judge_model="jj")
    assert low["ok"] is False
    with pytest.raises(ValueError):
        mod.answer_row(dict(rec, answer_format="multiple_choice"), prompts=PROMPTS, answerer=answerer,
                       judge=judge, backbone="bb", judge_model="jj")


def test_report_is_the_per_type_report_labelled_with_this_arm():
    mod = _load()
    recs = [_rec("a", "Q1", "n1"), _rec("b", "Q7", "n1", "short_answer")]
    rep = mod.build_report(recs, {"a": _row(1.0), "b": _row(0.5)}, seed=1, draws=100)
    assert rep["arm"] == "wp3_full_ctx" and rep["complete"] is True
    assert rep["by_type"]["Q1"]["mean_score"] == pytest.approx(1.0)
    assert rep["by_type"]["Q7"]["n"] == 1 and rep["overall"]["n"] == 2


def test_paired_report_pairs_only_items_usable_in_both_arms_and_reads_source_minus_full():
    mod = _load()
    recs = [_rec("a", "Q1", "n1"), _rec("b", "Q1", "n2"), _rec("c", "Q7", "n1", "short_answer"),
            _rec("d", "Q8", "n3"), _rec("e", "Q3", "n2")]
    src = {"a": _row(0.9), "b": _row(0.5), "c": _row(0.8), "d": _row(0.7, "regex_fallback"), "e": _row(0.4)}
    full = {"a": _row(1.0), "b": _row(0.9), "c": _row(0.8), "d": _row(0.6)}
    rep = mod.paired_report(recs, src, full, seed=1, draws=200)
    assert rep["unpaired"] == ["d", "e"] and rep["complete"] is False
    assert rep["bootstrap"] == {"seed": 1, "draws": 200}
    q1 = rep["by_type"]["Q1"]
    assert q1["n"] == 2 and q1["networks"] == 2
    assert q1["mean_src"] == pytest.approx(0.7) and q1["mean_full"] == pytest.approx(0.95)
    assert q1["delta"] == pytest.approx(-0.25) and q1["lo"] <= q1["delta"] <= q1["hi"]
    assert q1["reading"] == "来源路径落后全历史"
    q7 = rep["by_type"]["Q7"]
    assert q7["n"] == 1 and q7["delta"] == pytest.approx(0.0) and q7["reading"] == "来源路径已接近全历史"
    for empty in ("Q3", "Q8"):
        assert rep["by_type"][empty]["n"] == 0 and rep["by_type"][empty]["delta"] is None
        assert rep["by_type"][empty]["reading"] is None
    overall = rep["overall"]
    assert overall["n"] == 3 and overall["networks"] == 2
    assert overall["delta"] == pytest.approx(-0.5 / 3) and overall["reading"] == "来源路径落后全历史"


def test_answer_refuses_without_real_run_and_without_a_passing_precheck(tmp_path, capsys):
    mod = _load()
    corpus = tmp_path / "c.jsonl"
    corpus.write_text(json.dumps(_rec("a", "Q1", "n1")) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    base = ["answer", "--corpus", str(corpus), "--prompts", str(tmp_path / "p.yaml"),
            "--prompts-sha256", "0" * 64, "--out", str(out)]
    assert mod.main(base) == 1
    assert "--real-run" in capsys.readouterr().err
    assert mod.main(base + ["--real-run"]) == 1
    assert "precheck" in capsys.readouterr().err
    out.mkdir()
    (out / "precheck.json").write_text(json.dumps({"ready": False}), encoding="utf-8")
    assert mod.main(base + ["--real-run"]) == 1
    assert "ready" in capsys.readouterr().err


def test_driver_source_names_no_model():
    path = _SCRIPTS / "eval_socialmem_wp3_fullctx.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_wp3_fullctx.py 尚不存在(功能缺失)")
    text = path.read_text(encoding="utf-8").lower()
    for name in ("qwen", "deepseek", "gpt", "claude", "doubao"):
        assert name not in text


def test_offline_end_to_end_precheck_answer_resume_report(tmp_path, monkeypatch, capsys):
    """端到端离线冒烟(无网络):precheck、answer(假作答与假裁判)、单题失败后续跑、report。需要原生核心。
    本测试写在驱动之后,用于在真跑前验证整条命令链,不是先红后绿的单元测试。"""
    pytest.importorskip("starling._core")
    mod = _load()
    import eval_ladder

    corpus = tmp_path / "c.jsonl"
    recs = [_rec("a", "Q1", "n1"), _rec("b", "Q7", "n1", "short_answer"), _rec("c", "Q8", "n2")]
    corpus.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    out = tmp_path / "out"
    sha = "a" * 64
    monkeypatch.setattr(mod.proto, "load_official_prompts", lambda path, expected=None: PROMPTS)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "offline-placeholder")
    calls: list[str] = []
    monkeypatch.setattr(eval_ladder, "make_real_answerer_fn",
                        lambda **kw: (lambda prompt, backbone: calls.append(prompt) or "resp"))
    state = {"fail_c": True}

    def judge_factory(chat, prompts, **kw):
        def judge(question, reference, response, model):
            if state["fail_c"] and question == "Q c?":
                raise RuntimeError("boom")
            return {"score": 0.9, "raw": "{}", "status": "ok", "rationale": "r"}
        return judge

    monkeypatch.setattr(mod.proto, "make_official_judge_fn", judge_factory)
    total = sum(len(mod.build_prompt(PROMPTS, r).encode("utf-8")) for r in recs)
    common = ["--corpus", str(corpus), "--out", str(out)]
    pro = ["--prompts", str(tmp_path / "p.yaml"), "--prompts-sha256", sha]

    assert mod.main(["precheck", *common, *pro, "--expected-questions", "3",
                     "--expected-total-bytes", str(total)]) == 0
    assert json.loads((out / "precheck.json").read_text(encoding="utf-8"))["ready"] is True
    # 登记的总字节不符时 precheck 拒绝,且写出 ready=false
    assert mod.main(["precheck", *common, *pro, "--expected-questions", "3",
                     "--expected-total-bytes", str(total + 1)]) == 2
    assert json.loads((out / "precheck.json").read_text(encoding="utf-8"))["ready"] is False
    assert mod.main(["answer", *common, *pro, "--real-run"]) == 1          # 放行门没过
    assert mod.main(["precheck", *common, *pro, "--expected-questions", "3",
                     "--expected-total-bytes", str(total)]) == 0

    capsys.readouterr()
    assert mod.main(["answer", *common, *pro, "--real-run"]) == 0
    first = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert first == {"arm": "wp3_full_ctx", "answered": 2, "questions": 3, "errors": 1}
    assert len(calls) == 3
    journal = out / "wp3_full_ctx_journal.jsonl"
    lines = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert sum(1 for r in lines if "error" in r) == 1 and sum(1 for r in lines if r.get("ok") is True) == 2

    state["fail_c"] = False                                                 # 续跑只重答失败的那一题
    assert mod.main(["answer", *common, *pro, "--real-run"]) == 0
    second = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert second == {"arm": "wp3_full_ctx", "answered": 3, "questions": 3, "errors": 0}
    assert len(calls) == 4
    # 换了官方提示哈希,放行门文件对不上,拒绝
    assert mod.main(["answer", *common, "--prompts", str(tmp_path / "p.yaml"),
                     "--prompts-sha256", "b" * 64, "--real-run"]) == 1

    src = tmp_path / "src_journal.jsonl"
    src.write_text("".join(json.dumps({"key": f"wp3_src_v9|{i}", "arm": "wp3_src_v9", "item_id": i, "ok": s >= 0.7,
                                       "score": s, "judge_status": "ok"}) + "\n"
                           for i, s in (("a", 0.5), ("b", 0.9), ("c", 0.4))), encoding="utf-8")
    result = tmp_path / "result.json"
    assert mod.main(["report", *common, "--src-journal", str(src), "--result", str(result)]) == 0
    rep = json.loads(result.read_text(encoding="utf-8"))
    assert rep["full_ctx"]["arm"] == "wp3_full_ctx" and rep["full_ctx"]["complete"] is True
    assert rep["paired"]["complete"] is True and rep["paired"]["overall"]["n"] == 3
    assert rep["paired"]["overall"]["delta"] == pytest.approx(0.6 - 0.9)
    assert rep["paired"]["overall"]["reading"] == "来源路径落后全历史"
