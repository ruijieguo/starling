import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_supplement as experiment


def claim(**overrides):
    return {"holder": "Mina", "holder_perspective": "FIRST_PERSON", "subject": "Mina",
            "subject_kind": "cognizer", "predicate": "feels", "object": "sad to leave my colleagues",
            "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0, **overrides}


def test_supplement_preserves_base_native_semantics_and_objects(tmp_path):
    from starling import _core

    case = {"track": "synthetic", "id": "test", "holder": "Mina", "passage": "Mina: My update.",
            "question": "SECRET QUESTION", "answer": "SECRET GOLD"}
    templates = {"baseline": "Extract {convo}", "supplement": experiment.SUPPLEMENT_PROMPT}
    base = {"raw": json.dumps([claim(predicate="prefers", object="the cabbages", modality="DESIRES")]),
            "ok": True, "error": ""}
    extra = {"raw": json.dumps([claim()]), "ok": True, "error": ""}
    (tmp_path / "databases").mkdir()
    result = experiment.evaluate_case(_core, case, base, extra, templates, tmp_path, experiment.NOW)
    assert result["base_semantics_preserved"]
    assert result["before"][0]["object_value"] == "cabbage"
    assert result["rows"][0]["object_value"] == "sad to leave my colleagues"
    assert result["object_fidelity"] and result["native_ok"]
    assert len(result["after"]) == 2
    fake = _core.FakeLLMAdapter()
    fake.set_default_response("[]")
    call = experiment.complete(_core, fake, case, templates["supplement"], "supplement", tmp_path)
    assert "SECRET" not in call["prompt"]


@pytest.mark.parametrize("raw,ok,error", [("[]\n[]", True, ""), ("[]", False, "transport")])
def test_failures_are_archived_and_fail_empty_control(tmp_path, raw, ok, error):
    from starling import _core

    case = {"track": "controls", "id": "test", "holder": "Mina", "passage": "Thanks", "expected": []}
    (tmp_path / "databases").mkdir()
    result = experiment.evaluate_case(_core, case, None, {"raw": raw, "ok": ok, "error": error},
        {"supplement": experiment.SUPPLEMENT_PROMPT}, tmp_path, experiment.NOW)
    assert not result["native_ok"] and not result["control_exact"]
    assert (tmp_path / result["database"]).is_file()


def test_rules_expose_unlisted_predicate_without_rewriting():
    row = claim(predicate="prefers")
    result = experiment.check_supplement({"id": "test", "holder": "Mina"}, json.dumps([row]), [],
                                         {"extraction_failed": False}, True)
    assert result["invalid_predicates"] == [0]
    assert not result["object_fidelity"]


def test_answer_transport_failure_still_records_three_judgments(tmp_path):
    calls = []

    def chat(prompt, model, max_tokens):
        calls.append(max_tokens)
        if max_tokens == 512:
            raise OSError("offline")
        return "NO"

    record = {"item_id": "test", "question": "Question", "answer": "Reference", "task_type": "qa"}
    result = experiment.answer(chat, record, "baseline", "memory", tmp_path)
    assert not result["answer_ok"]
    assert result["judgment"]["acceptances"] == 0
    assert calls == [512, 8, 8, 8]


def test_failed_supplement_native_replay_ignores_random_pipeline_id_order(tmp_path):
    from starling import _core
    import verify_socialmem_supplement as verifier

    case = {"track": "synthetic", "id": "mixed_pipeline", "holder": "Mina", "passage": "My update"}
    templates = {"baseline": "Extract {convo}", "supplement": experiment.SUPPLEMENT_PROMPT}
    base = {"raw": "[]", "ok": True, "error": "", "prompt": experiment.render(templates["baseline"], case)}
    extra = {"raw": "[]\n[]", "ok": True, "error": "",
             "prompt": experiment.render(templates["supplement"], case)}
    (tmp_path / "databases").mkdir()
    result = experiment.evaluate_case(_core, case, base, extra, templates, tmp_path, experiment.NOW)
    result = json.loads(json.dumps(result))
    assert sorted(r[1] for r in result["pipelines"]) == ["failed", "finished"]
    verifier.check_case(_core, tmp_path, case, base, extra, templates, result, experiment.NOW)


def test_native_replay_compares_stored_object_multisets(tmp_path):
    from starling import _core
    import verify_socialmem_supplement as verifier

    case = {"track": "synthetic", "id": "multi", "holder": "Mina", "passage": "My update"}
    templates = {"supplement": experiment.SUPPLEMENT_PROMPT}
    extra = {"raw": json.dumps([claim(), claim(object="excited about the fellowship")]),
             "ok": True, "error": "", "prompt": experiment.render(templates["supplement"], case)}
    (tmp_path / "databases").mkdir()
    result = experiment.evaluate_case(_core, case, None, extra, templates, tmp_path, experiment.NOW)
    result = json.loads(json.dumps(result))
    result["stored_objects"].reverse()
    verifier.check_case(_core, tmp_path, case, None, extra, templates, result, experiment.NOW)
