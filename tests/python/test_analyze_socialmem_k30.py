"""配对结果必须保留技术失败分母，拒绝缺失/重复及范围混入。"""
import importlib.util
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / "scripts/analyze_socialmem_k30.py"
    assert path.is_file(), "paired analysis missing"
    spec = importlib.util.spec_from_file_location("analyze_k30", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rows():
    records = [{"item_id": "a", "source": {"network_id": "n1"}},
               {"item_id": "b", "source": {"network_id": "n1"}},
               {"item_id": "c", "source": {"network_id": "n2"}}]
    parent = [{"item_id": "a", "correct": True, "status": "ok"},
              {"item_id": "b", "correct": False, "status": "ok"},
              {"item_id": "c", "correct": False, "status": "judge_failure"}]
    candidate = [{"item_id": "a", "correct": False, "status": "judge_failure"},
                 {"item_id": "b", "correct": True, "status": "ok"},
                 {"item_id": "c", "correct": True, "status": "ok"}]
    return records, parent, candidate


def test_technical_failure_stays_in_denominator_and_paired_regression():
    result = module().paired_outcomes(*rows())
    assert result["n"] == 3
    assert result["parent_correct"] == 1
    assert result["candidate_correct"] == 2
    assert result["new_correct"] == 2
    assert result["regressed"] == 1
    assert result["delta"] == pytest.approx(1 / 3)


def test_row_order_does_not_change_pairing():
    records, parent, candidate = rows()
    assert module().paired_outcomes(records, parent, candidate) == module().paired_outcomes(records, parent[::-1], candidate[::-1])


def test_incomplete_candidate_is_not_silently_ignored():
    records, parent, candidate = rows()
    with pytest.raises(ValueError):
        module().paired_outcomes(records, parent, candidate[:-1])


def test_duplicate_receipt_is_not_silently_overwritten():
    records, parent, candidate = rows()
    with pytest.raises(ValueError):
        module().paired_outcomes(records, parent, candidate + [candidate[0]])


def test_out_of_scope_receipt_is_rejected():
    records, parent, candidate = rows()
    candidate.append({"item_id": "reserved", "correct": True, "status": "ok"})
    with pytest.raises(ValueError):
        module().paired_outcomes(records, parent, candidate)


def test_identical_outcomes_have_zero_cluster_interval():
    records, parent, _ = rows()
    assert module().paired_outcomes(records, parent, parent)["network_bootstrap_delta_95ci"] == [0.0, 0.0]


def test_truncated_response_usage_is_counted_even_when_not_scored():
    rows = []
    for ok, tokens, finish in [(True, 20, "stop"), (False, 512, "length")]:
        rows.append({"native_attempt_count": 1, "embedding_request_delta": 0,
                     "recall": {"context_bytes": 100, "source_count": 1},
                     "stages": {"answer": {"seconds": 2}},
                     "answer": {"raw_xml": "", "response": {"ok": ok,
                         "prompt_tokens": 100, "completion_tokens": tokens,
                         "total_tokens": 100 + tokens, "finish_reason": finish}}})
    result = module().resources(rows)
    assert result["answer"]["success"] == 1
    assert result["answer"]["total_tokens"] == 732
    assert result["answer"]["completion_tokens"] == 532
