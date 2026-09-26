"""离线诊断使用真实 SQLite 与逐题回执，禁止扩大或混淆分母。"""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT = Path(__file__).resolve().parents[2]


def analyzer():
    path = ROOT / "scripts/analyze_socialmem_structured_coverage.py"
    assert path.exists(), "missing offline structured coverage analyzer"
    spec = importlib.util.spec_from_file_location("coverage_analyzer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root):
    scope = root / "runs/g"
    write(scope / "scope.json", {"group": "g", "extraction": [{
        "holder": "Arin", "extraction_failed": False, "catalog_version": "claim-predicate-v2",
        "failure_category": "semantic_rejection", "rejected_by_predicate": {"__semantic_rejection__": 2}}]})
    write(scope / "ingestion.json", {"network_id": "n", "evaluation_scope": "all_history",
        "records": [{"history": [{"speaker": "Arin", "text": "I am relieved."}]}]})
    with sqlite3.connect(scope / "frozen.db") as db:
        db.executescript("""
            CREATE TABLE statements(id TEXT, tenant_id TEXT, predicate TEXT, semantic_claim_json TEXT);
            CREATE TABLE extraction_attempt(raw_output TEXT, error TEXT);
        """)
        db.execute("INSERT INTO statements VALUES (?,?,?,?)", ("claim", "default", "feels",
            json.dumps({"semantic_family": "affect", "source_turn": {"speaker": "Arin"}})))
        db.execute("INSERT INTO statements VALUES ('legacy','default','has_property',NULL)")
        db.execute("INSERT INTO extraction_attempt VALUES (NULL,NULL)")
    rows = [
        {"item_id": "one", "terminal": True, "status": "ok", "correct": True,
         "recall": {"statement_ids": ["claim"], "statement_count": 1}},
        {"item_id": "two", "terminal": True, "status": "ok", "correct": False,
         "recall": {"statement_ids": ["legacy"], "statement_count": 1}},
    ]
    for i, row in enumerate(rows):
        write(scope / f"questions/{i}.json", row)
    write(root / "summary.json", {"groups": [{"group": "g", "results": rows}]})
    return root


def test_counts_structured_rows_and_joins_statement_ids_without_guessing_rejections(tmp_path):
    report = analyzer().analyze_run(fixture(tmp_path))
    assert report["external_requests"] == 0
    assert report["totals"]["questions"] == 2
    assert report["totals"]["statements"] == 2
    assert report["totals"]["structured_claims"] == 1
    assert report["totals"]["structured_missing_session"] == 1
    assert report["qa_by_context"]["with_structured"] == {"questions": 1, "correct": 1}
    assert report["qa_by_context"]["legacy_only"] == {"questions": 1, "correct": 0}
    assert report["scopes"][0]["admission_reason_details"] is None
    assert report["scopes"][0]["rejected_by_predicate"] == {"__semantic_rejection__": 2}
    assert report["input_hashes"]


def test_source_only_is_missing_extraction_not_successful_empty(tmp_path):
    root = fixture(tmp_path)
    write(root / "runs/g/scope.json", {"group": "g", "ingestion_mode": "source_only", "extraction": []})
    report = analyzer().analyze_run(root)
    assert report["scopes"][0]["structured_scope_complete"] is False
    assert report["scopes"][0]["missing_holders"] == ["Arin"]


@pytest.mark.parametrize("fault", ["missing_scope", "duplicate_question", "receipt_drift", "wal", "missing_statement", "unreferenced_question"])
def test_rejects_incomplete_or_inconsistent_evidence(tmp_path, fault):
    module = analyzer()
    root = fixture(tmp_path)
    summary = json.loads((root / "summary.json").read_text())
    if fault == "missing_scope":
        (root / "runs/g/scope.json").unlink()
    elif fault == "duplicate_question":
        summary["groups"][0]["results"].append(summary["groups"][0]["results"][0])
        write(root / "summary.json", summary)
    elif fault == "receipt_drift":
        row = summary["groups"][0]["results"][0]
        row["correct"] = False
        write(root / "runs/g/questions/0.json", row)
    elif fault == "wal":
        (root / "runs/g/frozen.db-wal").write_bytes(b"uncheckpointed data")
    elif fault == "unreferenced_question":
        write(root / "runs/g/questions/extra.json", {"item_id": "extra"})
    else:
        with sqlite3.connect(root / "runs/g/frozen.db") as db:
            db.execute("DELETE FROM statements WHERE id='claim'")
    with pytest.raises(ValueError):
        module.analyze_run(root)
