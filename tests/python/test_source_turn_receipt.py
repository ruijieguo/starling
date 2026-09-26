"""SourceTurn payload and native three-channel receipt RED tests."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ladder = load("eval_ladder")
runner = load("run_socialmem_baseline")


class _FakeCore:
    class _Prepared:
        should_extract = True
        outcome = "accepted"

    def __init__(self):
        self.payloads = []
        self.receipt_calls = 0

    def claim_source_turn_payload(self, turns_json, preserve_invalid_time=False):
        from starling import _core
        self.payloads.append(json.loads(turns_json))
        return _core.claim_source_turn_payload(turns_json, preserve_invalid_time)

    def memory_remember_prepare(self, *args, **kwargs):
        return self._Prepared()

    def memory_remember_extract_all(self, *args, **kwargs):
        return object()

    def memory_remember_bundle_receipt(self, bundle):
        self.receipt_calls += 1
        return json.dumps({
            "schema_version": 1,
            "channels": {
                "belief": {"attempts": []},
                "general_fact": {"attempts": []},
                "episodic": {"response": {"raw_xml": "[]"}, "event_count": 0},
            },
        })

    def memory_remember_commit_all(self, *args, **kwargs):
        return {"extraction_failed": False, "statement_ids": []}


def test_real_extract_uses_native_source_turn_metadata_and_bundle_receipt(monkeypatch):
    core = _FakeCore()
    monkeypatch.setattr(ladder, "_build_extract_llm", lambda *args, **kwargs: object())
    extract = ladder.make_real_extract_fn(core, "qwen", "dashscope")
    history = [
        {"speaker": "Mina", "text": "I visited the park.", "session_index": 3,
         "message_index": 8, "turn_id": "s3_t8", "observed_at": "2026-01-03T10:00:00Z",
         "answer": "MUST_NOT_ENTER"},
    ]
    result = extract("adapter", {"history": history}, "qwen")
    assert core.payloads[0][0]["session_id"] == "3"
    assert core.payloads[0][0]["turn_id"] == "s3_t8"
    assert core.payloads[0][0]["turn_index"] == 8
    assert core.payloads[0][0]["observed_at"] == "2026-01-03T10:00:00Z"
    assert "MUST_NOT_ENTER" not in json.dumps(core.payloads, ensure_ascii=False)
    assert core.receipt_calls == 1
    assert result[0]["receipt"]["channels"]["episodic"]["event_count"] == 0


def test_real_extract_forwards_invalid_time_policy_to_native_renderer(monkeypatch):
    core = _FakeCore()
    monkeypatch.setattr(ladder, "_build_extract_llm", lambda *args, **kwargs: object())
    extract = ladder.make_real_extract_fn(core, preserve_invalid_time=True)
    result = extract("adapter", {"history": [{
        "speaker": "Mina", "text": "old", "observed_at": "2026-02-30T10:00:00",
    }]}, "qwen")
    assert result[0]["receipt"]["schema_version"] == 1


def test_scope_receipt_archive_has_one_complete_receipt_per_holder(tmp_path):
    outcomes = [
        {"holder": "Mina", "receipt": {"schema_version": 1, "channels": {
            "belief": {}, "general_fact": {}, "episodic": {}}}},
        {"holder": "Owen", "receipt": {"schema_version": 1, "channels": {
            "belief": {}, "general_fact": {}, "episodic": {}}}},
    ]
    path = runner.write_extraction_receipt_archive(tmp_path, outcomes)
    archived = json.loads(path.read_text(encoding="utf-8"))
    assert archived["schema_version"] == 1
    assert set(archived["holders"]) == {"Mina", "Owen"}
    for receipt in archived["holders"].values():
        assert set(receipt["channels"]) == {"belief", "general_fact", "episodic"}


def test_scope_receipt_archive_rejects_duplicate_or_missing_holder(tmp_path):
    with pytest.raises(ValueError, match="duplicate holder"):
        complete = {"schema_version": 1, "channels": {
            "belief": {}, "general_fact": {}, "episodic": {}}}
        runner.write_extraction_receipt_archive(tmp_path, [
            {"holder": "Mina", "receipt": complete},
            {"holder": "Mina", "receipt": complete},
        ])
    with pytest.raises(ValueError, match="receipt"):
        runner.write_extraction_receipt_archive(tmp_path, [{"holder": "Mina"}])
