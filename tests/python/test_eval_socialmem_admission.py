"""Evidence admission must fail closed without inventing or rewriting claims."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_admission as admission


def case(**overrides):
    return {"id": "test", "track": "controls", "holder": "Mina",
            "passage": "Mina: I am anxious about the launch.", **overrides}


def candidate(**overrides):
    return {"holder": "Mina", "holder_perspective": "FIRST_PERSON", "subject": "Mina",
            "subject_kind": "cognizer", "predicate": "feels", "object": "anxious about the launch",
            "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0, **overrides}


def response(c, decision="retain", reason="supported", quote=None):
    return json.dumps([{"index": 0, "decision": decision, "reason": reason,
                        "quotes": [c["passage"] if quote is None else quote] if decision == "retain" else []}])


def test_admitted_candidate_is_unchanged_and_has_utf8_source_offsets():
    c = case(passage="Mina: 我很担心明天的演示。")
    row = candidate(object="担心明天的演示")
    result = admission.apply_decisions(c, [row], response(c, quote="我很担心明天的演示。"))
    assert result["ok"] and result["retained"] == [0]
    assert result["candidates"] == [row]
    span, = result["decisions"][0]["evidence"]
    payload = c["passage"].encode("utf-8")
    assert payload[span["start_byte"]:span["end_byte"]].decode("utf-8") == span["quote"]


@pytest.mark.parametrize("raw", ["[]\n[]", "not JSON", '[{"index":true}]', '[]',
    '[{"index":0,"decision":"retain","reason":"supported","quotes":["invented"]}]'])
def test_incomplete_or_unverifiable_verdicts_do_not_admit_anything(raw):
    result = admission.apply_decisions(case(), [candidate()], raw)
    assert not result["ok"] and result["candidates"] == []


def test_duplicate_indexes_and_candidate_rewrites_are_rejected():
    c = case()
    verdict = json.loads(response(c))[0]
    for raw in (json.dumps([verdict, verdict]), json.dumps([{**verdict, "object": "rewritten"}])):
        assert not admission.apply_decisions(c, [candidate()], raw)["ok"]


def test_schema_holder_and_scope_rejection_precedes_admission():
    c = case()
    for row in (candidate(holder="Other"), candidate(subject_kind="entity"), candidate(predicate="believes"),
                candidate(nesting_depth=2), candidate(modality="DESIRES")):
        result = admission.apply_decisions(c, [row], response(c))
        assert result["ok"] and result["retained"] == []
        assert result["decisions"][0]["schema_errors"]


def test_empty_and_failed_upstream_outputs_stay_distinct():
    valid = admission.review_input({"raw": "[]", "ok": True, "error": ""})
    failed = admission.review_input({"raw": "[]\n[]", "ok": True, "error": ""})
    assert valid == {"ok": True, "candidates": [], "error": ""}
    assert not failed["ok"] and failed["error"]


def test_prompt_never_contains_control_labels_or_qa_gold():
    c = case(expected_keep=True, question="SECRET QUESTION", answer="SECRET GOLD")
    prompt = admission.gate_prompt(c, [candidate()])
    assert "SECRET" not in prompt and "expected_keep" not in prompt
    assert c["passage"] in prompt


def test_model_rejection_does_not_count_as_gate_failure():
    c = case()
    result = admission.apply_decisions(c, [candidate()], response(c, "reject", "wrong_relation"))
    assert result["ok"] and result["retained"] == []


def test_failed_gate_is_not_a_correct_negative_control(tmp_path):
    from starling import _core

    c = case(track="admission_controls", expected_keep=False)
    entry = {"case": c, "base": None, "original": {"raw": json.dumps([candidate()]), "ok": True, "error": ""}}
    fake = _core.FakeLLMAdapter()
    fake.set_default_response("[]", ok=False, error="offline")
    result = admission.admit(_core, fake, entry, tmp_path)
    metrics = admission.control_scores([entry], [result])
    assert metrics["correct"] == 0 and metrics["technical_failures"] == 1
    assert metrics["false_accepts"] == 0
    extra = admission.transformed(result, c, "{convo}")
    assert not extra["ok"] and extra["error"]
    assert len(admission.lines(tmp_path / "admission_calls.jsonl")) == 1


def test_rejection_leaves_base_memory_intact_through_native_replay(tmp_path):
    from starling import _core

    c = case(track="synthetic")
    row = candidate()
    decision = admission.apply_decisions(c, [row], response(c, "reject", "wrong_relation"))
    templates = {"baseline": "{convo}", "supplement": "{convo}"}
    extra = admission.transformed(decision, c, templates["supplement"])
    base = {"ok": True, "error": "", "raw": json.dumps([candidate(predicate="prefers", object="quiet")]),
            "prompt": c["passage"]}
    (tmp_path / "databases").mkdir()
    native = admission.supplement.evaluate_case(_core, c, base, extra, templates, tmp_path, admission.NOW)
    native = json.loads(json.dumps(native))
    assert native["base_semantics_preserved"] and len(native["after"]) == 1
    assert native["rows"] == []
    admission.native_verifier.check_case(_core, tmp_path, c, base, extra, templates, native, admission.NOW)


def test_duplicate_quote_occurrences_and_json_keys_fail_closed():
    c = case(passage="Mina: Worried. Mina: Worried.")
    assert not admission.apply_decisions(c, [candidate()], response(c, quote="Worried."))["ok"]
    duplicate = '[{"index":0,"index":0,"decision":"reject","reason":"unsupported","quotes":[]}]'
    assert not admission.apply_decisions(case(), [candidate()], duplicate)["ok"]


def test_judge_candidate_ignores_row_order_and_ids_but_preserves_semantic_multiset():
    rename = {"holder": "holder_id", "subject": "subject_id", "object": "object_value"}
    row = {rename.get(k, k): v for k, v in candidate().items()}
    rows = [{**row, "id": "first"}, {**row, "id": "second", "object_value": "relieved about the launch"},
            {**row, "id": "third"}]
    permuted = [{**rows[i], "id": f"new-{i}"} for i in (2, 0, 1)]
    canonical = admission.judge_candidate(rows)
    assert canonical == admission.judge_candidate(permuted)
    assert len(json.loads(canonical)) == 3
    assert canonical != admission.judge_candidate(rows[:2])
    assert canonical != admission.judge_candidate([*rows[:2], {**row, "polarity": "NEG"}])


def test_overlapping_quote_occurrences_are_ambiguous():
    c = case(passage="Mina: I am worried about the banana shipment.")
    result = admission.apply_decisions(c, [candidate()], response(c, quote="ana"))
    assert not result["ok"] and result["retained"] == []


def test_completion_distinguishes_technical_failure_from_semantic_rejection():
    c = case()
    rejected = {"upstream_ok": True, **admission.apply_decisions(c, [candidate()],
                response(c, "reject", "wrong_relation"))}
    native = {"native_ok": True, "object_fidelity": True, "base_receipt": {"extraction_failed": False}}
    judged = {"judgment": {"ok": False, "failed": 0}}
    clean = admission.failure_counts([rejected], [native], [judged])
    assert admission.completion_status(clean) == "complete"
    inherited = admission.failure_counts([{**rejected, "upstream_ok": False, "ok": False}],
                                        [{**native, "native_ok": False}], [judged])
    assert inherited["upstream_failures"] == inherited["native_failures"] == 1
    assert inherited["admission_failures"] == 0
    assert admission.completion_status(inherited) == "complete_with_errors"
    broken = admission.failure_counts([{**rejected, "ok": False}], [native],
                                      [{"judgment": {"ok": False, "failed": 3}}])
    assert broken["admission_failures"] == 1 and broken["invalid_judge_votes"] == 3
    assert admission.completion_status(broken) == "complete_with_errors"
