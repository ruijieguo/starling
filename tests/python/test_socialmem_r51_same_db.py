"""R5.1 同库 v6/v7 对照的 provenance 与终态合同测试。"""

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_socialmem_r51_same_db.py"


def driver():
    spec = importlib.util.spec_from_file_location("socialmem_r51_same_db", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def parent_fixture(tmp_path: Path):
    parent = tmp_path / "retry4"
    parent.mkdir()
    write_json(parent / "config.json", {"core_sha256": "core", "source_strategy": "evidence_profile_v7"})
    write_json(parent / "identity.json", {
        "core_sha256": "core",
        "config_sha256": "placeholder",
        "scope_manifest_sha256": "placeholder",
        "frozen_files": {},
    })
    write_json(parent / "scope-manifest.json", {"items": [{"item_id": "q1"}]})
    write_json(parent / "sample.json", [{"item_id": "q1"}])
    write_json(parent / "groups.json", [{"group_id": "g1", "records": [{"item_id": "q1"}]}])
    (parent / "source-databases" / "g1").mkdir(parents=True)
    (parent / "source-databases" / "g1" / "frozen.db").write_bytes(b"snapshot")
    return parent


def test_parent_provenance_requires_scope_snapshot_and_hashes(tmp_path):
    d = driver()
    parent = parent_fixture(tmp_path)
    with pytest.raises(ValueError, match="manifest|identity|hash"):
        d.validate_parent(parent)


def test_only_v6_and_v7_are_valid_strategies():
    d = driver()
    assert d.validate_strategy("evidence_profile_v6") == "evidence_profile_v6"
    assert d.validate_strategy("evidence_profile_v7") == "evidence_profile_v7"
    with pytest.raises(ValueError, match="strategy"):
        d.validate_strategy("focused_coverage")


def test_arm_row_binds_strategy_snapshot_and_terminal_state():
    d = driver()
    base = {
        "item_id": "q1",
        "group_id": "g1",
        "strategy": "evidence_profile_v7",
        "database_sha256": "db",
        "core_sha256": "core",
        "status": "ok",
        "terminal": True,
        "recall": {"source_refs": [], "block": "", "diagnostics": {}},
    }
    d.validate_arm_row(base, "evidence_profile_v7", "db", "core")
    with pytest.raises(ValueError, match="strategy"):
        d.validate_arm_row({**base, "strategy": "evidence_profile_v6"}, "evidence_profile_v7", "db", "core")
    with pytest.raises(ValueError, match="terminal"):
        d.validate_arm_row({**base, "terminal": False}, "evidence_profile_v7", "db", "core")


def test_compare_rows_aligns_same_question_and_reports_change():
    d = driver()
    v6 = {"item_id": "q1", "status": "ok", "terminal": True,
          "recall": {"source_refs": [{"engram_ref": "a", "clause_id": "c0"}],
                     "block": "old", "diagnostics": {"selected_by": {"relevance": 1}}}}
    v7 = {"item_id": "q1", "status": "ok", "terminal": True,
          "recall": {"source_refs": [{"engram_ref": "b", "clause_id": "c0"}],
                     "block": "new", "diagnostics": {"selected_by": {"semantic": 1, "event": 1}}}}
    result = d.compare_rows([v6], [v7])
    assert result["questions"] == 1
    assert result["changed_questions"] == 1
    assert result["rows"][0]["source_changed"] is True
    assert result["rows"][0]["block_changed"] is True


def test_compare_rejects_missing_or_duplicate_question():
    d = driver()
    row = {"item_id": "q1", "status": "ok", "terminal": True,
           "recall": {"source_refs": [], "block": "", "diagnostics": {}}}
    with pytest.raises(ValueError, match="question"):
        d.compare_rows([row, row], [row])
    with pytest.raises(ValueError, match="question"):
        d.compare_rows([row], [])
