import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "data" / "eval_commitment" / "scenarios.jsonl"
_VALID_STATES = {"ACTIVE", "FULFILLED", "BROKEN", "WITHDRAWN", "RENEGOTIATED"}

def test_corpus_shape():
    lines = [l for l in CORPUS.read_text().splitlines() if l.strip()]
    assert len(lines) == 100
    for l in lines:
        r = json.loads(l)
        assert r["scenario_id"] and r["category"]
        assert r["commit"]["stmt_id"] and r["commit"]["deadline"]
        assert r["actions"] and all(a["op"] in {"tick", "fulfill", "withdraw", "expire"} for a in r["actions"])
        assert r["expected"]["final_state"] in _VALID_STATES
        assert isinstance(r["expected"]["detect_by_turn"], int)

def test_generator_deterministic(tmp_path):
    out = tmp_path / "regen.jsonl"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_commitment_corpus.py"),
                    "--out", str(out)], check=True, capture_output=True)
    assert out.read_text() == CORPUS.read_text()
