"""claim 合同通道探针：离线夹具验证终态分类、协议形状记录、失败口径与密钥不落盘；不请求外部模型。"""
import importlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

TRANSPORT = {"legacy": {"endpoint": "fixture", "model": "fixture"}}
SECRET = "never-archive-this-secret"


@pytest.fixture
def probe():
    return importlib.import_module("probe_socialmem_claim_channel")


def statement(holder, obj, polarity, markers, topic, *, predicate="prefers", modality="PREFERS"):
    return {"holder": holder, "holder_perspective": "FIRST_PERSON", "subject": holder,
            "subject_kind": "cognizer", "predicate": predicate, "object": obj,
            "modality": modality, "polarity": polarity, "nesting_depth": 0, "confidence": None,
            "evidence": {"clause_id": "c0", "actor": holder, "attributed_to": None,
                         "assertion_scope": "ASSERTED", "scope_markers": markers, "time_text": "",
                         "topic": topic, "event_time": None}}


def decisions(count):
    return json.dumps({"schema_version": 1, "decisions": [
        {"index": i, "retain": True, "reason": "supported"} for i in range(count)]})


def scripted(core, case_id, statements, admission):
    import eval_socialmem_predicates as pred

    case = next(c for c in pred.synthetic_cases() if c["id"] == case_id)
    fake = core.FakeLLMAdapter()
    fake.set_default_response(admission)
    prompt = core.claim_extraction_prompt(case["passage"], case["holder"])
    fake.set_response(core.Extractor.compute_prompt_input_hash(prompt),
                      json.dumps({"schema_version": 2, "statements": statements}))
    return fake


def runs_of(out):
    return [json.loads(line) for line in (out / "runs.jsonl").read_text().splitlines()]


def run_single(probe, core, tmp_path, case_id, statements, admission, repeats=1):
    out = tmp_path / "run"
    summary = probe.run(core, {"legacy": scripted(core, case_id, statements, admission)}, TRANSPORT, out,
                        case_ids=(case_id,), repeats=repeats)
    return summary["cells"][f"{case_id}|legacy"], runs_of(out)


def test_faithful_negation_is_admitted_and_stored(probe, core, tmp_path):
    cell, runs = run_single(probe, core, tmp_path, "negative_target_scope",
        [statement("Dana", "no downtime", "NEG", ["ASSERTED", "NEGATED"], "no downtime")], decisions(1), repeats=2)
    assert cell["runs"] == 2 and cell["outcomes"] == {"admitted": 2}
    assert cell["admission_called"] == 2 and cell["admission_unparsable"] == 0
    assert all(r["stored"] == [{"predicate": "prefers", "object": "no downtime", "polarity": "neg"}] for r in runs)


def test_negative_polarity_without_negated_marker_is_rejected_before_admission(probe, core, tmp_path):
    cell, runs = run_single(probe, core, tmp_path, "negative_target_scope",
        [statement("Dana", "no downtime", "NEG", ["ASSERTED"], "no downtime")], decisions(1))
    assert cell["outcomes"] == {"semantic_rejection": 1}
    assert cell["failure_details"] == {"explicit source marker missing: NEGATED": 1}
    assert cell["admission_called"] == 0
    assert runs[0]["stored"] == []


def test_one_rejected_row_does_not_hide_the_admitted_row(probe, core, tmp_path):
    cell, runs = run_single(probe, core, tmp_path, "preference_contrast",
        [statement("Mateo", "green room", "NEG", ["ASSERTED"], "green room"),
         statement("Mateo", "red room", "POS", ["ASSERTED"], "red room")], decisions(1))
    assert cell["outcomes"] == {"admitted": 1}
    assert cell["rejection_details"] == {"explicit source marker missing: NEGATED": 1}
    assert runs[0]["stored"] == [{"predicate": "prefers", "object": "red room", "polarity": "pos"}]


@pytest.mark.parametrize("admission,balance", [(decisions(2)[:-1], 1), (decisions(2) + "}", -1)],
                         ids=["missing_closing_brace", "extra_closing_brace"])
def test_malformed_admission_envelope_is_a_technical_failure_recorded_literally(
        probe, core, tmp_path, admission, balance):
    cell, runs = run_single(probe, core, tmp_path, "preference_contrast",
        [statement("Mateo", "green room", "NEG", ["ASSERTED", "NEGATED"], "green room"),
         statement("Mateo", "red room", "POS", ["ASSERTED"], "red room")], admission)
    assert cell["outcomes"] == {"technical_failure": 1}
    assert cell["failure_details"] == {"envelope_failure: invalid JSON envelope": 1}
    assert cell["admission_called"] == 1 and cell["admission_unparsable"] == 1
    shape = runs[0]["admission"]
    assert shape["parsable"] is False and shape["brace_balance"] == balance
    assert shape["raw"] == admission, "nothing may be repaired or truncated"
    assert runs[0]["stored"] == []


@pytest.mark.parametrize("topic", ["", "   ", 5], ids=["empty", "blank", "number"])
def test_invalid_topic_reproduces_the_historical_schema_failure(probe, core, tmp_path, topic):
    cell, runs = run_single(probe, core, tmp_path, "negative_target_scope",
        [statement("Dana", "no downtime", "NEG", ["ASSERTED", "NEGATED"], topic)], decisions(1))
    assert cell["outcomes"] == {"technical_failure": 1}
    error = runs[0]["attempt_errors"][0]
    assert error["kind"] == "schema_failure" and error["detail"] == "topic must be null or a nonempty string"
    assert runs[0]["stored"] == []


