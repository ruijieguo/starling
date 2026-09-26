"""Controlled predicate regression and general-fact envelope follow-up."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_followup as followup


def test_format_factor_preserves_semantics_and_has_one_bare_empty_example():
    from starling.extractor.general_fact_prompt import GENERAL_FACT_EXTRACTION_PROMPT as original

    modified = followup.single_array_prompt(original)
    assert original != modified
    assert modified.count("{convo}") == original.count("{convo}") == 1
    assert modified.count("{self}") == original.count("{self}")
    assert "JSON array:\n[]\n\nPassage:" in modified
    assert "ONE JSON array" in modified
    assert followup.EMPTY_EXPLANATION in modified
    assert "DO NOT extract" in modified and "standalone DECLARATIVE FACTS" in modified
    assert "uncertain_about" not in modified
    with pytest.raises(ValueError, match="anchor"):
        followup.single_array_prompt("unrecognized template")


def test_empty_duplicate_response_is_a_recorded_native_failure(tmp_path):
    from starling import _core

    llm = _core.FakeLLMAdapter()
    raw = "[]\n```json\n[]\n```"
    llm.set_default_response(raw)
    case = {"id": "empty", "track": "general_fact", "holder": "Lena", "passage": "Lena: Thanks.", "expected": []}
    (tmp_path / "databases").mkdir()
    result = followup.evaluate(_core, llm, case, "baseline", "Extract {self}: {convo}", tmp_path,
                               "2099-01-01T00:00:00Z")
    assert result["receipt"]["extraction_failed"]
    assert result["parse_error"] and not result["strict_json"]
    assert result["generic_exact"] is False
    assert result["rows"] == [] and all(status == "failed" for _, status in result["pipelines"])
    call, = followup.trial.extraction.load_lines(tmp_path / "extraction_calls.jsonl")
    assert call["raw"] == raw and call["prompt"] == "Extract Lena: Lena: Thanks."
    assert followup.trial.controls.frozen_database_hash(tmp_path / result["database"]) == result["database_sha256"]


def test_valid_fact_uses_native_normalization_and_retains_raw(tmp_path):
    from starling import _core

    llm = _core.FakeLLMAdapter()
    raw = json.dumps([{"holder": "Lena", "holder_perspective": "FIRST_PERSON", "subject": "boiler",
                       "subject_kind": "entity", "predicate": "has_property", "object": "noisy",
                       "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0}])
    llm.set_default_response(raw)
    case = {"id": "mixed", "track": "general_fact", "holder": "Lena", "passage": "The boiler is noisy.",
            "expected": [["boiler", "has_property", "noisy", "pos"]]}
    (tmp_path / "databases").mkdir()
    result = followup.evaluate(_core, llm, case, "single_array", "Extract {self}: {convo}", tmp_path,
                               "2099-01-01T00:00:00Z")
    assert result["strict_json"] and result["generic_exact"]
    assert not result["receipt"]["extraction_failed"]
    assert result["rows"][0]["object_value"] == "noisy"


def test_followup_uses_all_reviewed_speakers_without_questions_in_payload():
    records = [{"item_id": "test", "source": {"network_id": "test"},
                "question": "SECRET QUESTION", "answer": "SECRET GOLD",
                "evaluation_protocol": {"status": "include", "sessions": [1]},
                "history": [{"speaker": holder, "text": "Thank you.", "turn_id": str(i),
                             "session_index": 1, "message_index": i, "observed_at": "2025-01-01T00:00:00"}
                            for i, holder in enumerate(("Zoe", "Ada"))]}]
    cases = followup.fact_cases(records)
    assert len(cases) == 10
    assert [c["holder"] for c in cases[:2]] == ["Ada", "Zoe"]
    assert all("SECRET" not in c["passage"] for c in cases)


def test_failed_response_is_not_scored_as_correct_empty_output():
    case = {"track": "general_fact", "expected": []}
    result = followup.score(case, "[]", {"extraction_failed": True}, [], True)
    assert result["generic_exact"] is False
    assert result["native_ok"] is False


def test_followup_failure_counts_remain_in_summary_denominator():
    row = {"track": "general_fact", "arm": "baseline", "receipt": {"extraction_failed": True},
           "ok": True, "native_ok": False, "strict_json": False, "parse_error": "invalid", "generic_exact": False}
    summary = followup.summarize([row])
    assert summary["general_fact"]["baseline"]["cases"] == 1
    assert summary["general_fact"]["baseline"]["native_failed"] == 1
    assert summary["general_fact"]["baseline"]["generic_exact"] == 0


def test_transport_failure_is_replayed_as_native_failure(tmp_path):
    from starling import _core

    llm = _core.FakeLLMAdapter()
    llm.set_default_response("[]", ok=False, error="transport interrupted")
    case = {"id": "transport", "track": "general_fact", "holder": "Lena", "passage": "Thanks.", "expected": []}
    (tmp_path / "databases").mkdir()
    result = followup.evaluate(_core, llm, case, "baseline", "{convo}", tmp_path, "2099-01-01T00:00:00Z")
    assert result["receipt"]["extraction_failed"]
    assert all(status == "failed" for _, status in result["pipelines"])
    assert not result["generic_exact"]


@pytest.mark.parametrize("depth", ["0", None])
def test_p1_schema_error_is_explicit_and_keeps_empty_prediction_denominator(depth):
    truth = {"holder": "Lena", "holder_perspective": "FIRST_PERSON", "predicate": "knows", "object": "room",
             "nesting_depth": 2}
    case = {"track": "p1", "holder": "Lena", "record": {"ground_truth_statements": [truth]}}
    raw = json.dumps([{"predicate": "knows", "object": "other", "nesting_depth": depth}])
    result = followup.score(case, raw, {"extraction_failed": True}, [], True)
    assert result["metric_error"].startswith("TypeError:")
    assert result["p1_counts"] == followup.trial.extraction.p1.evaluate_record(case["record"], [])


def test_discarded_malformed_claim_does_not_pass_empty_control():
    result = followup.score({"track": "general_fact", "expected": []}, "[{}]",
                            {"extraction_failed": False}, [], True)
    assert result["strict_json"]
    assert not result["generic_exact"]
