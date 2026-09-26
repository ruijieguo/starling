"""Failure handling and semantic measurement for the next isolated trial."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_contracts as contracts


def claim(**overrides):
    return {"holder": "Nora", "holder_perspective": "FIRST_PERSON", "subject": "Nora",
            "subject_kind": "cognizer", "cognizer_kind": "human", "predicate": "feels",
            "object": "anxious about exam", "modality": "BELIEVES", "polarity": "POS",
            "nesting_depth": 0, **overrides}


def test_contract_transform_preserves_original_predicate_rules():
    from starling.extractor.prompts import EXTRACTION_PROMPT
    import eval_socialmem_predicates as trial

    vocabulary = trial.with_vocabulary(EXTRACTION_PROMPT)
    modified = contracts.belief_contract(vocabulary)
    assert modified.count("{convo}") == 1
    for anchor in ("HOLDER vs SUBJECT (CRITICAL):", "CANONICAL OBJECT FOR responsible_for (CRITICAL):",
                   "POLICY-AS-HOLDER (CRITICAL):", "NESTING DEPTH for 2nd-order beliefs:"):
        original_section = vocabulary.split(anchor, 1)[1].split("\n\n", 1)[0]
        assert original_section == modified.split(anchor, 1)[1].split("\n\n", 1)[0]
    assert "uncertain_about" in modified and "BELIEVES + POS" in modified
    with pytest.raises(ValueError, match="anchor"):
        contracts.belief_contract("unknown template")


def test_relation_rules_are_not_a_vacuous_semantic_success():
    assert contracts.relation_rules([]) == {"emitted": 0, "violations": []}
    bad = claim(subject="problem", subject_kind="entity", modality="DESIRES")
    result = contracts.relation_rules([bad])
    assert result["emitted"] == 1
    assert result["violations"][0]["fields"] == ["subject_kind", "modality"]
    assert contracts.relation_rules([claim()])["violations"] == []


def test_rule_checks_do_not_crash_on_invalid_json_fields():
    result = contracts.relation_rules([claim(predicate=[]), claim(subject=None, polarity=[]),
                                       claim(modality={})])
    assert result["emitted"] == 2
    assert len(result["violations"]) == 2


def test_explicit_uncertainty_and_temporal_checks_require_emitted_evidence():
    raw = [claim(predicate="uncertain_about", polarity="UNKNOWN")]
    assert contracts.case_checks("undecided", raw)["affirmed_uncertainty"] is False
    raw[0]["polarity"] = "POS"
    assert contracts.case_checks("undecided", raw)["affirmed_uncertainty"] is True
    assert contracts.case_checks("decision_change", [])["temporal_qualifiers"] is False
    history = [claim(predicate="uncertain_about", object="last week: workshop"),
               claim(predicate="decided_on", object="today: attend workshop", modality="INTENDS")]
    assert contracts.case_checks("decision_change", history)["temporal_qualifiers"] is True


def test_invalid_and_failed_judgments_are_archived_without_quality_retry(tmp_path):
    outputs = iter(["YES", "YES because it is correct", OSError("offline")])
    calls = []

    def chat(prompt, model, max_tokens):
        calls.append((prompt, model, max_tokens))
        reply = next(outputs)
        if isinstance(reply, Exception):
            raise reply
        return reply

    case = {"id": "test", "track": "synthetic", "question": "question", "answer": "reference"}
    judgment = contracts.judge(chat, case, "contract", "[]", tmp_path)
    assert len(calls) == 3 and all(c[1:] == ("gpt-5.5", 8) for c in calls)
    assert judgment["acceptances"] == 1 and judgment["failed"] == 2
    assert judgment["ok"] is False
    raw = [json.loads(line) for line in (tmp_path / "judge_responses.jsonl").read_text().splitlines()]
    assert [r["raw"] for r in raw] == ["YES", "YES because it is correct", ""]
    assert raw[2]["error"] == "OSError: offline"


def test_candidate_uses_all_stored_semantic_fields_in_receipt_order():
    import eval_socialmem_predicates as trial

    rows = [{"id": sid, **{key: sid for key in trial.SEMANTIC_FIELDS}} for sid in ("a", "b")]
    candidate = json.loads(contracts.candidate(rows, {"statement_ids": ["b", "a"]}))
    assert candidate == [{key: sid for key in trial.SEMANTIC_FIELDS} for sid in ("b", "a")]


def test_contract_policy_registers_relations_and_failure_keeps_database(tmp_path):
    from starling import _core

    case = {"id": "test", "track": "synthetic", "holder": "Nora", "passage": "Nora: I feel anxious.",
            "question": "SECRET QUESTION", "answer": "SECRET REFERENCE"}
    llm = _core.FakeLLMAdapter()
    llm.set_default_response(json.dumps([claim()]))
    (tmp_path / "databases").mkdir()
    result = contracts.evaluate(_core, llm, case, "contract", "Extract {convo}", tmp_path,
                                "2099-01-01T00:00:00Z")
    assert result["native_ok"]
    assert result["rows"][0]["predicate"] == "feels"
    assert result["rows"][0]["review_status"] == "approved"
    assert result["raw_rules"]["emitted"] == 1
    raw = [json.loads(line) for line in (tmp_path / "extraction_calls.jsonl").read_text().splitlines()]
    assert "SECRET" not in raw[0]["prompt"]
    llm.set_default_response("[]\n```json\n[]\n```")
    failed = contracts.evaluate(_core, llm, case, "vocabulary", "{convo}", tmp_path,
                                "2099-01-01T00:00:00Z")
    assert not failed["native_ok"] and failed["parse_error"]
    assert (tmp_path / failed["database"]).is_file()
    assert failed["pipelines"][0][1] == "failed"


def test_general_fact_empty_response_still_fails_mixed_control():
    case = {"id": "mixed", "track": "general_fact", "holder": "Nora",
            "expected": [["boiler", "has_property", "noisy", "pos"]]}
    score = contracts.score(case, "[]", {"extraction_failed": False}, [], True)
    assert score["strict_json"] and not score["generic_exact"]


def test_verifier_detects_changed_raw_semantics_even_when_rule_scores_match(tmp_path):
    from starling import _core
    import verify_socialmem_contracts as verifier

    case = {"id": "replay", "track": "synthetic", "holder": "Nora", "passage": "Nora: I feel anxious."}
    llm = _core.FakeLLMAdapter()
    llm.set_default_response(json.dumps([claim()]))
    (tmp_path / "databases").mkdir()
    result = contracts.evaluate(_core, llm, case, "contract", "{convo}", tmp_path, "2099-01-01T00:00:00Z")
    result = json.loads(json.dumps(result))
    call, = contracts.lines(tmp_path / "extraction_calls.jsonl")
    manifest = {"query_time": "2099-01-01T00:00:00Z"}
    verifier.check_case(_core, tmp_path, manifest, case, "contract", "{convo}", result, call)
    changed = {**call, "raw": json.dumps([claim(object="happy about exam")])}
    with pytest.raises(AssertionError):
        verifier.check_case(_core, tmp_path, manifest, case, "contract", "{convo}", result, changed)


def test_technical_failure_is_not_a_majority_supported_candidate():
    judgment = {"arm": "contract", "native_ok": False, "judgment": {"ok": True, "acceptances": 3, "failed": 0}}
    summary = contracts.summarize([], [judgment])
    assert summary["synthetic"]["contract"]["majority_supported"] == 0
