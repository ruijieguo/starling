"""Exercise native raw-response replay and strict preference comparison."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_extraction as experiment


@pytest.mark.parametrize("polarity", ["POS", "NEG", "UNKNOWN"])
def test_native_replay_preserves_relation_scope(tmp_path, polarity):
    raw = json.dumps([{"holder": "Nora", "holder_perspective": "FIRST_PERSON",
                       "subject": "Nora", "subject_kind": "cognizer", "cognizer_kind": "human",
                       "predicate": "prefers", "object": "smoke-free room", "modality": "DESIRES",
                       "polarity": polarity, "nesting_depth": 0}])
    replay = experiment.native_replay(raw, "Nora: room preference", "Nora", "{convo}", tmp_path / "native.db")
    assert experiment.controls.frozen_database_hash(tmp_path / "native.db")
    assert len(replay["rows"]) == 1
    row = replay["rows"][0]
    assert row["subject_id"] == row["holder_id"] == "Nora"
    assert row["subject_kind"] == "cognizer"
    assert row["object_value"] == "smoke-free room"
    assert row["polarity"] == polarity.lower()
    assert row["modality"] == "desires"


def test_replay_exposes_bad_model_subject_without_rewriting(tmp_path):
    raw = json.dumps([{"holder": "Nora", "subject": "room", "subject_kind": "entity",
                       "predicate": "prefers", "object": "smoke-free room", "polarity": "NEG",
                       "holder_perspective": "FIRST_PERSON", "modality": "DESIRES"}])
    result = experiment.native_replay(raw, "Nora: preference", "Nora", "{convo}", tmp_path / "bad.db")
    assert result["rows"][0]["subject_id"] == "room"
    record = {"subject": "Nora", "speaker": "Nora", "objects": ["smoke-free room"], "polarity": "neg"}
    assert not experiment.preference_score(record, result["rows"])["relation_ok"]


def test_preference_score_rejects_contradictory_extra_prediction():
    record = {"subject": "Nora", "speaker": "Nora", "objects": ["tea"], "polarity": "pos"}
    row = {"subject_id": "Nora", "holder_id": "Nora", "subject_kind": "cognizer",
           "predicate": "prefers", "object_value": "tea", "polarity": "pos"}
    assert experiment.preference_score(record, [row])["relation_ok"]
    assert not experiment.preference_score(record, [row, {**row, "polarity": "neg"}])["relation_ok"]


def test_parser_rejects_partial_or_malformed_response():
    assert experiment.parse_response('```json\n[]\n```') == []
    with pytest.raises(ValueError):
        experiment.parse_response('[]\n```json\n[]\n```')


def test_raw_cache_requires_identical_inputs_and_preserves_first_response(tmp_path):
    inputs, prompts = [{"id": "case"}], {"before": "old", "after": "new"}
    transport = {"endpoint": "https://provider.test/v1", "max_tokens": 4096}
    experiment.controls.dump(tmp_path / "manifest.json", {
        "core_sha256": "core", "model": "deepseek-v3", "provider": "dashscope", "transport": transport})
    experiment.controls.dump(tmp_path / "inputs.json", inputs)
    experiment.controls.dump(tmp_path / "prompts.json", prompts)
    receipt = {"id": "case", "track": "preference", "phase": "before", "raw": "[]"}
    experiment.ladder.append_journal(tmp_path / "raw_calls.jsonl", receipt)
    cache = experiment.cached_calls(tmp_path, inputs, prompts, "core", transport)
    assert cache[("preference", "case", "before")] == receipt
    with pytest.raises(ValueError, match="configuration does not match"):
        experiment.cached_calls(tmp_path, [{"id": "changed"}], prompts, "core", transport)
    with pytest.raises(ValueError, match="configuration does not match"):
        experiment.cached_calls(tmp_path, inputs, prompts, "core", {**transport, "max_tokens": 512})
    experiment.ladder.append_journal(tmp_path / "raw_calls.jsonl", receipt)
    with pytest.raises(ValueError, match="duplicate cached completion"):
        experiment.cached_calls(tmp_path, inputs, prompts, "core", transport)


def test_provider_cannot_silently_fall_back(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "other-provider-test-key")
    with pytest.raises(ValueError, match="provider fallback is not allowed"):
        experiment.build_llm(None)


def test_provider_records_native_config_and_restores_environment(monkeypatch):
    from starling import _core

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/compatible-mode/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://original.test/v1")
    _, transport = experiment.build_llm(_core)
    assert transport["endpoint"] == "https://example.test/compatible-mode/v1"
    assert transport["model"] == "deepseek-v3"
    assert transport["max_tokens"] == 4096 and transport["temperature"] == 0
    assert "OPENAI_API_KEY" not in experiment.os.environ
    assert experiment.os.environ["OPENAI_BASE_URL"] == "https://original.test/v1"


def test_provider_json_mode_is_explicit_and_recorded(monkeypatch):
    from starling import _core

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/compatible-mode/v1")
    _, default = experiment.build_llm(_core)
    assert "response_format" not in default
    _, transport = experiment.build_llm(_core, json_object_output=True)
    assert transport["response_format"] == {"type": "json_object"}
    assert transport["response_content"] == "verbatim"
