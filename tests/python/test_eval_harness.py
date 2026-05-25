"""Self-tests for the EVAL harness. No real LLM calls — uses a fake extractor."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eval_p1_extractor import f1_score, evaluate_record, P1_THRESHOLDS  # noqa: E402


def test_f1_perfect_match():
    assert f1_score(tp=10, fp=0, fn=0) == 1.0


def test_f1_partial():
    # precision=0.5, recall=0.5, f1=0.5
    assert f1_score(tp=1, fp=1, fn=1) == 0.5


def test_f1_zero_when_no_predictions_or_truth():
    assert f1_score(tp=0, fp=0, fn=0) == 0.0


def test_evaluate_record_exact_match():
    record = {
        "id": "eval-001",
        "ground_truth_statements": [
            {"holder": "Alice", "holder_perspective": "FIRST_PERSON",
             "predicate": "knows", "object": "calculus", "nesting_depth": 0},
        ],
    }
    predicted = [
        {"holder": "Alice", "holder_perspective": "FIRST_PERSON",
         "predicate": "knows", "object": "calculus", "nesting_depth": 0},
    ]
    per_field = evaluate_record(record, predicted)
    assert per_field["holder"] == (1, 0, 0)
    assert per_field["holder_perspective"] == (1, 0, 0)
    assert per_field["predicate"] == (1, 0, 0)
    assert per_field["object"] == (1, 0, 0)
    # nesting_depth=0 → does not contribute to nesting bucket
    assert per_field["nesting_depth_1"] == (0, 0, 0)


def test_evaluate_record_misses_holder():
    record = {
        "id": "eval-002",
        "ground_truth_statements": [
            {"holder": "Alice", "holder_perspective": "FIRST_PERSON",
             "predicate": "knows", "object": "calculus", "nesting_depth": 0},
        ],
    }
    predicted = [
        {"holder": "Bob", "holder_perspective": "FIRST_PERSON",
         "predicate": "knows", "object": "calculus", "nesting_depth": 0},
    ]
    per_field = evaluate_record(record, predicted)
    assert per_field["holder"] == (0, 1, 1)  # fp on Bob, fn on Alice


def test_thresholds_match_spec():
    assert P1_THRESHOLDS == {
        "holder": 0.85,
        "holder_perspective": 0.80,
        "predicate": 0.75,
        "object": 0.70,
        "nesting_depth_1": 0.60,
    }
