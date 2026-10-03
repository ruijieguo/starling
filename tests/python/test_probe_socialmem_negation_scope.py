"""否定范围探针：离线夹具验证标签绑定、打分边界、失败口径与密钥不落盘；不请求外部模型。"""
import importlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

TRANSPORT = {"endpoint": "fixture", "model": "fixture"}
SECRET = "never-archive-this-secret"


@pytest.fixture
def probe():
    return importlib.import_module("probe_socialmem_negation_scope")


def row(holder, subject, obj, polarity, predicate="prefers", modality="DESIRES"):
    return {"holder": holder, "holder_perspective": "FIRST_PERSON", "subject": subject,
            "subject_kind": "cognizer", "cognizer_kind": "human", "predicate": predicate,
            "object": obj, "modality": modality, "polarity": polarity, "nesting_depth": 0}


FAITHFUL = {
    "negative_target_scope": [row("Dana", "Dana", "no downtime", "NEG")],
    "preference_contrast": [row("Mateo", "Mateo", "green room", "NEG"),
                            row("Mateo", "Mateo", "red room", "POS")],
}


def scripted(core, probe, responses):
    """按各用例的真实渲染提示哈希预置原生 fake 响应。"""
    import eval_socialmem_predicates as pred
    from starling.extractor.prompts import EXTRACTION_PROMPT

    fake = core.FakeLLMAdapter()
    _, sources = probe.load_labels()
    for name, rows in responses.items():
        source = sources[name]
        prompt = pred.render_prompts({"belief": EXTRACTION_PROMPT}, source["holder"], source["passage"])["belief"]
        fake.set_response(core.Extractor.compute_prompt_input_hash(prompt), json.dumps(rows))
    return fake


def test_labels_bind_to_source_text(probe):
    labels, sources = probe.load_labels()
    assert [c["id"] for c in labels["cases"]] == ["negative_target_scope", "preference_contrast"]
    assert sum(len(c["targets"]) for c in labels["cases"]) == 3
    assert set(c["id"] for c in labels["cases"]) <= set(sources)


def test_tampered_label_source_hash_is_rejected(probe, tmp_path):
    labels = json.loads(probe.LABEL_PATH.read_text())
    labels["cases"][0]["source_sha256"] = "0" * 64
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(labels))
    with pytest.raises(ValueError, match="drifted"):
        probe.load_labels(path)


def test_faithful_extraction_covers_every_target_in_every_repeat(probe, core, tmp_path):
    out = tmp_path / "run"
    summary = probe.run(core, scripted(core, probe, FAITHFUL), TRANSPORT, out, repeats=2)
    assert summary["strict"] == {"targets": 6, "valid": 6, "covered": 6}
    assert all(c["technical_failures"] == 0 and c["unmatched_rows"] == 0 for c in summary["cases"].values())
    assert json.loads((out / "manifest.json").read_text())["status"] == "complete"
    assert len((out / "runs.jsonl").read_text().splitlines()) == 4
    assert len(list((out / "databases").glob("*.db"))) == 4


@pytest.mark.parametrize("wrong", [
    row("Dana", "Dana", "no downtime", "POS"),
    row("Dana", "Dana", "downtime", "NEG"),
], ids=["polarity_flipped", "negation_moved_off_target"])
def test_wrong_polarity_or_scope_is_not_covered(probe, core, tmp_path, wrong):
    responses = {**FAITHFUL, "negative_target_scope": [wrong]}
    summary = probe.run(core, scripted(core, probe, responses), TRANSPORT, tmp_path / "run", repeats=1)
    target = summary["cases"]["negative_target_scope"]["targets"][0]
    assert target["valid"] == 1 and target["covered"] == 0
    assert summary["cases"]["preference_contrast"]["targets"][1]["covered"] == 1


def test_one_row_cannot_cover_two_targets(probe, core, tmp_path):
    responses = {**FAITHFUL, "preference_contrast": [row("Mateo", "Mateo", "green room", "NEG")]}
    summary = probe.run(core, scripted(core, probe, responses), TRANSPORT, tmp_path / "run", repeats=1)
    covered = [t["covered"] for t in summary["cases"]["preference_contrast"]["targets"]]
    assert covered == [1, 0]


def test_transport_failure_stays_in_strict_denominator_and_leaks_no_secret(probe, core, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    cfg = core.OpenAIAdapterConfig.from_env()
    cfg.timeout_ms = -1
    cfg.model = "probe-fixture"
    out = tmp_path / "run"
    summary = probe.run(core, core.OpenAIAdapter(cfg), {"endpoint": cfg.base_url, "model": cfg.model}, out, repeats=1)
    assert summary["strict"] == {"targets": 3, "valid": 0, "covered": 0}
    assert all(c["technical_failures"] == 1 for c in summary["cases"].values())
    for path in out.rglob("*"):
        if path.is_file() and path.suffix != ".db":
            assert SECRET not in path.read_text()


def test_existing_output_directory_is_refused(probe, core, tmp_path):
    with pytest.raises(FileExistsError):
        probe.run(core, scripted(core, probe, FAITHFUL), TRANSPORT, tmp_path, repeats=1)


def test_build_llm_demands_explicit_https_env_and_restores_openai_env(probe, core, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", SECRET)
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/compatible-mode/v1")
    _, transport = probe.build_llm(core, "probe-model")
    assert transport["model"] == "probe-model"
    assert transport["endpoint"] == "https://example.test/compatible-mode/v1"
    assert SECRET not in json.dumps(transport)
    assert "OPENAI_API_KEY" not in os.environ and "OPENAI_BASE_URL" not in os.environ
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "http://example.test/v1")
    with pytest.raises(ValueError, match="HTTPS"):
        probe.build_llm(core, "probe-model")
    monkeypatch.delenv("DASHSCOPE_API_KEY")
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        probe.build_llm(core, "probe-model")
