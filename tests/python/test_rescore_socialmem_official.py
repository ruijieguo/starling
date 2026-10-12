"""WP0.2:九月已存回答按官方口径重判(scripts/rescore_socialmem_official.py)的纯逻辑测试。

用合成的逐题文件与假裁判,离线验证:回答正文从嵌套回执里的取法、按题号续跑、汇总口径。
不读真语料、不发网络。九月选择题的回答是 0 起的下标整数,官方字母口径不适用,所以只重判开放题。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    path = _SCRIPTS / f"{name}.py"
    if not path.exists():
        pytest.fail(f"scripts/{name}.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CORPUS = {
    "Q5_a": {"item_id": "Q5_a", "query_type": "Q5", "answer_format": "long_form",
             "question": "What did Femi know?", "answer": "Femi knew Claudette's preference."},
    "Q2_b": {"item_id": "Q2_b", "query_type": "Q2", "answer_format": "multiple_choice",
             "question": "Who dissented?", "options": ["x", "y"], "answer": 0},
    "Q5_c": {"item_id": "Q5_c", "query_type": "Q5", "answer_format": "long_form",
             "question": "What changed?", "answer": "The venue changed."},
}


def _question_file(root: Path, item_id: str, *, correct: bool, raw: str | None, verdict: str = "NO",
                   envelope_only: bool = False, status: str = "ok") -> Path:
    p = root / "runs" / "net1" / "questions" / f"{item_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    resp = {"ok": True, "finish_reason": "stop"}
    if envelope_only:
        resp["http_attempts"] = [{"attempt": 1, "http_status": 200,
                                  "response_body": json.dumps({"choices": [{"message": {"content": raw}}]})}]
        answer = {"response": resp}
    else:
        resp["raw_completion"] = raw
        answer = {"raw_completion": raw, "response": resp}
    p.write_text(json.dumps({
        "item_id": item_id, "status": status, "correct": correct, "answer": answer,
        "judge": {"response": {"raw_completion": verdict}},
        "judge_prompt": "strict grader prompt",
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def _stub_judge(table):
    def judge(question, reference, candidate, backbone):
        return {"score": table[candidate], "rationale": "r", "raw": "{}", "status": "ok"}

    return judge


def _rows(path):
    return {r["item_id"]: r for r in (json.loads(line) for line in Path(path).read_text().splitlines() if line.strip())}


# ---------------------------- 回答正文的取法 ----------------------------

def test_answer_text_prefers_the_top_level_raw_completion(tmp_path):
    mod = _load("rescore_socialmem_official")
    p = _question_file(tmp_path, "Q5_a", correct=False, raw="candidate text")
    assert mod.answer_text(json.loads(p.read_text())) == "candidate text"


def test_answer_text_falls_back_to_the_http_envelope(tmp_path):
    mod = _load("rescore_socialmem_official")
    p = _question_file(tmp_path, "Q5_a", correct=False, raw="from envelope", envelope_only=True)
    assert mod.answer_text(json.loads(p.read_text())) == "from envelope"


def test_answer_text_returns_empty_when_no_text_exists(tmp_path):
    mod = _load("rescore_socialmem_official")
    p = _question_file(tmp_path, "Q5_a", correct=False, raw=None)
    j = json.loads(p.read_text())
    j["answer"] = {"response": {"ok": False, "error": "transport"}}
    assert mod.answer_text(j) == ""


# ---------------------------- 逐题文件枚举与语料 ----------------------------

def test_iter_question_files_finds_every_question(tmp_path):
    mod = _load("rescore_socialmem_official")
    _question_file(tmp_path, "Q5_a", correct=False, raw="a")
    _question_file(tmp_path, "Q5_c", correct=True, raw="c")
    assert [p.name for p in mod.iter_question_files(tmp_path)] == ["Q5_a.json", "Q5_c.json"]


def test_load_corpus_indexes_records_by_item_id(tmp_path):
    mod = _load("rescore_socialmem_official")
    p = tmp_path / "corpus.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in CORPUS.values()) + "\n", encoding="utf-8")
    got = mod.load_corpus(p)
    assert set(got) == {"Q5_a", "Q2_b", "Q5_c"}
    assert got["Q5_a"]["question"] == "What did Femi know?"


# ---------------------------- 重判与汇总 ----------------------------

def test_rescore_records_strict_and_official_side_by_side(tmp_path):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    _question_file(root, "Q5_a", correct=False, raw="Femi knew it", verdict="NO")
    _question_file(root, "Q5_c", correct=True, raw="The venue changed", verdict="YES")
    _question_file(root, "Q2_b", correct=True, raw="0", verdict="")      # 九月选择题:0 起下标
    out = tmp_path / "rows.jsonl"
    summary = mod.rescore(root, CORPUS, out, _stub_judge({"Femi knew it": 0.9, "The venue changed": 0.4}))
    rows = _rows(out)
    assert set(rows) == {"Q5_a", "Q5_c"}                                  # 选择题不重判
    assert rows["Q5_a"]["strict_correct"] is False and rows["Q5_a"]["official_score"] == 0.9
    assert rows["Q5_a"]["official_correct"] is True
    assert rows["Q5_c"]["strict_correct"] is True and rows["Q5_c"]["official_correct"] is False
    assert rows["Q5_a"]["query_type"] == "Q5" and rows["Q5_a"]["judge_status"] == "ok"
    assert summary["n"] == 2 and summary["strict_correct"] == 1 and summary["official_correct"] == 1
    assert summary["skipped_multiple_choice"] == 1


def test_rescore_is_resumable_by_item_id(tmp_path):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    _question_file(root, "Q5_a", correct=False, raw="Femi knew it")
    _question_file(root, "Q5_c", correct=True, raw="The venue changed")
    out = tmp_path / "rows.jsonl"
    mod.rescore(root, CORPUS, out, _stub_judge({"Femi knew it": 0.9, "The venue changed": 0.4}))
    before = out.read_text()
    calls = []

    def counting(*args):
        calls.append(args)
        return {"score": 0.0, "rationale": "r", "raw": "{}", "status": "ok"}

    summary = mod.rescore(root, CORPUS, out, counting)
    assert out.read_text() == before          # 已判题不重复写、不重复判
    assert calls == []
    assert summary["n"] == 2                  # 汇总仍覆盖续跑前已写入的行


def test_rescore_skips_items_missing_from_the_corpus(tmp_path):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    _question_file(root, "Q5_unknown", correct=False, raw="x")
    out = tmp_path / "rows.jsonl"
    summary = mod.rescore(root, CORPUS, out, _stub_judge({"x": 1.0}))
    assert summary["n"] == 0 and summary["skipped_missing_record"] == 1
    assert out.read_text() == ""


def test_rescore_skips_items_without_a_usable_answer(tmp_path):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    _question_file(root, "Q5_a", correct=False, raw="", status="answer_failure")
    _question_file(root, "Q5_c", correct=False, raw="", status="ok")
    out = tmp_path / "rows.jsonl"
    summary = mod.rescore(root, CORPUS, out, _stub_judge({}))
    assert summary["n"] == 0 and summary["skipped_not_ok"] == 2


def test_summary_reports_per_query_type(tmp_path):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    _question_file(root, "Q5_a", correct=False, raw="Femi knew it")
    _question_file(root, "Q5_c", correct=True, raw="The venue changed")
    out = tmp_path / "rows.jsonl"
    summary = mod.rescore(root, CORPUS, out, _stub_judge({"Femi knew it": 0.9, "The venue changed": 0.4}))
    assert summary["by_query_type"]["Q5"] == {"n": 2, "strict_correct": 1, "official_correct": 1,
                                              "mean_score": pytest.approx(0.65)}
    assert summary["mean_score"] == pytest.approx(0.65)


def test_rescore_does_not_touch_other_paths(tmp_path):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    _question_file(root, "Q5_a", correct=False, raw="Femi knew it")
    out = tmp_path / "out" / "rows.jsonl"
    mod.rescore(root, CORPUS, out, _stub_judge({"Femi knew it": 0.5}))
    assert out.exists() and out.parent.name == "out"
    assert sorted(p.name for p in root.rglob("*") if p.is_file()) == ["Q5_a.json"]


# ---------------------------- 命令行防线 ----------------------------

def _cli_args(tmp_path, out, *extra):
    return ["--root", str(tmp_path / "dev"), "--corpus", str(tmp_path / "c.jsonl"), "--out", str(out),
            "--prompts", str(tmp_path / "p.yaml"), "--prompts-sha256", "0" * 64,
            "--judge-model", "m", *extra]


def test_main_refuses_to_run_without_real_run(tmp_path, capsys):
    mod = _load("rescore_socialmem_official")
    (tmp_path / "dev").mkdir()
    out = tmp_path / "out" / "rows.jsonl"
    assert mod.main(_cli_args(tmp_path, out)) == 1
    assert "--real-run" in capsys.readouterr().err
    assert not out.exists()


def test_main_refuses_an_output_inside_the_question_directory(tmp_path, capsys):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    root.mkdir()
    for out in (root / "rows.jsonl", root / "nested" / "rows.jsonl"):
        assert mod.main(_cli_args(tmp_path, out, "--real-run")) == 1
        assert "--root" in capsys.readouterr().err
        assert not out.exists()
    assert list(root.rglob("*")) == []


def test_main_refuses_a_summary_inside_the_question_directory(tmp_path, capsys):
    mod = _load("rescore_socialmem_official")
    root = tmp_path / "dev"
    root.mkdir()
    out = tmp_path / "out" / "rows.jsonl"
    for summary in (root / "summary.json", root / "nested" / "summary.json"):
        assert mod.main(_cli_args(tmp_path, out, "--real-run", "--summary", str(summary))) == 1
        assert "--summary" in capsys.readouterr().err
        assert not summary.exists()
    assert list(root.rglob("*")) == []
