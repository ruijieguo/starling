"""R3.5 holder isolation RED tests: native batch boundary and partial scope gate."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load("r35_runner", "scripts/run_socialmem_structured_eval.py")
ladder = load("r35_ladder", "scripts/eval_ladder.py")


def test_r35_arm_is_explicit_and_keeps_native_retry_boundary():
    config = runner.arm_config("hybrid_holder_isolation")
    assert config["claim_protocol_retry_budget"] == 1
    assert config["holder_isolation"] is True
    assert config["semantic_claim_contract"] is True


def test_r35_factory_exposes_native_holder_batch_switch():
    assert "holder_isolation" in __import__("inspect").signature(
        ladder.make_real_extract_fn).parameters


def test_r35_factory_calls_single_native_batch_boundary(monkeypatch):
    class FakeCore:
        def __init__(self):
            self.calls = []

        def claim_source_turn_payload(self, turns_json, preserve_invalid_time=False):
            return turns_json

        def memory_remember_holders(self, adapter, llm, belief, episodic, general,
                                    holder_inputs, policy=None):
            self.calls.append(holder_inputs)
            return [{"holder_id": item["holder_id"], "outcome": "accepted",
                     "extraction_failed": False, "receipt": json.dumps({
                         "schema_version": 1,
                         "channels": {"belief": {}, "general_fact": {}, "episodic": {}}})}
                    for item in holder_inputs]

    fake = FakeCore()
    monkeypatch.setattr(ladder, "_build_extract_llm", lambda *args, **kwargs: object())
    extract = ladder.make_real_extract_fn(fake, holder_isolation=True)
    result = extract("adapter", {"history": [
        {"speaker": "Bad", "text": "one"}, {"speaker": "Good", "text": "two"}]}, "stub")
    assert len(fake.calls) == 1
    assert [row["holder_id"] for row in fake.calls[0]] == ["Bad", "Good"]
    assert [row["holder"] for row in result] == ["Bad", "Good"]


def test_holder_extraction_reuses_registered_source_engram_identity(monkeypatch):
    class FakeCore:
        def __init__(self):
            self.calls = []

        def claim_source_turn_payload(self, turns_json, preserve_invalid_time=False):
            return turns_json

        def memory_remember_holders(self, adapter, llm, belief, episodic, general,
                                    holder_inputs, policy=None):
            self.calls.append(holder_inputs)
            return [{"holder_id": item["holder_id"], "outcome": "accepted",
                     "extraction_failed": False, "receipt": json.dumps({
                         "schema_version": 1,
                         "channels": {"belief": {}, "general_fact": {}, "episodic": {}}})}
                    for item in holder_inputs]

    fake = FakeCore()
    monkeypatch.setattr(ladder, "_build_extract_llm", lambda *args, **kwargs: object())
    extract = ladder.make_real_extract_fn(fake, holder_isolation=True)
    extract("adapter", {"history": [{"speaker": "Ada", "text": "one"}]}, "stub")
    row = fake.calls[0][0]
    assert row["adapter_name"] == "source_turns"
    assert row["source_prefix"] == "source-Ada-"


def test_partial_scope_gate_requires_complete_holder_results(tmp_path):
    scope = tmp_path / "scope"
    scope.mkdir()
    (scope / "scope.json").write_text(json.dumps({
        "group": "g",
        "scope_state": "partial",
        "holder_complete": ["Good"],
        "holder_failures": [{"holder": "Bad", "failure_category": "schema_failure"}],
        "extraction": [
            {"holder": "Good", "extraction_failed": False,
             "source_preserved": True, "catalog_version": "claim-predicate-v3",
             "outcome": "accepted"},
            {"holder": "Bad", "extraction_failed": True,
             "source_preserved": True, "catalog_version": "claim-predicate-v3",
             "outcome": "accepted", "failure_category": "schema_failure"},
        ],
    }))
    (scope / "frozen.db").write_bytes(b"fixture")
    runner._validate_structured_scope(scope, {"group_id": "g",
                                               "history": [{"speaker": "Good"}, {"speaker": "Bad"}]})
