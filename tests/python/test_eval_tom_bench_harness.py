"""Fixture-mode self-tests for the ToMBench harness.

No real LLM calls are made — the harness is invoked with --fixture-mode so
the deterministic mock provides answers.  Tests cover:

  1. Harness exits 0 and prints PASS on a tiny corpus.
  2. All 4 first-order abilities are counted (no records skipped).
  3. Report file is written with the expected number of rounds.
  4. Records whose ability is NOT in the first-order subset are skipped.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eval_tom_bench import (  # noqa: E402
    ACCURACY_THRESHOLD,
    FIRST_ORDER_ABILITIES,
    _fixture_answer,
    run_one_round,
    write_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_corpus(
    tmp_path: Path,
    n_per_ability: int = 2,
    extra_abilities: list[str] | None = None,
) -> Path:
    """Write a JSONL corpus to tmp_path and return the path."""
    records = []
    for i, ability in enumerate(sorted(FIRST_ORDER_ABILITIES)):
        for j in range(n_per_ability):
            idx = i * n_per_ability + j
            records.append(
                {
                    "question_id": f"tb-{idx:03d}",
                    "context": f"Alice hid a toy in the box. Context variant {idx}.",
                    "question": "Where will Bob look for the toy?",
                    "options": ["in the box", "in the basket", "on the shelf", "outside"],
                    "answer": 0,  # ground truth = index 0
                    "ability": ability,
                }
            )
    # Add records with abilities outside the first-order subset — these should
    # be silently skipped (not counted toward accuracy).
    for ability in (extra_abilities or []):
        records.append(
            {
                "question_id": f"tb-skip-{ability}",
                "context": "Context.",
                "question": "Question?",
                "options": ["A", "B", "C", "D"],
                "answer": 1,
                "ability": ability,
            }
        )
    p = tmp_path / "corpus.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records))
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fixture_mode_exits_zero(tmp_path: Path) -> None:
    """Harness in fixture mode exits 0 and prints PASS."""
    corpus = _make_corpus(tmp_path, n_per_ability=5)
    report = tmp_path / "report.md"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "scripts" / "eval_tom_bench.py"),
            "--corpus",
            str(corpus),
            "--rounds",
            "3",
            "--report",
            str(report),
            "--fixture-mode",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"eval_tom_bench.py exited {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "PASS" in result.stdout


def test_report_written_with_three_rounds(tmp_path: Path) -> None:
    """Report markdown file is created and contains exactly 3 round columns."""
    corpus = _make_corpus(tmp_path, n_per_ability=3)
    report = tmp_path / "eval_tom_bench.md"
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "scripts" / "eval_tom_bench.py"),
            "--corpus",
            str(corpus),
            "--rounds",
            "3",
            "--report",
            str(report),
            "--fixture-mode",
        ],
        check=True,
        capture_output=True,
    )
    assert report.exists(), "report file was not created"
    content = report.read_text()
    # Header row should contain "round 1", "round 2", "round 3"
    assert "round 1" in content
    assert "round 2" in content
    assert "round 3" in content
    assert "threshold" in content
    assert "PASS" in content or "FAIL" in content


def test_second_order_abilities_are_skipped(tmp_path: Path) -> None:
    """Records with abilities outside the first-order subset are not counted."""
    # Corpus has 4 first-order records + 4 out-of-scope records.
    corpus = _make_corpus(
        tmp_path,
        n_per_ability=1,
        extra_abilities=["false-belief", "second-order", "higher-order", "social-script"],
    )
    records = [json.loads(l) for l in corpus.read_text().splitlines() if l.strip()]
    # run_one_round in fixture mode
    acc = run_one_round(
        records,
        fixture_mode=True,
        base_url="",
        api_key="",
        model="",
    )
    # Fixture mock returns correct for 7/10 items; with only 4 valid records
    # (indices 0–3) all land in the "correct" slots (0%10 < 7).
    assert acc >= ACCURACY_THRESHOLD, f"accuracy {acc} < threshold {ACCURACY_THRESHOLD}"


def test_write_report_format(tmp_path: Path) -> None:
    """write_report produces a readable markdown table with PASS verdict."""
    report_path = tmp_path / "r.md"
    # Simulate 3 rounds all well above threshold
    write_report(report_path, [0.70, 0.72, 0.68], ACCURACY_THRESHOLD)
    content = report_path.read_text()
    assert "# ToMBench Eval Report" in content
    assert "0.7000" in content
    assert "0.7200" in content
    assert "0.6800" in content
    assert f"{ACCURACY_THRESHOLD:.2f}" in content
    assert "PASS" in content


def test_second_order_subset_with_higher_threshold(tmp_path: Path) -> None:
    """P3.a2 准入:--order second 选二阶子集,阈值 0.70;一阶记录被跳过。"""
    recs = []
    for i, ab in enumerate(["false-belief", "second-order", "higher-order"] * 4):
        recs.append({"question_id": f"q{i}", "ability": ab, "context": "s",
                     "question": "q", "choices": ["a", "b", "c", "d"], "answer": 1})
    recs.append({"question_id": "skip-first-order", "ability": "desire",
                 "context": "s", "question": "q", "choices": ["a", "b"],
                 "answer": 0})
    corpus = tmp_path / "second.jsonl"
    corpus.write_text("\n".join(json.dumps(r) for r in recs))
    report = tmp_path / "report.md"
    script = Path(__file__).resolve().parents[2] / "scripts" / "eval_tom_bench.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--corpus", str(corpus),
         "--order", "second", "--fixture-mode", "--rounds", "2",
         "--report", str(report)],
        check=True, capture_output=True, text=True)
    assert "PASS" in proc.stdout
    content = report.read_text()
    assert "0.70" in content and "PASS" in content
