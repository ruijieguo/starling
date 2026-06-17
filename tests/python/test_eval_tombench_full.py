"""No-network self-tests for the full-ToMBench harness + extractor.

The LLM call path needs real credentials, so these cover the deterministic
pieces: ToMBench-record -> Starling-record transformation (incl. the "A." answer
quirk) and the per-task aggregation / report writer.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from build_tombench_full_corpus import _answer_idx, build  # noqa: E402
from eval_tombench_full import aggregate, write_report  # noqa: E402


def _write_tombench_file(tmp_path: Path) -> Path:
    import json
    d = tmp_path / "data"
    d.mkdir()
    rec = {
        "能力\nABILITY": "Belief: Location false beliefs",
        "STORY": "S", "QUESTION": "Q",
        "OPTION-A": "a", "OPTION-B": "b", "OPTION-C": "c", "OPTION-D": "d",
        "答案\nANSWER": "C",
    }
    rec2 = {**rec, "答案\nANSWER": "A.", "STORY": "S2"}  # the "A." quirk
    (d / "False Belief Task.jsonl").write_text(
        json.dumps(rec, ensure_ascii=False) + "\n"
        + json.dumps(rec2, ensure_ascii=False) + "\n")
    return d


def test_answer_idx_tolerates_punctuation():
    assert _answer_idx("A") == 0
    assert _answer_idx("A.") == 0
    assert _answer_idx(" d ") == 3


def test_build_transforms_and_labels(tmp_path):
    rows = build(_write_tombench_file(tmp_path))
    assert len(rows) == 2
    r = rows[0]
    assert r["task"] == "False Belief Task"
    assert r["question_id"].startswith("tb-false-belief-task-")
    assert r["options"] == ["a", "b", "c", "d"]
    assert r["answer"] == 2  # "C"
    assert r["ability"] == "Belief: Location false beliefs"
    assert rows[1]["answer"] == 0  # "A." -> 0


def test_aggregate_overall_and_per_task():
    records = [
        {"task": "T1", "answer": 0},
        {"task": "T1", "answer": 1},
        {"task": "T2", "answer": 2},
    ]
    preds = [0, 0, 2]  # T1: 1/2, T2: 1/1
    agg = aggregate(records, preds)
    assert agg["overall"] == (2, 3)
    assert agg["per_task"]["T1"] == [1, 2]
    assert agg["per_task"]["T2"] == [1, 1]


def test_write_report_has_per_task_and_overall(tmp_path):
    agg = {"overall": (2, 3), "per_task": {"T1": [1, 2], "T2": [1, 1]}}
    out = tmp_path / "r.md"
    write_report(out, agg, "deepseek-v4-pro", threshold=0.5)
    text = out.read_text()
    assert "T1" in text and "T2" in text
    assert "OVERALL" in text
    assert "0.6667" in text  # 2/3
    assert "PASS" in text    # 0.6667 >= 0.5
