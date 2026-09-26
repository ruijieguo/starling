"""Persistent request-budget and frozen-identity guard contracts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import multiprocessing
from pathlib import Path
import sys
from threading import Thread

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _reserve_in_process(path, request_id, queue):
    guard = importlib.import_module("socialmem_run_guard")
    try:
        ledger = guard.RequestLedger(path, "race-run")
        ledger.reserve("C0", "extract", request_id)
        queue.put(True)
    except ValueError:
        queue.put(False)


def _case(**changes):
    return {"id": "case-1", "track": "scoped", "holder": "Mina",
            "passage": "Mina: I am worried about the launch.", **changes}


def _canonical_source(case):
    value = {key: case[key] for key in ("id", "track", "holder", "passage")}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def test_ledger_reserves_once_enforces_phase_budget_and_preserves_rejections(tmp_path):
    guard = importlib.import_module("socialmem_run_guard")
    path = tmp_path / "ledger.jsonl"
    ledger = guard.RequestLedger(path, "run-1", create=True)
    for index in range(4):
        ledger.reserve("C0", "probe", f"probe-{index}", count=2)
    assert ledger.snapshot() == {
        "run_id": "run-1", "used": {"probe": 8, "extract": 0, "admission": 0},
        "arms": {"C0": {"probe": 8, "extract": 0, "admission": 0},
                 "C1": {"probe": 0, "extract": 0, "admission": 0}},
        "reserved_total": 8,
    }
    before = path.read_bytes()
    with pytest.raises(ValueError, match="duplicate"):
        ledger.reserve("C0", "probe", "probe-0", count=2)
    with pytest.raises(ValueError, match="budget"):
        ledger.reserve("C0", "probe", "probe-4", count=2)
    with pytest.raises(ValueError, match="count"):
        ledger.reserve("C1", "probe", "wrong-count")
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="already exists"):
        guard.RequestLedger(path, "run-1", create=True)
    with pytest.raises(ValueError, match="run_id"):
        guard.RequestLedger(path, "other-run")


def test_ledger_rejects_corruption_without_appending(tmp_path):
    guard = importlib.import_module("socialmem_run_guard")
    path = tmp_path / "ledger.jsonl"
    ledger = guard.RequestLedger(path, "run-2", create=True)
    ledger.reserve("C0", "extract", "first")
    with path.open("ab") as stream:
        stream.write(b'{"not":"a ledger record"}\n')
    before = path.read_bytes()
    with pytest.raises(ValueError, match="ledger"):
        ledger.reserve("C0", "extract", "second")
    assert path.read_bytes() == before


def test_ledger_file_lock_allows_at_most_eight_concurrent_extract_reservations(tmp_path):
    guard = importlib.import_module("socialmem_run_guard")
    path = tmp_path / "ledger.jsonl"
    guard.RequestLedger(path, "race-run", create=True)
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    processes = [context.Process(target=_reserve_in_process, args=(str(path), f"id-{index}", queue))
                 for index in range(12)]
    for process in processes:
        process.start()
    results = [queue.get(timeout=10) for _ in processes]
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    assert sum(results) == 8
    assert guard.RequestLedger(path, "race-run").snapshot()["arms"]["C0"]["extract"] == 8


def test_frozen_identity_verifies_native_schema_config_sources_prompt_and_code(tmp_path):
    from starling import _core
    guard = importlib.import_module("socialmem_run_guard")
    artifact = tmp_path / "worker.py"
    artifact.write_text("frozen worker\n")
    config = {"endpoint": "https://provider.test/v1", "model": "fixture",
              "max_retries": 0, "output_mode": "json_schema_strict"}
    case = _case()
    frozen = guard.frozen_identity(_core, config, [case], [artifact])
    assert frozen["core_path"] == str(Path(_core.__file__).resolve())
    assert frozen["sources"] == {"case-1": _canonical_source(case)}
    assert frozen["prompt_sha256"]["case-1"] == hashlib.sha256(
        _core.claim_extraction_prompt(case["passage"], case["holder"]).encode()).hexdigest()
    assert guard.verify_identity(_core, config, frozen, case) is True
    with pytest.raises(ValueError, match="config"):
        guard.verify_identity(_core, {**config, "model": "drift"}, frozen)
    with pytest.raises(ValueError, match="source"):
        guard.verify_identity(_core, config, frozen, _case(passage="changed"))
    artifact.write_text("changed worker\n")
    with pytest.raises(ValueError, match="code"):
        guard.verify_identity(_core, config, frozen)
    altered = json.loads(json.dumps(frozen))
    altered["schemas"]["claim_extraction_v2"] = "0" * 64
    with pytest.raises(ValueError, match="schema"):
        guard.verify_identity(_core, config, altered)
    altered = json.loads(json.dumps(frozen))
    altered["core_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="core"):
        guard.verify_identity(_core, config, altered)


@pytest.fixture
def conformant_report(monkeypatch):
    from starling import _core
    probe = importlib.import_module("probe_socialmem_output_capability")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            name = body.get("response_format", {}).get("json_schema", {}).get("name", "")
            raw = ('{"schema_version":1,"decisions":[]}' if name == "claim_admission_v1"
                   else '{"schema_version":2,"statements":[]}')
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
    monkeypatch.setenv("OPENAI_API_KEY", "local-guard-fixture")
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    cfg = _core.OpenAIAdapterConfig.from_env()
    cfg.model, cfg.max_retries, cfg.timeout_ms = "local-guard", 0, 1000
    try:
        transport = {"endpoint": cfg.base_url, "model": cfg.model}
        yield _core, transport, probe.collect_report(_core, _core.OpenAIAdapter(cfg), transport)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_capability_requires_the_frozen_identity_report_hash_and_native_schema(conformant_report, tmp_path):
    core, transport, report = conformant_report
    guard = importlib.import_module("socialmem_run_guard")
    case = _case()
    config = {**transport, "max_retries": 0, "output_mode": "json_schema_strict"}
    frozen = guard.frozen_identity(core, config, [case])
    report_path = tmp_path / "capability.json"
    report_path.write_text(json.dumps(report))
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    readiness = guard.verify_capability(core, config, frozen, report_path, digest,
                                        at=datetime.now(timezone.utc))
    assert readiness["ready"] is True
    old_schema = json.loads(json.dumps(report))
    old_schema["schemas"]["claim_extraction_v2"]["sha256"] = "0" * 64
    report_path.write_text(json.dumps(old_schema))
    old_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="schema"):
        guard.verify_capability(core, config, frozen, report_path, old_digest,
                                check_freshness=False)
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="hash"):
        guard.verify_capability(core, config, frozen, report_path, "0" * 64)
