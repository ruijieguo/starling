"""Fixture-mode self-tests for the FANToM harness.

No real LLM calls are made — the harness is invoked with --fixture-mode so
the deterministic mock provides answers.  Tests cover:

  1. Harness exits 0 and prints PASS on a small corpus (all 3 question types).
  2. Report file is written with correct round columns and verdict.
  3. Per-question-type stddev is 0.0 (fixture is deterministic across rounds).
  4. Conversations where a participant was absent are handled correctly
     (visible_turns filter works).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eval_fantom import (  # noqa: E402
    DEFAULT_SEED,
    STDDEV_THRESHOLD,
    _gold_index,
    _stddev,
    _visible_turns,
    load_corpus,
    run_one_round,
    sample_corpus,
    write_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_corpus(tmp_path: Path, n_conversations: int = 5) -> Path:
    """Write a small in-memory FANToM JSONL corpus covering all 3 question types."""
    records = []
    for i in range(n_conversations):
        participants = ["Alice", "Bob", "Carol"]
        turns = [
            {
                "speaker": "Alice",
                "listener_set": ["Bob", "Carol"],
                "utterance": f"The project deadline is Friday. (conv {i})",
            },
            {
                "speaker": "Bob",
                "listener_set": ["Alice"],
                "utterance": f"I already finished my part. (conv {i})",
            },
            {
                "speaker": "Carol",
                "listener_set": [],  # broadcast — all hear this
                "utterance": f"We need more time. (conv {i})",
            },
        ]
        questions = [
            {
                "question_type": "factual",
                "target_cognizer": "Bob",
                "question_text": "What is the project deadline?",
                "expected_answer": "Friday",
                "options": ["Monday", "Wednesday", "Friday", "Next week"],
            },
            {
                "question_type": "belief",
                "target_cognizer": "Carol",
                "question_text": "What does Carol believe about the deadline?",
                "expected_answer": "Friday",
                "options": ["Unknown", "Wednesday", "Friday", "Monday"],
            },
            {
                "question_type": "answerability",
                "target_cognizer": "Carol",
                "question_text": "Can Carol answer what Bob said privately to Alice?",
                "expected_answer": "no",
                "options": ["yes", "maybe", "no", "depends"],
            },
        ]
        records.append(
            {
                "conversation_id": f"fantom-test-{i:04d}",
                "participants": participants,
                "turns": turns,
                "questions": questions,
            }
        )
    p = tmp_path / "corpus.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records))
    return p


def _run_harness(
    tmp_path: Path,
    corpus_path: Path,
    rounds: int = 3,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke eval_fantom.py as a subprocess in fixture mode."""
    report = tmp_path / "eval_fantom.md"
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parents[2] / "scripts" / "eval_fantom.py"),
        "--corpus", str(corpus_path),
        "--rounds", str(rounds),
        "--sample-size", "1000",
        "--seed", str(DEFAULT_SEED),
        "--report", str(report),
        "--fixture-mode",
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fixture_mode_exits_zero(tmp_path: Path) -> None:
    """Harness in fixture mode exits 0 and prints PASS."""
    corpus = _make_corpus(tmp_path)
    result = _run_harness(tmp_path, corpus)
    assert result.returncode == 0, (
        f"eval_fantom.py exited {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "PASS" in result.stdout


def test_report_written_with_three_rounds(tmp_path: Path) -> None:
    """Report file is written and contains the expected round columns."""
    corpus = _make_corpus(tmp_path, n_conversations=3)
    _run_harness(tmp_path, corpus, rounds=3)
    report = tmp_path / "eval_fantom.md"
    assert report.exists(), "report file was not created"
    content = report.read_text()
    assert "round 1" in content
    assert "round 2" in content
    assert "round 3" in content
    assert "PASS" in content or "FAIL" in content
    # All three question types should appear in the report
    assert "factual" in content
    assert "belief" in content
    assert "answerability" in content


def test_stddev_is_zero_in_fixture_mode(tmp_path: Path) -> None:
    """Fixture mock is deterministic so stddev across 3 rounds is exactly 0.0."""
    corpus_path = _make_corpus(tmp_path, n_conversations=5)
    conversations = load_corpus(corpus_path)
    sample = sample_corpus(conversations, 1000, DEFAULT_SEED)
    question_types = frozenset(["factual", "belief", "answerability"])

    rounds_data = []
    for _ in range(3):
        rd = run_one_round(
            sample,
            question_types,
            fixture_mode=True,
            base_url="",
            api_key="",
            model="",
        )
        rounds_data.append(rd)

    for qt in question_types:
        accs = []
        for rd in rounds_data:
            correct, total = rd.get(qt, (0, 0))
            assert total > 0, f"No questions evaluated for type {qt}"
            accs.append(correct / total)
        sd = _stddev(accs)
        assert sd <= STDDEV_THRESHOLD, (
            f"{qt}: stddev {sd:.4f} > threshold {STDDEV_THRESHOLD}"
        )


def test_all_question_types_evaluated(tmp_path: Path) -> None:
    """All 3 question types run on 100 % of items with non-zero totals."""
    corpus_path = _make_corpus(tmp_path, n_conversations=5)
    conversations = load_corpus(corpus_path)
    sample = sample_corpus(conversations, 1000, DEFAULT_SEED)
    question_types = frozenset(["factual", "belief", "answerability"])

    rd = run_one_round(
        sample,
        question_types,
        fixture_mode=True,
        base_url="",
        api_key="",
        model="",
    )
    for qt in question_types:
        correct, total = rd.get(qt, (0, 0))
        assert total > 0, f"No questions evaluated for type {qt}"
        # 5 conversations × 1 question per type = 5 per type
        assert total == 5, f"{qt}: expected 5 questions, got {total}"


def test_visible_turns_respects_listener_set(tmp_path: Path) -> None:
    """_visible_turns correctly filters turns based on listener_set."""
    turns = [
        {"speaker": "Alice", "listener_set": ["Bob"], "utterance": "private to Bob"},
        {"speaker": "Bob", "listener_set": [], "utterance": "broadcast"},
        {"speaker": "Carol", "listener_set": ["Alice", "Carol"], "utterance": "to Alice+Carol"},
    ]
    # Bob sees: Alice→Bob (direct), Bob→all (broadcast), but NOT Carol→Alice+Carol
    bob_turns = _visible_turns(turns, "Bob")
    assert len(bob_turns) == 2
    assert bob_turns[0]["utterance"] == "private to Bob"
    assert bob_turns[1]["utterance"] == "broadcast"

    # Carol sees: broadcast from Bob, Carol→Alice+Carol (Carol is speaker)
    carol_turns = _visible_turns(turns, "Carol")
    assert len(carol_turns) == 2
    assert carol_turns[0]["utterance"] == "broadcast"
    assert carol_turns[1]["utterance"] == "to Alice+Carol"
