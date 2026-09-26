"""结构化 SocialMemBench 双臂运行器的离线协议门禁。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "run_socialmem_structured_eval_guard",
    ROOT / "scripts/run_socialmem_structured_eval.py",
)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def test_select_scope_is_the_frozen_57_question_set():
    source = ROOT / "build/socialmem_20260917_source_speaker/corpus.jsonl"
    records = [json.loads(line) for line in source.read_text().splitlines() if line]
    selected = runner.select_records(records)
    assert len(selected) == 57
    assert len({row["item_id"] for row in selected}) == 57
    assert len({row["source"]["network_id"] for row in selected}) == 6
    assert sum(1 + int(row["answer_format"] != "multiple_choice") for row in selected) == 101


def test_arm_config_keeps_answer_protocol_identical_and_enables_claims_only_for_statements():
    common = runner.arm_config("sources")
    structured = runner.arm_config("statements")
    fenced = runner.arm_config("statements_fenced")
    hybrid = runner.arm_config("hybrid_fenced")
    dialogue = runner.arm_config("hybrid_dialogue")
    expanded = runner.arm_config("hybrid_dialogue_expanded")
    coverage = runner.arm_config("hybrid_coverage")
    retry = runner.arm_config("hybrid_protocol_retry")
    for key in ("answer_model", "answer_endpoint", "answer_max_tokens", "judge_max_tokens",
                "embedding_model", "embedding_endpoint", "max_retries", "timeout_ms"):
        assert common[key] == structured[key]
    assert common["recall_mode"] == "sources"
    assert common["semantic_claim_contract"] is False
    assert structured["recall_mode"] == "statements"
    assert structured["semantic_claim_contract"] is True
    assert structured["preserve_text_objects"] is True
    assert structured["claim_output_mode"] == "json_object"
    assert fenced["recall_mode"] == "statements"
    assert fenced["semantic_claim_contract"] is True
    assert fenced["preserve_text_objects"] is True
    assert fenced["claim_allow_code_fence"] is True
    assert hybrid["recall_mode"] == "hybrid"
    assert hybrid["semantic_claim_contract"] is True
    assert hybrid["claim_allow_code_fence"] is True
    assert hybrid["claim_output_mode"] == "json_object"
    assert dialogue["recall_mode"] == "hybrid"
    assert dialogue["source_strategy"] == "focused_dialogue"
    assert dialogue["claim_allow_code_fence"] is True
    assert expanded["recall_mode"] == "hybrid"
    assert expanded["source_strategy"] == "focused_dialogue"
    assert expanded["source_seed_k"] == 5
    assert expanded["source_seed_max_context_bytes"] == 4000
    assert expanded["source_dialogue_radius"] == 2
    assert expanded["k"] == dialogue["k"] == 10
    assert expanded["max_context_bytes"] == dialogue["max_context_bytes"] == 8000
    assert coverage["recall_mode"] == "hybrid"
    assert coverage["source_strategy"] == "focused_coverage"
    assert coverage["min_source_items"] == 7
    assert coverage["source_seed_k"] == 5
    assert coverage["source_seed_max_context_bytes"] == 4000
    assert coverage["source_dialogue_radius"] == 1
    assert retry["claim_protocol_retry_budget"] == 1
    assert retry["recall_mode"] == "hybrid"


def test_r31_raises_only_structured_extraction_capacity():
    assert runner.arm_config("sources")["extract_max_tokens"] == 4096
    for arm in ("statements", "statements_fenced", "hybrid_fenced",
                "hybrid_dialogue", "hybrid_dialogue_expanded", "hybrid_coverage"):
        config = runner.arm_config(arm)
        assert config["extract_max_tokens"] == 8192
        assert config["answer_max_tokens"] == 512
        assert config["judge_max_tokens"] == 64
    assert runner.arm_config("hybrid_protocol_retry")["extract_max_tokens"] == 8192


def test_check_rejects_model_or_budget_drift(tmp_path):
    with pytest.raises(ValueError, match="answer_model"):
        runner.validate_arm_config("sources", {**runner.arm_config("sources"),
                                                  "answer_model": "other-model"})
    with pytest.raises(ValueError, match="max_retries"):
        runner.validate_arm_config("statements", {**runner.arm_config("statements"),
                                                    "max_retries": 1})


def test_dynamic_frozen_runner_uses_serial_execution_for_pickle_safety():
    assert runner.EXECUTION_WORKERS == 1


def complete_scope():
    return {"group": "g", "extraction": [
        {"holder": name, "extraction_failed": False, "source_preserved": True,
         "catalog_version": "claim-predicate-v2", "statement_ids": [],
         "structured_claims_persisted": False, "outcome": "accepted"}
        for name in ("Arin", "Vale")]}


def scope_group():
    return {"group_id": "g", "history": [{"speaker": "Arin"}, {"speaker": "Vale"}]}


def write_scope(path, metadata):
    path.mkdir(exist_ok=True)
    (path / "scope.json").write_text(json.dumps(metadata))
    (path / "frozen.db").write_bytes(b"fixture identity only; no SQL needed by gate")


def test_structured_gate_accepts_complete_empty_extraction_and_unstarted_scope(tmp_path):
    assert hasattr(runner, "_validate_structured_scope"), "missing structured scope coverage gate"
    runner._validate_structured_scope(tmp_path / "absent", scope_group())


def test_structured_gate_accepts_terminal_scope_failure_as_technical_result(tmp_path):
    scope = tmp_path / "failed"
    scope.mkdir()
    (scope / "scope.failure.json").write_text(json.dumps({"group": "g", "error": "envelope_failure"}))
    runner._validate_structured_scope(scope, scope_group())
    write_scope(tmp_path, complete_scope())
    runner._validate_structured_scope(tmp_path, scope_group())


@pytest.mark.parametrize("fault", ["source_only", "missing_holder", "duplicate_holder",
                                   "failed", "missing_version", "missing_source", "wrong_group"])
def test_structured_gate_rejects_incomplete_or_source_only_snapshot(tmp_path, fault):
    assert hasattr(runner, "_validate_structured_scope"), "missing structured scope coverage gate"
    metadata = complete_scope()
    if fault == "source_only":
        metadata.update(ingestion_mode="source_only", extraction=[])
    elif fault == "missing_holder":
        metadata["extraction"].pop()
    elif fault == "duplicate_holder":
        metadata["extraction"][1] = metadata["extraction"][0]
    elif fault == "failed":
        metadata["extraction"][0]["extraction_failed"] = True
    elif fault == "missing_version":
        metadata["extraction"][0].pop("catalog_version")
    elif fault == "missing_source":
        metadata["extraction"][0]["source_preserved"] = False
    else:
        metadata["group"] = "other"
    write_scope(tmp_path, metadata)
    with pytest.raises(ValueError, match="structured scope"):
        runner._validate_structured_scope(tmp_path, scope_group())


def test_structured_gate_rejects_partly_written_scope(tmp_path):
    assert hasattr(runner, "_validate_structured_scope"), "missing structured scope coverage gate"
    (tmp_path / "network.db").write_bytes(b"partial")
    with pytest.raises(ValueError, match="structured scope"):
        runner._validate_structured_scope(tmp_path, scope_group())