@pytest.mark.parametrize("topic", [None, "no downtime"], ids=["null", "nonempty"])
def test_null_or_nonempty_topic_is_accepted(probe, core, tmp_path, topic):
    cell, _ = run_single(probe, core, tmp_path, "negative_target_scope",
        [statement("Dana", "no downtime", "NEG", ["ASSERTED", "NEGATED"], topic)], decisions(1))
    assert cell["outcomes"] == {"admitted": 1}


def test_transport_failure_stays_technical_and_leaks_no_secret(probe, core, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    cfg = core.OpenAIAdapterConfig.from_env()
    cfg.timeout_ms = -1
    cfg.model = "probe-fixture"
    out = tmp_path / "run"
    summary = probe.run(core, {"legacy": core.OpenAIAdapter(cfg)}, TRANSPORT, out,
                        case_ids=("negative_target_scope",), repeats=1)
    cell = summary["cells"]["negative_target_scope|legacy"]
    assert cell["outcomes"] == {"technical_failure": 1} and cell["admission_called"] == 0
    for path in out.rglob("*"):
        if path.is_file():
            assert SECRET not in path.read_text()


def test_mode_order_alternates_per_repeat_and_both_modes_are_recorded(probe, core, tmp_path):
    rows = [statement("Dana", "no downtime", "NEG", ["ASSERTED", "NEGATED"], "no downtime")]
    llms = {"legacy": scripted(core, "negative_target_scope", rows, decisions(1)),
            "json_object": scripted(core, "negative_target_scope", rows, decisions(1))}
    transports = {"legacy": {"model": "fixture"}, "json_object": {"model": "fixture"}}
    out = tmp_path / "run"
    summary = probe.run(core, llms, transports, out, case_ids=("negative_target_scope",), repeats=2)
    assert [(r["repeat"], r["mode"]) for r in runs_of(out)] == [
        (0, "legacy"), (0, "json_object"), (1, "json_object"), (1, "legacy")]
    assert set(summary["cells"]) == {"negative_target_scope|legacy", "negative_target_scope|json_object"}
    assert summary["runs"] == 4 and summary["requests"] == 8


def test_manifest_records_budget_identity_and_no_secret(probe, core, tmp_path):
    out = tmp_path / "run"
    probe.run(core, {"legacy": scripted(core, "negative_target_scope", [], decisions(0))}, TRANSPORT, out,
              case_ids=("negative_target_scope", "emotion_negative"), repeats=2)
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["max_requests"] == 2 * 2 * 1 * 2
    assert set(manifest["source_sha256"]) == {"negative_target_scope", "emotion_negative"}
    assert len(manifest["core_sha256"]) == 64 and len(manifest["script_sha256"]) == 64


def test_unknown_or_duplicate_case_is_refused_before_any_output(probe, core, tmp_path):
    fake = scripted(core, "negative_target_scope", [], decisions(0))
    for ids in (("no_such_case",), ("negative_target_scope", "negative_target_scope"), ()):
        with pytest.raises(ValueError):
            probe.run(core, {"legacy": fake}, TRANSPORT, tmp_path / "run", case_ids=ids)
        assert not (tmp_path / "run").exists()


def test_existing_output_directory_is_refused(probe, core, tmp_path):
    fake = scripted(core, "negative_target_scope", [], decisions(0))
    with pytest.raises(FileExistsError):
        probe.run(core, {"legacy": fake}, TRANSPORT, tmp_path, case_ids=("negative_target_scope",), repeats=1)


def test_build_llm_json_object_flag_reaches_transport_and_restores_env(core, monkeypatch):
    base = importlib.import_module("probe_socialmem_negation_scope")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", SECRET)
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/compatible-mode/v1")
    _, transport = base.build_llm(core, "probe-model", json_object=True)
    assert transport["json_object_output"] is True
    _, transport = base.build_llm(core, "probe-model")
    assert transport["json_object_output"] is False
    assert SECRET not in json.dumps(transport)
    assert "OPENAI_API_KEY" not in os.environ and "OPENAI_BASE_URL" not in os.environ


def test_resolve_case_ids_expands_all_to_every_synthetic_case(probe):
    ids = probe.resolve_case_ids(["all"])
    assert len(ids) == 16 and len(set(ids)) == 16 and "negative_target_scope" in ids
    assert probe.resolve_case_ids(["negative_target_scope", "emotion_negative"]) == (
        "negative_target_scope", "emotion_negative")


def test_historical_profile_reproduces_the_recorded_transport_and_default_is_unchanged(probe, core, monkeypatch):
    base = importlib.import_module("probe_socialmem_negation_scope")
    monkeypatch.setenv("DASHSCOPE_API_KEY", SECRET)
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/compatible-mode/v1")
    _, old = base.build_llm(core, "deepseek-v3", json_object=True, **probe.PROFILES["deepseek-2026-09-12"])
    assert (old["max_tokens"], old["timeout_ms"], old["max_retries"]) == (4096, 60000, 3)
    assert old["enable_thinking"] is None and old["json_object_output"] is True
    _, default = base.build_llm(core, "qwen3.8-27b", **probe.PROFILES["default"])
    assert (default["max_tokens"], default["timeout_ms"], default["max_retries"]) == (8192, 120000, 0)
    assert default["enable_thinking"] is False and default["json_object_output"] is False
    assert SECRET not in json.dumps([old, default])


def test_manifest_records_the_profile_and_states_that_transport_retries_follow_the_transport(probe, core, tmp_path):
    out = tmp_path / "run"
    probe.run(core, {"legacy": scripted(core, "negative_target_scope", [], decisions(0))}, TRANSPORT, out,
              case_ids=("negative_target_scope",), repeats=1, profile="deepseek-2026-09-12")
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["profile"] == "deepseek-2026-09-12"
    assert "no content retries" in manifest["protocol"] and "transport retries follow" in manifest["protocol"]
