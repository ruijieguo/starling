"""Offline regression tests for the frozen SocialMemBench baseline runner."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from socialmem_fixtures import source_config


_RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run_socialmem_baseline.py"
_SPEC = importlib.util.spec_from_file_location("run_socialmem_baseline", _RUNNER)
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def _record(item_id: str, *, scope: str = "all", history: list[dict] | None = None) -> dict:
    return {
        "item_id": item_id,
        "network_id": "network-a",
        "evaluation_scope": scope,
        "history": history or [{"speaker": "Ada", "text": "private fact"}],
        "question": "Which private fact?",
        "options": ["private fact", "another fact"],
        "answer": 0,
        "answer_format": "multiple_choice",
        "gold_statements": [{"subject": "Ada", "object": "private fact"}],
        "source": {"reference_answer": "private fact", "correct_option": "A"},
    }


def test_prepare_groups_separates_scopes_and_reuses_matching_history():
    groups = runner.prepare_groups([
        _record("a1", scope="participant-a"),
        _record("a2", scope="participant-a"),
        _record("b1", scope="participant-b"),
    ])

    assert [(group["network_id"], group["evaluation_scope"], len(group["records"]))
            for group in groups] == [
                ("network-a", "participant-a", 2),
                ("network-a", "participant-b", 1),
            ]


def test_prepare_groups_rejects_different_history_in_one_network_scope():
    with pytest.raises(ValueError, match="history mismatch"):
        runner.prepare_groups([
            _record("a1"),
            _record("a2", history=[{"speaker": "Ada", "text": "changed fact"}]),
        ])


def test_ingestion_record_removes_question_answers_and_gold_material():
    sanitized = runner.ingestion_record(_record("a1"))

    assert sanitized == {
        "item_id": "a1",
        "network_id": "network-a",
        "evaluation_scope": "all",
        "history": [{"speaker": "Ada", "text": "private fact"}],
    }


def test_terminal_result_is_skipped_but_started_file_is_incomplete(tmp_path):
    question_dir = tmp_path / "questions"
    question_dir.mkdir()
    (question_dir / "done.json").write_text('{"status":"ok"}\n')
    (question_dir / "crashed.started").write_text('{"item_id":"crashed"}\n')

    states = runner.question_states(question_dir, ["done", "crashed", "new"])

    assert states == {"done": "terminal", "crashed": "incomplete", "new": "pending"}


def test_summarize_keeps_all_records_in_primary_denominator():
    records = [_record("mc"), dict(_record("free"), answer_format="short_answer")]
    summary = runner.summarize(records, [
        {"item_id": "mc", "status": "ok", "correct": True},
        {"item_id": "free", "status": "answer_failure", "correct": False},
    ])

    assert summary["total"] == 2
    assert summary["correct"] == 1
    assert summary["accuracy"] == 0.5
    assert summary["by_format"]["multiple_choice"]["total"] == 1
    assert summary["by_format"]["short_answer"]["failed"] == 1


def test_prepare_groups_rejects_duplicate_item_identity():
    with pytest.raises(ValueError, match="duplicate item_id"):
        runner.prepare_groups([_record("same"), _record("same", scope="other")])


def test_scope_started_marker_is_incomplete_and_carries_fingerprint(tmp_path):
    scope = tmp_path / "scope"
    scope.mkdir()
    fingerprint = {"corpus_sha256": "corpus", "scope_manifest_sha256": "scope"}
    (scope / "scope.started").write_text(json.dumps({"fingerprint": fingerprint}))

    assert runner.scope_state(scope, fingerprint) == "incomplete"
    with pytest.raises(RuntimeError, match="fingerprint"):
        runner.scope_state(scope, {"corpus_sha256": "different"})


def test_response_validation_uses_raw_xml_and_never_judges_failed_answer():
    class Response:
        ok = False
        error = "timeout"
        raw_xml = ""
        raw_completion = "reasoning only"

        @staticmethod
        def to_json():
            return '{"attempt_count":1,"http_attempts":[{"error":"timeout"}]}'

    payload, text, error = runner.response_text(Response(), "answer")

    assert payload["response"]["attempt_count"] == 1
    assert text == ""
    assert error == "answer response not ok: timeout"


def test_budget_ledger_reserves_and_keeps_unknown_crash_reservation(tmp_path):
    ledger = runner.BudgetLedger(tmp_path / "budget.sqlite", 10)
    reservation = ledger.reserve("scope-a", "extract", 7)
    assert reservation["state"] == "reserved"
    assert ledger.reserve("scope-b", "extract", 4)["state"] == "blocked"
    ledger.settle(reservation["id"], 3)
    assert ledger.snapshot()["reserved"] == 0
    stranded = ledger.reserve("scope-c", "embed", 6)
    assert ledger.snapshot()["reserved"] == 6
    assert stranded["state"] == "reserved"


def test_summary_reports_query_type_and_unexecuted_coverage():
    records = [dict(_record("one"), query_type="Q1"),
               dict(_record("two"), query_type="Q2")]
    summary = runner.summarize(records, [{"item_id": "one", "status": "ok", "correct": True}])

    assert summary["coverage"] == 0.5
    assert summary["successful_denominator"] == 1
    assert summary["by_query_type"]["Q2"]["unexecuted"] == 1


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_offline_native_smoke_keeps_frozen_snapshot_unchanged(tmp_path):
    work = Path(__file__).resolve().parents[2] / "build" / "socialmem_20260916_baseline"

    smoke = runner.offline_native_smoke(work, tmp_path)

    assert smoke["frozen_unchanged"] is True
    assert smoke["embedding"]["embedded"] == 1
    assert smoke["result"]["status"] == "ok"
    assert smoke["result"]["correct"] is True
    assert smoke["three_phase_outcomes"][0]["extraction_failed"] is False
    assert smoke["three_phase_database"]["pipeline_run"] >= 2


def test_budget_blocked_is_unexecuted_not_a_system_failure():
    summary = runner.summarize([_record("one")], [
        {"item_id": "one", "status": "budget_blocked", "correct": False}])
    assert summary["executed"] == 0
    assert summary["technical"] == 0
    assert summary["unexecuted"] == 1


def test_external_group_cannot_replace_frozen_history():
    groups = runner.prepare_groups([_record("one")])
    changed = runner.prepare_groups([_record("one", history=[{"speaker": "Ada", "text": "leaked"}])])
    with pytest.raises(ValueError, match="frozen corpus"):
        runner.validate_groups(groups, changed)


def test_unknown_request_is_charged_at_reserved_upper_bound(tmp_path):
    ledger = runner.BudgetLedger(tmp_path / "budget.sqlite", 10)
    reservation = ledger.reserve("scope", "extract", 9)
    ledger.charge_upper(reservation["id"])
    assert ledger.snapshot()["charged_upper"] == 9
    assert ledger.snapshot()["reserved"] == 0
    assert ledger.snapshot()["remaining"] == 1


def test_terminal_scope_missing_snapshot_does_not_restart_ingestion(tmp_path):
    scope = tmp_path / "scope"
    scope.mkdir()
    runner._json_write(scope / "scope.json", {"fingerprint": {"run": "one"}})
    with pytest.raises(RuntimeError, match="snapshot"):
        runner.scope_state(scope, {"run": "one"})


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_baseline_uses_dashscope_for_every_model_role():
    work = Path(__file__).resolve().parents[2] / "build" / "socialmem_20260916_baseline"
    import json
    config = json.loads((work / "config.json").read_text())
    assert config["answer_endpoint"] == config["extract_endpoint"]
    assert config["answer_key_env"] == "DASHSCOPE_API_KEY"
    assert config["answer_model"] == config["extract_model"] == "qwen3.8-27b"


@pytest.mark.parametrize("thinking", ["missing", False, True])
def test_native_thinking_mapping_isolated_to_extractor(thinking):
    # 独立进程避开前面冻结基线smoke载入的旧_core。
    import subprocess
    import sys
    program = r'''
import importlib.util, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
spec = importlib.util.spec_from_file_location("runner", sys.argv[1])
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from starling import _core
assert hasattr(_core.OpenAIAdapterConfig(), "enable_thinking")
requests = []
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        body = b'{"choices":[{"message":{"content":"[]"},"finish_reason":"stop"}]}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    config = json.loads(sys.argv[3]); config["extract_enable_thinking"] = None; config["answer_enable_thinking"] = None
    for role in ("extract", "answer", "embedding"):
        config[role + "_endpoint"] = f"http://127.0.0.1:{server.server_port}/v1"
    os.environ["DASHSCOPE_API_KEY"] = "local-fixture"
    thinking = json.loads(sys.argv[2])
    if thinking != "missing":
        config["extract_enable_thinking"] = thinking
    extractor, _, answerer, judge = runner._make_native_adapters(_core, config)
    assert extractor.extract("Extract JSON", "test").ok
    assert answerer.extract("Answer", "").ok
    assert judge.extract("Judge", "").ok
    assert len(requests) == 3
    if thinking == "missing":
        assert "enable_thinking" not in requests[0]
    else:
        assert requests[0].get("enable_thinking") is thinking, requests[0]
    assert all("enable_thinking" not in request for request in requests[1:])
finally:
    server.shutdown()
    server.server_close()
    thread.join()
'''
    completed = subprocess.run([sys.executable, "-c", program, str(_RUNNER), json.dumps(thinking), json.dumps(source_config())],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
