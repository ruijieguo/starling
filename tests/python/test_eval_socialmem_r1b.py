import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_r1b as evaluation


def test_budget_rejects_overflow_and_capability_gate_stops_samples():
    budget = evaluation.Budget(max_probe=8, max_extract=2, max_admission=2)
    budget.consume("probe", 8)
    with pytest.raises(ValueError, match="probe"):
        budget.consume("probe")
    assert evaluation.capability_gate({"D0": {"ready": True}, "D1": {"ready": False}}) is False
    assert evaluation.schedule_samples([{"id": "a"}], arms=("D0", "D1"), repetitions=2,
                                       capabilities={"D0": {"ready": True}, "D1": {"ready": False}}) == []


def test_schedule_is_bounded_and_alternates_arms():
    cases = [{"id": f"s{i}", "holder": "Mina", "passage": "Mina: hi"} for i in range(4)]
    rows = evaluation.schedule_samples(cases, arms=("D0", "D1"), repetitions=2)
    assert len(rows) == 16
    assert all(r["arm"] in ("D0", "D1") and r["repetition"] in (0, 1) for r in rows)
    assert rows[0]["arm"] != rows[1]["arm"]


def test_worker_bad_json_and_empty_candidates_skip_admission(monkeypatch):
    from starling import _core
    core = _core
    config = {"model": "fake", "endpoint": "offline", "timeout_ms": 1,
              "max_tokens": 4096, "max_retries": 0, "temperature": 0,
              "output_mode": "json_schema_strict"}
    case = {"id": "x", "track": "T", "holder": "Mina", "passage": "Mina: hi"}
    fake = core.FakeLLMAdapter()
    prompt = core.claim_extraction_prompt(case["passage"], case["holder"])
    fake.set_response(core.Extractor.compute_prompt_input_hash(prompt), "not json", True, "")
    result = evaluation.worker_sample(core, fake, config, case, admission_llm=fake)
    assert result["admission"]["called"] is False
    assert result["status"] in {"parse_failure", "empty_candidates"}


def test_worker_native_admission_replay_retains_or_rejects_without_python_apply():
    from starling import _core
    core = _core
    case = {"id": "x", "track": "T", "holder": "Mina",
            "passage": "Mina: I am worried about launch."}
    row = {"holder": "Mina", "holder_perspective": "FIRST_PERSON", "subject": "Mina",
           "subject_kind": "cognizer", "predicate": "feels", "object": "worried about launch",
               "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0, "confidence": None,
               "evidence": {"clause_id": "c0", "actor": "Mina", "attributed_to": None, "assertion_scope": "ASSERTED",
                        "scope_markers": ["ASSERTED"], "time_text": "", "event_time": None,
                        "topic": "launch"}}
    raw = json.dumps({"schema_version": 2, "statements": [row]}, ensure_ascii=False)
    extraction = core.FakeLLMAdapter()
    ep = core.claim_extraction_prompt(case["passage"], case["holder"])
    extraction.set_response(core.Extractor.compute_prompt_input_hash(ep), raw, True, "")
    admission = core.FakeLLMAdapter()
    admission.set_default_response(json.dumps({"schema_version": 1, "decisions": [{"index": 0,
        "retain": True, "reason": "supported"}]}), True, "")
    result = evaluation.worker_sample(core, extraction, {"model": "fake", "endpoint": "offline",
        "timeout_ms": 1, "max_tokens": 4096, "max_retries": 0, "temperature": 0,
        "output_mode": "json_schema_strict"}, case, admission_llm=admission)
    assert result["admission"]["called"] is True
    assert result["receipt"]["schema_version"] == 2
    assert len(result["retained"]) == 1
    assert result["retained"][0]["object"] == "worried about launch"


