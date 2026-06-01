"""Offline fixture-mode self-tests for the LongMemEval harness."""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_longmemeval import run_one_round, ACCURACY_THRESHOLD, SUBSETS  # noqa: E402

def _make(tmp_path):
    recs = []
    for s in SUBSETS:
        for i in range(4):
            recs.append({"item_id": f"{s}-{i}", "subset": s,
                         "history": [{"speaker": "a", "text": "x", "observed_at": "2026-04-01T10:00:00Z"}],
                         "question": "q?", "options": ["A", "B", "C", "D"], "answer": 0})
    p = tmp_path / "c.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in recs))
    return p

def test_fixture_exits_zero(tmp_path):
    corpus = _make(tmp_path)
    report = tmp_path / "r.md"
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "eval_longmemeval.py"),
         "--corpus", str(corpus), "--rounds", "3", "--report", str(report), "--fixture-mode"],
        capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "PASS" in res.stdout
    assert report.exists()

def test_both_subsets_evaluated(tmp_path):
    corpus = _make(tmp_path)
    recs = [json.loads(l) for l in corpus.read_text().splitlines() if l.strip()]
    res = run_one_round(recs, SUBSETS, fixture_mode=True)
    for s in SUBSETS:
        assert res[s][1] == 4 and res[s][0] >= 1   # 都被评且有正确
