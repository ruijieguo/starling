"""能力回执只由 C++ 产生；Python 验证归档身份和实验调度。"""
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def test_invalid_native_config_creates_blocked_archive_without_cohort_calls(monkeypatch, tmp_path):
    from starling import _core

    probe = importlib.import_module("probe_socialmem_output_capability")
    evaluation = importlib.import_module("eval_socialmem_claim_contract")
    monkeypatch.setenv("OPENAI_API_KEY", "never-archive-this-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    cfg = _core.OpenAIAdapterConfig.from_env()
    cfg.timeout_ms = -1
    cfg.model = "probe-fixture"
    llm = _core.OpenAIAdapter(cfg)
    transport = {"endpoint": cfg.base_url, "model": cfg.model}
    report = probe.collect_report(_core, llm, transport)
    assert len(report["capabilities"]) == 4
    assert report["request_count"] == 0
    assert {v["state"] for v in report["capabilities"]} == {"unknown"}
    assert "never-archive-this-secret" not in json.dumps(report)
    assert probe.check_report(_core, report, transport, "json_schema_strict")["ready"] is False
    out = tmp_path / "blocked"
    result = evaluation.run(tmp_path / "absent-parent", out, _core, llm, None, None,
        transport, "unused", output_mode="json_schema_strict", capability_report=report)
    assert result["quality"] is None
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    assert verifier.verify(out)["run_status"] == "capability_blocked"
    altered = json.loads(json.dumps(report))
    altered["capabilities"][0]["state"] = "observed_conformant"
    with pytest.raises(ValueError, match="capability|evidence"):
        probe.check_report(_core, altered, transport, "json_schema_strict")
    altered = json.loads(json.dumps(report))
    altered["schemas"]["claim_extraction_v2"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="schema"):
        probe.check_report(_core, altered, transport, "json_schema_strict")


@pytest.fixture
def conformant_service(monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from starling import _core

    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            schema_name = body.get("response_format", {}).get("json_schema", {}).get("name", "")
            admission = schema_name == "claim_admission_v1" or "the candidate list is empty" in body["messages"][0]["content"]
            raw = '{"schema_version":1,"decisions":[]}' if admission else '{"schema_version":2,"statements":[]}'
            response = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": raw}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("loopback listener not permitted")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("OPENAI_API_KEY", "local-fixture")
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    cfg = _core.OpenAIAdapterConfig.from_env()
    cfg.model = "local-capability-fixture"
    cfg.max_retries = 3
    cfg.timeout_ms = 1000
    try:
        yield _core, _core.OpenAIAdapter(cfg), {"endpoint": cfg.base_url, "model": cfg.model,
                                               "max_retries": cfg.max_retries}, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_positive_report_checks_native_evidence_and_expiry_without_reprobing(conformant_service):
    from datetime import datetime, timedelta

    core, llm, transport, requests = conformant_service
    probe = importlib.import_module("probe_socialmem_output_capability")
    report = probe.collect_report(core, llm, transport)
    assert len(requests) == report["request_count"] == 8
    assert probe.check_report(core, report, transport, "json_schema_strict")["ready"]
    late = datetime.fromisoformat(report["created_at"]) + timedelta(minutes=11)
    assert not probe.check_report(core, report, transport, "json_schema_strict", at=late)["ready"]
    assert len(requests) == 8
    altered = json.loads(json.dumps(report))
    altered["capabilities"][2]["probes"][0]["response"]["raw_completion"] += " trailing explanation"
    with pytest.raises(ValueError, match="capability"):
        probe.check_report(core, altered, transport, "json_schema_strict")


@pytest.mark.parametrize("use_cli", [False, True])
def test_selected_model_reaches_native_http_and_capability_archive(conformant_service, monkeypatch, tmp_path, use_cli):
    from types import SimpleNamespace

    core, _llm, local_transport, requests = conformant_service
    extraction = importlib.import_module("eval_socialmem_extraction")
    probe = importlib.import_module("probe_socialmem_output_capability")
    original_build = extraction.build_llm
    monkeypatch.setenv("DASHSCOPE_API_KEY", "local-fixture")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://fixture.invalid/v1")

    def local_config():
        config = core.OpenAIAdapterConfig.from_env()
        config.base_url = local_transport["endpoint"]
        config.timeout_ms = 1000
        return config

    # Only route transport to the local server; construction, model selection,
    # request serialization, schema checks and report generation remain real.
    routed = SimpleNamespace(OpenAIAdapterConfig=SimpleNamespace(from_env=local_config),
                             OpenAIAdapter=core.OpenAIAdapter)
    if use_cli:
        monkeypatch.setattr(extraction, "build_llm", lambda _core, **kwargs: original_build(routed, **kwargs))
        path = tmp_path / "capability.json"
        monkeypatch.setattr(sys, "argv", ["probe", "--model", "qwen3.7-plus", "--out", str(path)])
        probe.main()
        report = json.loads(path.read_text())
    else:
        llm, transport = original_build(routed, model="qwen3.7-plus")
        report = probe.collect_report(core, llm, transport)
    assert len(requests) == report["request_count"] == 8
    assert {body["model"] for body in requests} == {"qwen3.7-plus"}
    assert report["transport"]["model"] == "qwen3.7-plus"
    assert probe.check_report(core, report, report["transport"], "json_schema_strict")["ready"]


@pytest.mark.parametrize("model", ["", "   ", "\n"])
def test_empty_model_is_rejected_before_native_construction(monkeypatch, model):
    extraction = importlib.import_module("eval_socialmem_extraction")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "local-fixture")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://fixture.invalid/v1")
    with pytest.raises(ValueError, match="model"):
        extraction.build_llm(None, model=model)