def test_worker_writes_extraction_and_admission_preview_before_request(tmp_path):
    from starling import _core
    case = {"id": "x", "track": "T", "holder": "Mina", "passage": "Mina: hi"}
    fake = _core.FakeLLMAdapter()
    p = _core.claim_extraction_prompt(case["passage"], case["holder"])
    fake.set_response(_core.Extractor.compute_prompt_input_hash(p), "not json", True, "")
    seen = []
    result = evaluation.worker_sample(_core, fake, {"model": "fake", "endpoint": "offline",
        "timeout_ms": 1, "max_tokens": 4096, "max_retries": 0, "temperature": 0,
        "output_mode": "json_schema_strict"}, case, artifact_dir=tmp_path,
        before_request=lambda kind: seen.append(kind))
    assert (tmp_path / "extraction.json").is_file()
    assert not (tmp_path / "admission_preview.json").exists()
    assert seen == ["extract"]


def test_admission_preview_exists_before_external_call(tmp_path):
    from starling import _core
    case = {"id": "x", "track": "T", "holder": "Mina", "passage": "Mina: I am worried about launch."}
    row = {"holder": "Mina", "holder_perspective": "FIRST_PERSON", "subject": "Mina",
           "subject_kind": "cognizer", "predicate": "feels", "object": "worried about launch",
           "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0, "confidence": None,
           "evidence": {"clause_id": "c0", "actor": "Mina", "attributed_to": None,
                        "assertion_scope": "ASSERTED", "scope_markers": ["ASSERTED"],
                        "time_text": "", "event_time": None, "topic": "launch"}}
    raw = json.dumps({"schema_version": 2, "statements": [row]})
    extraction = _core.FakeLLMAdapter(); p = _core.claim_extraction_prompt(case["passage"], "Mina")
    extraction.set_response(_core.Extractor.compute_prompt_input_hash(p), raw, True, "")
    admission = _core.FakeLLMAdapter(); admission.set_default_response("{}", False, "offline")
    seen = []
    evaluation.worker_sample(_core, extraction, {"model": "fake", "endpoint": "offline", "timeout_ms": 1,
        "max_tokens": 4096, "max_retries": 0, "temperature": 0, "output_mode": "json_schema_strict"}, case,
        admission_llm=admission, artifact_dir=tmp_path,
        before_request=lambda kind: seen.append((kind, (tmp_path / "admission_preview.json").exists())))
    assert ("admission", True) in seen


def test_admission_failure_statuses_are_distinct():
    assert evaluation.admission_status({"ok": False, "error": "timeout"}) == "admission_transport_failure"
    assert evaluation.admission_status({"ok": True, "wire_error": "schema_failure:x"}) == "admission_protocol_failure"
    assert evaluation.admission_status({"ok": True, "wire_error": None, "parse_errors": ["x"]}) == "admission_parse_failure"
    assert evaluation.admission_status({"ok": True, "wire_error": None, "parse_errors": [], "retained": []}) == "admission_rejected"


def test_supervisor_plan_stops_on_failed_arm_and_budget_overflow():
    from run_socialmem_r1b import build_plan
    cases = [{"id": str(i)} for i in range(4)]
    blocked = build_plan({"D0": {"ready": True, "request_count": 8},
                          "D1": {"ready": False, "request_count": 8}}, cases)
    assert blocked["status"] == "blocked_capability" and blocked["schedule"] == []
    with pytest.raises(ValueError, match="extract"):
        build_plan({"D0": {"ready": True, "request_count": 8},
                    "D1": {"ready": True, "request_count": 8}}, cases + [{"id": "x"}])


def test_worker_rejects_nonzero_retry_or_non_strict_mode_before_request():
    from starling import _core
    case = {"id": "guard", "track": "T", "holder": "Mina", "passage": "Mina: hi"}
    fake = _core.FakeLLMAdapter()
    config = {"model": "fake", "endpoint": "offline", "timeout_ms": 1,
              "max_tokens": 4096, "max_retries": 1, "temperature": 0,
              "output_mode": "json_schema_strict"}
    with pytest.raises(ValueError, match="retries"):
        evaluation.worker_sample(_core, fake, config, case)
    config["max_retries"] = 0
    config["output_mode"] = "legacy"
    with pytest.raises(ValueError, match="extraction mode"):
        evaluation.worker_sample(_core, fake, config, case)
