"""Offline self-tests for the commitment eval harness."""
import json, subprocess, sys
from pathlib import Path
import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_commitment import run_scenario, _median  # noqa: E402


def _scn(stmt_id, final_state, actions, detect_by=1):
    return {"scenario_id": stmt_id, "category": "fulfill",
            "commit": {"stmt_id": f"{stmt_id}-c", "holder": "alice", "subject": "bob",
                       "object": "x", "deadline": "2026-06-10T12:00:00Z",
                       "observed_at": "2026-06-10T08:00:00Z"},
            "actions": actions, "expected": {"final_state": final_state, "detect_by_turn": detect_by}}


def test_fulfill_scenario_detected():
    ok, turn = run_scenario(_scn("t1", "FULFILLED",
        [{"turn": 0, "op": "tick", "now": "2026-06-10T09:00:00Z"},
         {"turn": 1, "op": "fulfill", "now": "2026-06-10T10:00:00Z"}]))
    assert ok and turn == 1


def test_negative_mismatch_not_detected():
    # expect FULFILLED but we never fulfill → observed stays ACTIVE → ok=False
    ok, _ = run_scenario(_scn("t2", "FULFILLED",
        [{"turn": 0, "op": "tick", "now": "2026-06-10T09:00:00Z"}]))
    assert ok is False


def test_full_harness_exits_zero(tmp_path):
    corpus = tmp_path / "c.jsonl"
    scns = [_scn(f"t{i}", "FULFILLED",
                 [{"turn": 0, "op": "tick", "now": "2026-06-10T09:00:00Z"},
                  {"turn": 1, "op": "fulfill", "now": "2026-06-10T10:00:00Z"}]) for i in range(3)]
    corpus.write_text("\n".join(json.dumps(s) for s in scns))
    report = tmp_path / "r.md"
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "eval_commitment.py"),
         "--corpus", str(corpus), "--report", str(report)],
        capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "PASS" in res.stdout
    assert report.exists()


def test_median():
    assert _median([1, 1, 2]) == 1.0
    assert _median([]) == 0.0
    assert _median([0, 2]) == 1.0
