"""评测配对分析的独立人工小样本。"""
from pathlib import Path
import importlib.util
import pytest

path = Path(__file__).resolve().parents[2] / "scripts/analyze_socialmem_baseline.py"
spec = importlib.util.spec_from_file_location("analyze_socialmem_baseline", path)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def records():
    return [{"item_id": i, "source": {"network_id": n}}
            for i, n in [("a", "one"), ("b", "one"), ("c", "two")]]


def result(i, correct, status="ok"):
    return {"item_id": i, "correct": correct, "status": status, "terminal": True}


def test_paired_changes_include_failures_in_original_denominator():
    base = [result("a", False, "ingestion_failure"), result("b", False), result("c", True)]
    new = [result("a", True), result("b", True), result("c", False)]
    report = analysis.paired(records(), base, new, samples=1000)
    assert report["newly_correct"] == 2
    assert report["newly_incorrect"] == 1
    assert report["delta"] == pytest.approx(1 / 3)
    assert report["network_bootstrap_95ci"] == [-1, 1]


def test_incomplete_run_has_no_final_paired_score():
    with pytest.raises(ValueError, match="incomplete"):
        analysis.paired(records(), [result("a", True)], [result("a", False)])


def test_duplicate_archived_result_is_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        analysis.index_results([result("a", True), result("a", False)])


def test_protocol_changes_are_reported_not_attributed_to_core():
    base = {"answer_model": "model-a", "k": 10}
    new = {"answer_model": "model-b", "k": 10}
    with pytest.raises(ValueError, match="answer_model"):
        analysis.check_common_config(base, new)


def test_reserved_networks_can_be_excluded_from_pair_analysis():
    base = [result("a", False), result("b", False)]
    new = [result("a", True), result("b", True)]
    report = analysis.paired(records()[:2], base, new, samples=100)
    assert report["total"] == 2
    assert report["delta"] == 1
    assert report["network_bootstrap_95ci"] == [1, 1]
