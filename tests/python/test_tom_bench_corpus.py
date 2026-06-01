"""Shape-validation test for the hand-authored first-order ToMBench corpus."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "data" / "eval_tom_bench" / "first_order.jsonl"
_ABIL = {"unexpected-outcome", "desire", "persuade", "world-knowledge"}


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
