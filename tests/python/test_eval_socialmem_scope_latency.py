"""S/T experimental orchestration keeps native transport and frozen identities."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
from pathlib import Path
import sys
from threading import Thread
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
A_RUN = ROOT / "build/socialmem_20260914_protocol_recovery_a_real"


@pytest.fixture
def modules():
    return (importlib.import_module("eval_socialmem_scope_latency"),
            importlib.import_module("run_socialmem_scope_latency"))


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_scope_selection_uses_native_errors_and_nearest_clean_same_track(modules):
    from starling import _core

    worker, _ = modules
    selected = worker.select_scope_sources(
        _core, A_RUN / "inputs.json", A_RUN / "extraction_calls.jsonl")
    assert [(pair["target"]["id"], pair["control"]["id"]) for pair in selected] == [
        ("eval-002", "eval-004"),
        ("eval-008", "eval-027"),
        ("eval-012", "eval-007"),
        ("eval-015", "eval-037"),
        ("eval-018", "eval-005"),
        ("eval-029", "eval-038"),
        ("Q9_a0b1c2d3_Yuki", "Q1_a5s1c1_Claudette"),
    ]
    assert all(pair["target"]["track"] == pair["control"]["track"] for pair in selected)
    assert len({pair["control"]["id"] for pair in selected}) == 7
    controls = {pair["control"]["id"]: pair["control"] for pair in selected}
    assert controls["eval-007"]["native_errors"] == []
    assert controls["eval-038"]["native_errors"] == []
    assert controls["eval-007"]["native_semantic_rejections"]
    assert controls["eval-038"]["native_semantic_rejections"]


@pytest.mark.historical_eval(reason='固定封存语料、数据库或原生构建；见 tests/README.md 的历史回放说明')
def test_timeout_sources_and_paired_schedules_are_fixed_and_alternate(modules, tmp_path):
    worker, runner = modules
    sources = worker.select_timeout_sources(
        A_RUN / "inputs.json", A_RUN / "extraction_calls.jsonl")
    assert [source["id"] for source in sources] == [
        "eval-028", "eval-022", "eval-009", "eval-036",
        "eval-025", "eval-038", "eval-044", "eval-048",
        "Q1_a5s1c1_Femi", "Q9_a0b1c2d3_Yuki",
        "Q9_a0b1c2d3_Marcus", "Q1_a5s1c1_Claudette",
    ]
    assert [source["historical_call"]["ok"] for source in sources] == [False, True] * 6
    assert [source["historical_call"]["error"] for source in sources] == [
        value for _ in range(6)
        for value in ("transport_error:Timeout was reached", "")]
    altered_calls = []
    for line in (A_RUN / "extraction_calls.jsonl").read_text().splitlines():
        call = json.loads(line)
        if call["id"] == "eval-028":
            call["error"] = "transport_error:authentication failed"
        altered_calls.append(json.dumps(call))
    altered_path = tmp_path / "calls.jsonl"
    altered_path.write_text("\n".join(altered_calls) + "\n")
    with pytest.raises(ValueError, match="timeout identity"):
        worker.select_timeout_sources(A_RUN / "inputs.json", altered_path)
    t_schedule = runner.paired_schedule("T", sources, ("T60", "T120"))
    assert len(t_schedule) == 24
    assert [entry["arm"] for entry in t_schedule[:6]] == [
        "T60", "T120", "T120", "T60", "T60", "T120"]
    assert all(t_schedule[index]["id"] == t_schedule[index + 1]["id"]
               for index in range(0, len(t_schedule), 2))

    scope_pairs = [{"target": {"id": f"bad-{i}", "track": "p1", "passage": "x", "holder": "h"},
                    "control": {"id": f"ok-{i}", "track": "p1", "passage": "y", "holder": "h"}}
                   for i in range(7)]
    s_schedule = runner.scope_schedule(scope_pairs, ("S0", "S1"))
    assert len(s_schedule) == 28
    assert sum(entry["arm"] == "S0" for entry in s_schedule) == 14
    assert sum(entry["arm"] == "S1" for entry in s_schedule) == 14


def _report(created_at: datetime, *, ready: bool = True):
    states = "observed_conformant" if ready else "unsupported"
    return {"created_at": created_at.isoformat(), "capabilities": [
        {"output_mode": "json_schema_strict", "output_contract": kind,
         "state": states, "observed_at": created_at.isoformat(), "error": ""}
        for kind in ("claim_extraction_v2", "claim_admission_v1")
    ]}


def _frozen_arm(tmp_path: Path, name: str, now: datetime):
    report_path = tmp_path / f"{name}-report.json"
    report_path.write_text(json.dumps(_report(now)))
    config = {"endpoint": "https://provider.test/v1", "model": "qwen3.7-plus",
              "timeout_ms": 60000, "max_tokens": 4096, "max_retries": 0,
              "temperature": 0, "output_mode": "json_schema_strict"}
    return {"arm": name, "config": config, "config_sha256": "",
            "core_sha256": "a" * 64, "schema_sha256": "b" * 64,
            "report": str(report_path), "report_sha256": "", "created_at": now.isoformat()}


def test_uniform_start_gate_rejects_drift_failure_and_expiry_before_extract(modules, tmp_path):
    _, runner = modules
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    arms = [_frozen_arm(tmp_path, "T60", now), _frozen_arm(tmp_path, "T120", now)]
    runner.seal_arm_manifest(arms[0])
    runner.seal_arm_manifest(arms[1])
    calls = []

    def validate(arm, started_at):
        calls.append(("validate", arm["arm"], started_at))
        return {"ready": True, "reasons": []}

    def extract(_arm, entry):
        calls.append(("extract", entry["arm"], entry["id"]))
        return {"ok": False, "error": "fixture failure"}

    schedule = runner.paired_schedule(
        "T", [{"id": f"source-{index}"} for index in range(12)], ("T60", "T120"))
    results = runner.execute_frozen_schedule(arms, schedule, validate=validate, extract=extract,
                                             started_at=now, extraction_budget=24)
    assert len(results) == 24
    assert len([call for call in calls if call[0] == "extract"]) == 24

    calls.clear()
    drifted = json.loads(json.dumps(arms))
    drifted[1]["config"]["timeout_ms"] = 120001
    with pytest.raises(ValueError, match="config.*drift"):
        runner.execute_frozen_schedule(drifted, schedule, validate=validate, extract=extract,
                                       started_at=now, extraction_budget=24)
    assert calls == []

    for key, value in (("max_tokens", 2048), ("output_mode", "json_object")):
        altered = json.loads(json.dumps(arms))
        altered[1]["config"][key] = value
        with pytest.raises(ValueError, match="drift"):
            runner.execute_frozen_schedule(altered, schedule, validate=validate, extract=extract,
                                           started_at=now, extraction_budget=24)
    for key in ("core_sha256", "schema_sha256"):
        altered = json.loads(json.dumps(arms))
        altered[1][key] = "c" * 64
        with pytest.raises(ValueError, match="drift"):
            runner.execute_frozen_schedule(altered, schedule, validate=validate, extract=extract,
                                           started_at=now, extraction_budget=24)
    altered = json.loads(json.dumps(arms))
    altered[1]["report_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="report drift"):
        runner.execute_frozen_schedule(altered, schedule, validate=validate, extract=extract,
                                       started_at=now, extraction_budget=24)

    calls.clear()
    with pytest.raises(ValueError, match="capability"):
        runner.execute_frozen_schedule(arms, schedule,
            validate=lambda arm, at: {"ready": arm["arm"] != "T120", "reasons": ["unsupported"]},
            extract=extract, started_at=now, extraction_budget=24)
    assert not [call for call in calls if call[0] == "extract"]

    calls.clear()
    with pytest.raises(ValueError, match="expired"):
        runner.execute_frozen_schedule(arms, schedule,
            validate=lambda _arm, _at: {"ready": False, "reasons": ["capability_report_expired"]},
            extract=extract, started_at=now + timedelta(minutes=11), extraction_budget=24)
    assert not calls


def test_budget_is_exact_and_failed_actions_are_never_retried(modules, tmp_path):
    _, runner = modules
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    arms = [_frozen_arm(tmp_path, "S0", now), _frozen_arm(tmp_path, "S1", now)]
    for arm in arms:
        runner.seal_arm_manifest(arm)
    schedule = runner.paired_schedule("S", [{"id": f"c{i}"} for i in range(14)], ("S0", "S1"))
    attempts = []
    with pytest.raises(ValueError, match="budget"):
        runner.execute_frozen_schedule(arms, schedule,
            validate=lambda _arm, _at: {"ready": True, "reasons": []},
            extract=lambda arm, entry: attempts.append((arm["arm"], entry["id"])),
            started_at=now, extraction_budget=27)
    assert attempts == []

    results = runner.execute_frozen_schedule(arms, schedule,
        validate=lambda _arm, _at: {"ready": True, "reasons": []},
        extract=lambda arm, entry: attempts.append((arm["arm"], entry["id"])) or
                                   {"ok": False, "error": "timeout"},
        started_at=now, extraction_budget=28)
    assert len(results) == len(attempts) == 28
    assert len(set(attempts)) == 28


@pytest.fixture
def delayed_native_service(monkeypatch):
    from starling import _core

    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append({"headers": dict(self.headers), "body": json.loads(body)})
            time.sleep(0.12)
            raw = '{"schema_version":2,"statements":[]}'
            response = json.dumps({"choices": [{"finish_reason": "stop",
                "message": {"content": raw}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            try:
                self.wfile.write(response)
            except BrokenPipeError:
                pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("loopback listener not permitted")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("OPENAI_API_KEY", "local-only-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    try:
        yield _core, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_native_timeout_passthrough_receipt_and_request_capture(modules, delayed_native_service):
    worker, _ = modules
    core, requests = delayed_native_service
    case = {"id": "local", "track": "fixture", "holder": "Nora",
            "passage": "Nora: I feel cheerful about the community picnic."}

    short_llm, short_config = worker.build_native_adapter(core, model="local-model", timeout_ms=30)
    short = worker.extract_once(core, short_llm, short_config, case)
    long_llm, long_config = worker.build_native_adapter(core, model="local-model", timeout_ms=1000)
    long = worker.extract_once(core, long_llm, long_config, case)

    assert short["ok"] is False
    assert short["native"]["attempt_count"] == 1
    assert short["raw_response"] is None
    assert short["completion_tokens"] is None
    assert long["ok"] is True
    assert long["native"]["attempt_count"] == 1
    assert long["raw_response"] == '{"schema_version":2,"statements":[]}'
    assert len(requests) == 2
    assert [request["body"]["model"] for request in requests] == ["local-model", "local-model"]
    assert all(request["body"]["max_tokens"] == 4096 for request in requests)
    assert all(request["body"]["temperature"] == 0 for request in requests)
    captured = worker.sanitize_captured_request(requests[-1])
    assert not any(key.lower() == "authorization" for key in captured["headers"])
    assert "response_format" in captured["body"]
    changed = worker.sanitize_captured_request({
        "headers": requests[-1]["headers"],
        "body": {**requests[-1]["body"], "model": "different-model"}})
    assert len(captured["body_sha256"]) == 64
    assert changed["body_sha256"] != captured["body_sha256"]
    path_changed = worker.sanitize_captured_request({
        "path": "/different", "headers": requests[-1]["headers"],
        "body": requests[-1]["body"]})
    method_changed = worker.sanitize_captured_request({
        "method": "PUT", "path": captured["path"],
        "headers": requests[-1]["headers"], "body": requests[-1]["body"]})
    assert len(captured["request_sha256"]) == 64
    assert path_changed["body_sha256"] == captured["body_sha256"]
    assert path_changed["request_sha256"] != captured["request_sha256"]
    assert method_changed["body_sha256"] == captured["body_sha256"]
    assert method_changed["request_sha256"] != captured["request_sha256"]
    assert short_config["timeout_ms"] == 30 and long_config["timeout_ms"] == 1000
    assert short_config["max_retries"] == long_config["max_retries"] == 0


def test_preview_capture_preserves_intended_endpoint_path(modules):
    from starling import _core

    worker, _ = modules
    case = {"id": "local", "track": "fixture", "holder": "Nora",
            "passage": "Nora: I feel cheerful about the community picnic."}
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    preview = worker.capture_preview(
        _core, [case], model="local-model", timeout_ms=1000,
        intended_endpoint=endpoint, include_probe=False)

    assert preview["config"]["endpoint"] == endpoint
    assert preview["capture_config"]["endpoint"].endswith("/compatible-mode/v1")
    assert [request["path"] for request in preview["requests"]] == [
        "/compatible-mode/v1/chat/completions"]


def test_worker_stage_command_is_python_isolated_and_explicit(modules, tmp_path):
    _, runner = modules
    stage = tmp_path / "stage"
    (stage / "python" / "starling").mkdir(parents=True)
    command = runner.worker_command(Path("/python"), Path("/worker.py"), stage,
                                    "inspect", Path("/result.json"))
    assert command[:4] == ["/python", "-S", "/worker.py", "inspect"]
    assert command[4:] == ["--stage", str(stage.resolve()), "--out", "/result.json"]


def test_preview_pair_enforces_only_the_intended_experimental_variable(modules):
    _, runner = modules
    base_config = {"endpoint": "https://provider.test/v1", "model": "qwen3.7-plus",
                   "timeout_ms": 60000, "max_tokens": 4096, "max_retries": 0,
                   "temperature": 0, "output_mode": "json_schema_strict"}

    def preview(core_hash, config, prompt):
        return {"identity": {"core_sha256": core_hash, "schema_sha256": "s" * 64},
                "config": config, "requests": [{"method": "POST", "path": "/v1/chat/completions",
                    "headers": {}, "body": {
                    "model": "qwen3.7-plus", "max_tokens": 4096, "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_schema"}}}]}

    t60 = preview("a" * 64, dict(base_config), "same")
    t120 = preview("a" * 64, dict(base_config, timeout_ms=120000), "same")
    assert runner.verify_preview_pair("T", t60, t120)
    changed_request = json.loads(json.dumps(t120))
    changed_request["requests"][0]["body"]["max_tokens"] = 2048
    with pytest.raises(ValueError, match="request"):
        runner.verify_preview_pair("T", t60, changed_request)

    s0 = preview("a" * 64, dict(base_config), "old native prompt")
    s1 = preview("b" * 64, dict(base_config), "new native prompt")
    assert runner.verify_preview_pair("S", s0, s1)
    changed_config = json.loads(json.dumps(s1))
    changed_config["config"]["timeout_ms"] = 120000
    with pytest.raises(ValueError, match="config"):
        runner.verify_preview_pair("S", s0, changed_config)

    for experiment, left, right in (("S", s0, s1), ("T", t60, t120)):
        for key, changed_value in (("method", "PUT"), ("path", "/other/chat/completions")):
            changed_target = json.loads(json.dumps(right))
            changed_target["requests"][0][key] = changed_value
            with pytest.raises(ValueError, match="method/path"):
                runner.verify_preview_pair(experiment, left, changed_target)


def test_all_frozen_identities_are_preflighted_before_any_probe(modules):
    _, runner = modules
    arms = [
        {"name": "T60", "config": {"timeout_ms": 60000},
         "identity": {"core_sha256": "a" * 64, "worker_sha256": "w" * 64,
                      "probe_helper_sha256": "p" * 64},
         "request_sha256s": ["r" * 64]},
        {"name": "T120", "config": {"timeout_ms": 120000},
         "identity": {"core_sha256": "a" * 64, "worker_sha256": "w" * 64,
                      "probe_helper_sha256": "p" * 64},
         "request_sha256s": ["r" * 64]},
    ]
    probes = []

    def unchanged(arm):
        return {"config": arm["config"], "identity": arm["identity"],
                "request_sha256s": arm["request_sha256s"]}

    result = runner.preflight_then_probe(
        arms, preflight=unchanged,
        probe=lambda arm: probes.append(arm["name"]) or {"arm": arm["name"], "ready": True},
        probe_ready=lambda result: result["ready"])
    assert [item["arm"] for item in result] == ["T60", "T120"]
    assert probes == ["T60", "T120"]

    for section, key, value in (
            ("config", "timeout_ms", 120001),
            ("identity", "core_sha256", "b" * 64),
            ("identity", "worker_sha256", "x" * 64),
            ("identity", "probe_helper_sha256", "q" * 64),
            (None, "request_sha256s", ["z" * 64])):
        probes.clear()

        def drifted(arm, section=section, key=key, value=value):
            snapshot = json.loads(json.dumps(unchanged(arm)))
            if arm["name"] == "T120":
                if section is None:
                    snapshot[key] = value
                else:
                    snapshot[section][key] = value
            return snapshot

        with pytest.raises(ValueError, match="preflight.*drift"):
            runner.preflight_then_probe(
                arms, preflight=drifted,
                probe=lambda arm: probes.append(arm["name"]),
                probe_ready=lambda _result: True)
        assert probes == []

    probes.clear()
    with pytest.raises(ValueError, match="capability"):
        runner.preflight_then_probe(
            arms, preflight=unchanged,
            probe=lambda arm: probes.append(arm["name"]) or
                              {"arm": arm["name"], "ready": False},
            probe_ready=lambda result: result["ready"])
    assert probes == ["T60"]


def test_runtime_shape_rejects_underbudget_or_non_alternating_plan(modules):
    _, runner = modules
    sources = [{"id": f"source-{i}", "track": "fixture", "holder": "h",
                "passage": "p", "source_sha256": f"{i:064x}"} for i in range(12)]
    schedule = runner.paired_schedule("T", sources, ("T60", "T120"))
    plan = {"experiment": "T", "extraction_budget": 24,
            "arms": [{"name": "T60", "timeout_ms": 60000},
                     {"name": "T120", "timeout_ms": 120000}],
            "schedule": schedule}
    assert runner.verify_experiment_shape(plan)
    underbudget = json.loads(json.dumps(plan))
    underbudget["schedule"] = underbudget["schedule"][:-2]
    underbudget["extraction_budget"] = 22
    with pytest.raises(ValueError, match="budget"):
        runner.verify_experiment_shape(underbudget)
    wrong_order = json.loads(json.dumps(plan))
    wrong_order["schedule"][2]["arm"], wrong_order["schedule"][3]["arm"] = (
        wrong_order["schedule"][3]["arm"], wrong_order["schedule"][2]["arm"])
    with pytest.raises(ValueError, match="alternat"):
        runner.verify_experiment_shape(wrong_order)

    duplicate_arm = json.loads(json.dumps(plan))
    duplicate_arm["arms"].append(json.loads(json.dumps(duplicate_arm["arms"][1])))
    with pytest.raises(ValueError, match="arm.*mapping"):
        runner.verify_experiment_shape(duplicate_arm)

    reversed_arms = json.loads(json.dumps(plan))
    reversed_arms["arms"].reverse()
    with pytest.raises(ValueError, match="arm.*mapping"):
        runner.verify_experiment_shape(reversed_arms)
