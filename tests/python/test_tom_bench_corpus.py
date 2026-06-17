"""Shape-validation test for the hand-authored first-order ToMBench corpus."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "data" / "eval_tom_bench" / "first_order.jsonl"
_ABIL = {"unexpected-outcome", "desire", "persuade", "world-knowledge"}

# Second-order subset (P3.a2 admission, threshold 0.70) — extracted from ToMBench
# via scripts/build_tombench_second_order_corpus.py. eval_tom_bench.py --order
# second filters records on this ability set.
CORPUS2 = ROOT / "tests" / "data" / "eval_tom_bench" / "second_order.jsonl"
_ABIL2 = {"false-belief", "second-order", "higher-order"}


def test_first_order_corpus_shape():
    lines = [l for l in CORPUS.read_text().splitlines() if l.strip()]
    assert len(lines) >= 16
    seen = set()
    for l in lines:
        r = json.loads(l)
        assert r["question_id"] and r["question_id"] not in seen
        seen.add(r["question_id"])
        assert len(r["options"]) == 4
        assert 0 <= int(r["answer"]) <= 3
        assert r["ability"] in _ABIL
        assert r["context"] and r["question"]


def test_second_order_corpus_shape():
    # second_order.jsonl is committed via a .gitignore negation (ToMBench-derived;
    # regenerable via scripts/build_tombench_second_order_corpus.py). The skip
    # guard is defensive — validate the shape whenever the corpus is present.
    if not CORPUS2.exists():
        pytest.skip("second_order.jsonl not present")
    lines = [l for l in CORPUS2.read_text().splitlines() if l.strip()]
    assert len(lines) >= 24
    seen = set()
    for l in lines:
        r = json.loads(l)
        assert r["question_id"] and r["question_id"] not in seen
        seen.add(r["question_id"])
        assert len(r["options"]) == 4
        assert 0 <= int(r["answer"]) <= 3
        # the answer must index a non-empty option
        assert r["options"][int(r["answer"])]
        assert r["ability"] in _ABIL2
        assert r["context"] and r["question"]
