"""R5.2 同库 QA 对照的提示、终态和配对统计合同。"""

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_socialmem_r52_v6_v7_qa.py"


def driver():
    spec = importlib.util.spec_from_file_location("socialmem_r52_v6_v7_qa", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(item_id, correct, status="ok", prompt="p"):
    return {"item_id": item_id, "correct": correct, "status": status,
            "terminal": True, "prompt": prompt, "native_attempt_count": 1}


def test_only_frozen_answer_policies_are_allowed():
    d = driver()
    assert d.validate_policy("legacy") == "legacy"
    assert d.validate_policy("grounded_memory_v1") == "grounded_memory_v1"
    with pytest.raises(ValueError, match="policy"):
        d.validate_policy("grounded_memory_v2")


def test_reused_v7_receipt_must_match_item_prompt_and_terminal():
    d = driver()
    good = row("q1", True, prompt="same")
    d.validate_reused_receipt(good, "q1", "same")
    with pytest.raises(ValueError, match="prompt"):
        d.validate_reused_receipt(good, "q1", "changed")
    with pytest.raises(ValueError, match="terminal"):
        d.validate_reused_receipt({**good, "terminal": False}, "q1", "same")


def test_pair_score_is_v7_minus_v6_and_tracks_transitions():
    d = driver()
    v6 = [row("q1", False), row("q2", True), row("q3", False)]
    v7 = [row("q1", True), row("q2", False), row("q3", False)]
    result = d.compare_scores(v6, v7)
    assert result["v6_correct"] == 1
    assert result["v7_correct"] == 1
    assert result["net_v7_minus_v6"] == 0
    assert result["transitions"] == {"improved": 1, "regressed": 1, "unchanged": 1}


def test_pair_score_rejects_duplicate_or_unaligned_items():
    d = driver()
    with pytest.raises(ValueError, match="item"):
        d.compare_scores([row("q1", True), row("q1", False)], [row("q1", True)])
    with pytest.raises(ValueError, match="item"):
        d.compare_scores([row("q1", True)], [row("q2", True)])


def test_fresh_v7_execution_plan_generates_both_arms_without_reusing_answers():
    d = driver()
    plan = d.build_execution_plan(
        Path("/tmp/r51-contexts"),
        Path("/tmp/r50-parent"),
        {"answer_model": "qwen3.8-27b", "answer_max_tokens": 512,
         "judge_max_tokens": 512, "answer_enable_thinking": False},
        fresh_v7=True,
    )
    assert plan["generated_arms"] == ["v6", "v7"]
    assert plan["reused_arm"] is None
    assert plan["fresh_v7"] is True


def test_reuse_execution_plan_keeps_v7_as_archived_arm():
    d = driver()
    plan = d.build_execution_plan(
        Path("/tmp/r51-contexts"),
        Path("/tmp/r50-parent"),
        {"answer_model": "qwen3.8-27b", "answer_max_tokens": 512,
         "judge_max_tokens": 512, "answer_enable_thinking": False},
        fresh_v7=False,
    )
    assert plan["generated_arms"] == ["v6"]
    assert plan["reused_arm"] == "v7"
    assert plan["fresh_v7"] is False
