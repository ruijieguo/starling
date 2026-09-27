"""防止单变量对照混入配置变化、保留题和非冻结实现。"""
import importlib.util
import json
from pathlib import Path

import pytest
from socialmem_fixtures import source_config

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "build/socialmem_20260917_baseline_recovered"


def module():
    path = ROOT / "scripts/run_socialmem_k30_controlled.py"
    assert path.is_file(), "k30 controlled entry missing"
    spec = importlib.util.spec_from_file_location("k30_controlled", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def configs():
    parent = source_config('baseline')
    return parent, {**parent, "k": 30, "http_budget": 1314}


def selection():
    records = [json.loads(line) for line in (BASE / "corpus.jsonl").read_text().splitlines()]
    split = json.loads((BASE / "network-split.json").read_text())
    return records, split


def test_only_k_and_request_budget_can_change():
    module().validate_config(*configs())


@pytest.mark.parametrize("field,value", [
    ("answer_model", "other"), ("k", 60), ("http_budget", 1315),
    ("max_context_bytes", 12000), ("answer_enable_thinking", None),
    ("judge_enable_thinking", False), ("max_retries", 1),
    ("include_unknown_time", 1), ("core_sha256", "a" * 64),
    ("scoring", "relaxed"), ("query_time", "2027-01-01T00:00:00Z"),
])
def test_rejects_uncontrolled_configuration_before_requests(field, value):
    parent, candidate = configs()
    candidate[field] = value
    with pytest.raises(ValueError):
        module().validate_config(parent, candidate)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_selects_all_development_questions_without_reserved_networks():
    records, split = selection()
    selected = module().select_records(records, split)
    assert len(selected) == 733
    assert len({r["item_id"] for r in selected}) == 733
    assert {r["source"]["network_id"] for r in selected}.isdisjoint(split["reserved_networks"])
    assert sum(r["answer_format"] == "multiple_choice" for r in selected) == 152


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_missing_development_question_is_not_silently_dropped():
    records, split = selection()
    lost = next(r for r in records if r["source"]["network_id"] in split["development_networks"])
    with pytest.raises(ValueError):
        module().select_records([r for r in records if r is not lost], split)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_duplicate_question_is_rejected():
    records, split = selection()
    with pytest.raises(ValueError):
        module().select_records(records + [records[0]], split)


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_overlapping_split_is_rejected():
    records, split = selection()
    split["development_networks"][0] = split["reserved_networks"][0]
    with pytest.raises(ValueError):
        module().select_records(records, split)


def test_frozen_code_must_be_identical_including_prompts():
    old = {"frozen_files": {"scripts/eval_ladder.py": "prompt", "native.so": "core"}}
    module().validate_code_delta(old, old)
    for files in [{"scripts/eval_ladder.py": "changed", "native.so": "core"},
                  {"scripts/eval_ladder.py": "prompt"},
                  {**old["frozen_files"], "unreviewed.py": "new"}]:
        with pytest.raises(ValueError):
            module().validate_code_delta(old, {"frozen_files": files})


def test_file_hash_drift_is_rejected(tmp_path):
    m = module()
    p = tmp_path / "input.txt"
    p.write_text("frozen")
    files = {"input.txt": m.sha(p)}
    m.verify_files(tmp_path, files)
    p.write_text("changed")
    with pytest.raises(ValueError):
        m.verify_files(tmp_path, files)


@pytest.mark.parametrize("name", ["../outside", "/tmp/outside"])
def test_manifest_cannot_reference_outside_archive(tmp_path, name):
    with pytest.raises(ValueError):
        module().verify_files(tmp_path, {name: "0" * 64})


def test_missing_scope_snapshot_prohibits_extraction_fallback(tmp_path):
    plan = {"scope_ids": ["example"], "files": {}}
    with pytest.raises(ValueError):
        module().verify_manifest(tmp_path, plan)
