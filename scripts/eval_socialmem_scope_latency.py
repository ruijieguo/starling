#!/usr/bin/env python3
"""单个冻结 Starling 核心的 S/T 探测、预览和一次抽取 worker。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import sys
from threading import Thread
from urllib.parse import urlsplit


OUTPUT_MODE = "json_schema_strict"
MODEL = "qwen3.7-plus"
MAX_TOKENS = 4096
TEMPERATURE = 0
MAX_RETRIES = 0
T_SOURCE_IDS = (
    "eval-028", "eval-022", "eval-009", "eval-036",
    "eval-025", "eval-038", "eval-044", "eval-048",
    "Q1_a5s1c1_Femi", "Q9_a0b1c2d3_Yuki",
    "Q9_a0b1c2d3_Marcus", "Q1_a5s1c1_Claudette",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_sha256(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_json_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def source_record(case):
    """Freeze only model input identity; never copy QA labels into S/T plans."""
    return {key: case[key] for key in ("id", "track", "holder", "passage")} | {
        "source_bytes": len(case["passage"].encode()),
        "source_sha256": hashlib.sha256(case["passage"].encode()).hexdigest(),
    }


def _case_index(inputs):
    tracks = ("p1", "synthetic", "scoped", "fixed_controls")
    return {(case["track"], case["id"]): case
            for track in tracks for case in inputs.get(track, [])}


def select_scope_sources(core, inputs_path, calls_path):
    """Find A's native parse errors and nearest unused clean same-track controls."""
    cases = _case_index(load_json(inputs_path))
    failures, controls = [], []
    for call in load_jsonl(calls_path):
        if call["track"] not in ("p1", "synthetic", "scoped") or not call["ok"]:
            continue
        case = cases[call["track"], call["id"]]
        parsed = json.loads(core.claim_parse_response(
            call["raw_response"], case["passage"], case["holder"]))
        entry = source_record(case)
        entry["native_errors"] = parsed["errors"]
        entry["native_semantic_rejections"] = parsed["semantic_rejections"]
        if parsed["errors"]:
            failures.append(entry)
        else:
            controls.append(entry)
    require(len(failures) == 7, f"expected seven native scope failures, got {len(failures)}")
    selected, used = [], set()
    for target in failures:
        candidates = [control for control in controls
                      if control["track"] == target["track"] and control["id"] not in used]
        require(candidates, f"no unused clean control for {target['id']}")
        control = min(candidates, key=lambda item: (
            abs(item["source_bytes"] - target["source_bytes"]), item["id"]))
        used.add(control["id"])
        selected.append({"target": target, "control": control,
                         "source_byte_distance": abs(
                             control["source_bytes"] - target["source_bytes"])})
    return selected


def select_timeout_sources(inputs_path, calls_path):
    cases = _case_index(load_json(inputs_path))
    calls = {(call["track"], call["id"]): call for call in load_jsonl(calls_path)
             if call["track"] in ("p1", "synthetic", "scoped")}
    by_id = {}
    for case in cases.values():
        if case["id"] in by_id:
            require(by_id[case["id"]]["passage"] == case["passage"],
                    f"ambiguous source id: {case['id']}")
        by_id[case["id"]] = case
    missing = [case_id for case_id in T_SOURCE_IDS if case_id not in by_id]
    require(not missing, f"missing fixed T sources: {missing}")
    selected = []
    for index, case_id in enumerate(T_SOURCE_IDS):
        case = by_id[case_id]
        call = calls.get((case["track"], case_id))
        require(call is not None, f"missing historical extraction call: {case_id}")
        expected_ok = index % 2 == 1
        require(call["ok"] is expected_ok,
                f"fixed T historical response status drift: {case_id}")
        expected_error = "" if expected_ok else "transport_error:Timeout was reached"
        require(call["error"] == expected_error,
                f"fixed T timeout identity drift: {case_id}")
        selected.append(source_record(case) | {"historical_call": {
            "ok": call["ok"], "error": call["error"],
            "latency_ms": call["latency_ms"],
            "raw_response_sha256": (hashlib.sha256(call["raw_response"].encode()).hexdigest()
                                    if call["ok"] else None)}})
    return selected


def mode_value(core):
    return core.OutputMode.JsonSchemaStrict


def native_config_snapshot(config):
    return {"endpoint": config.base_url, "model": config.model,
            "timeout_ms": config.timeout_ms, "max_tokens": config.max_tokens,
            "max_retries": config.max_retries, "temperature": TEMPERATURE,
            "output_mode": OUTPUT_MODE}


def build_native_adapter(core, *, model=MODEL, timeout_ms=60000, endpoint=None,
                         credential_env=None):
    require(model.strip() == model and bool(model), "model must be explicit and non-empty")
    require(type(timeout_ms) is int and timeout_ms > 0, "timeout_ms must be positive")
    saved_key = os.environ.get("OPENAI_API_KEY")
    if credential_env is not None:
        require(bool(os.environ.get(credential_env)), f"{credential_env} is required")
        os.environ["OPENAI_API_KEY"] = os.environ[credential_env]
    try:
        config = core.OpenAIAdapterConfig.from_env()
        if endpoint is not None:
            require(bool(endpoint.strip()), "endpoint must be non-empty")
            config.base_url = endpoint
        config.model = model
        config.timeout_ms = timeout_ms
        config.max_tokens = MAX_TOKENS
        config.max_retries = MAX_RETRIES
        adapter = core.OpenAIAdapter(config)
    finally:
        if credential_env is not None:
            if saved_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = saved_key
    return adapter, native_config_snapshot(config)


def core_identity(core):
    kind = core.OutputContractKind.ClaimExtractionV2
    probe = importlib.import_module("probe_socialmem_output_capability")
    return {"core_path": str(Path(core.__file__).resolve()),
            "core_sha256": file_sha256(core.__file__),
            "schema_sha256": core.structured_output_schema_sha256(kind),
            "schema": json.loads(core.structured_output_schema(kind)),
            "worker_path": str(Path(__file__).resolve()),
            "worker_sha256": file_sha256(__file__),
            "probe_helper_path": str(Path(probe.__file__).resolve()),
            "probe_helper_sha256": file_sha256(probe.__file__)}


def _response_metadata(response):
    require(hasattr(response, "structured_metadata_json"),
            "native response has no structured transport metadata")
    metadata = json.loads(response.structured_metadata_json())
    require(type(metadata.get("attempt_count")) is int and metadata["attempt_count"] <= 1,
            "native extraction retry budget drift")
    return metadata


def extract_once(core, llm, config, case):
    require(config["max_retries"] == 0, "extraction retries must be disabled")
    require(config["output_mode"] == OUTPUT_MODE, "unknown extraction mode")
    prompt = core.claim_extraction_prompt(case["passage"], case["holder"])
    prompt_hash = core.Extractor.compute_prompt_input_hash(prompt)
    request = core.StructuredOutputRequest(
        core.OutputContractKind.ClaimExtractionV2, mode_value(core))
    response = llm.extract_with_contract(prompt, prompt_hash, request)
    native = _response_metadata(response)
    complete = bool(response.ok)
    parsed = None
    wire_error = None
    if complete:
        wire_error = core.structured_output_validation_error(
            response.raw_xml, core.OutputContractKind.ClaimExtractionV2)
        parsed = json.loads(core.claim_parse_response(
            response.raw_xml, case["passage"], case["holder"]))
    attempts = native.get("http_attempts") or []
    certainty = attempts[-1].get("execution_certainty") if attempts else "unknown"
    return {"id": case["id"], "track": case["track"], "holder": case["holder"],
            "source_sha256": hashlib.sha256(case["passage"].encode()).hexdigest(),
            "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt_input_hash": prompt_hash, "config": config,
            "ok": complete, "error": response.error, "execution_certainty": certainty,
            "raw_response": response.raw_xml if complete else None,
            "prompt_tokens": response.prompt_tokens if complete else None,
            "completion_tokens": response.completion_tokens if complete else None,
            "total_tokens": response.total_tokens if complete else None,
            "latency_ms": response.latency_ms, "wire_error": wire_error,
            "parse_result": parsed, "native": native}


def sanitize_captured_request(request):
    sensitive = {"authorization", "proxy-authorization", "x-api-key", "api-key"}
    headers = {key: value for key, value in request.get("headers", {}).items()
               if key.lower() not in sensitive}
    method = request.get("method", "POST")
    path = request.get("path")
    body = request["body"]
    return {"method": method,
            "path": path, "headers": headers,
            "body": body, "body_sha256": canonical_sha256(body),
            "request_sha256": canonical_sha256(
                {"method": method, "path": path, "body": body})}


def verify_worker_manifest(core, config, manifest):
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    require(manifest["config_sha256"] == canonical_sha256(manifest["config"]),
            "config identity drift")
    require(manifest["config"] == config, "constructed config drift")
    report_path = Path(manifest["report"])
    require(report_path.is_file() and manifest["report_sha256"] == file_sha256(report_path),
            "capability report drift")
    require(manifest["manifest_sha256"] == canonical_sha256(body), "arm identity drift")
    identity = core_identity(core)
    require(manifest["core_sha256"] == identity["core_sha256"], "native core drift")
    require(manifest["schema_sha256"] == identity["schema_sha256"], "native schema drift")
    require(manifest.get("worker_sha256", identity["worker_sha256"]) == identity["worker_sha256"],
            "worker source drift")
    require(manifest.get("probe_helper_sha256", identity["probe_helper_sha256"]) ==
            identity["probe_helper_sha256"], "probe helper source drift")
    if manifest.get("supervisor_path"):
        require(file_sha256(manifest["supervisor_path"]) == manifest["supervisor_sha256"],
                "supervisor source drift")
    return load_json(report_path)


def verify_frozen_preview(core, config, expected, request_sha256s=None):
    require(config == expected["config"], "frozen config preflight drift")
    require(core_identity(core) == expected["identity"], "frozen native/source preflight drift")
    if request_sha256s is not None:
        require(request_sha256s == expected["request_sha256s"],
                "frozen native request preflight drift")
    return True


def capture_preview(core, cases, *, model, timeout_ms, intended_endpoint,
                    include_probe=True):
    """Capture C++ serialized requests on loopback; never synthesize service JSON."""
    captured = []
    endpoint = urlsplit(intended_endpoint)
    require(endpoint.scheme in ("http", "https") and endpoint.netloc and
            not endpoint.query and not endpoint.fragment,
            "intended endpoint must be an absolute URL without query or fragment")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append(sanitize_captured_request(
                {"method": "POST", "path": self.path,
                 "headers": dict(self.headers), "body": body}))
            schema_name = body.get("response_format", {}).get("json_schema", {}).get("name", "")
            prompt = body["messages"][0]["content"]
            admission = schema_name == "claim_admission_v1" or "candidate list is empty" in prompt
            raw = ('{"schema_version":1,"decisions":[]}' if admission else
                   '{"schema_version":2,"statements":[]}')
            response = json.dumps({"choices": [{"finish_reason": "stop",
                "message": {"content": raw}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    old_key, old_url = os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = "local-preview-only"
    os.environ["OPENAI_BASE_URL"] = (
        f"http://127.0.0.1:{server.server_port}{endpoint.path}")
    try:
        llm, capture_config = build_native_adapter(
            core, model=model, timeout_ms=timeout_ms)
        report = None
        if include_probe:
            probe = importlib.import_module("probe_socialmem_output_capability")
            report = probe.collect_report(core, llm, capture_config)
        receipts = [extract_once(core, llm, capture_config, case) for case in cases]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_url is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = old_url
    intended_config = dict(capture_config, endpoint=intended_endpoint)
    probe_request_count = report["request_count"] if report is not None else 0
    require(probe_request_count <= 8, "probe request budget exceeded")
    require(len(captured) == probe_request_count + len(cases),
            "captured native request count drift")
    return {"created_at": datetime.now(timezone.utc).isoformat(),
            "identity": core_identity(core), "config": intended_config,
            "capture_config": capture_config, "local_capability_report": report,
            "requests": captured, "receipts": receipts,
            "probe_request_count": probe_request_count,
            "extraction_request_count": len(cases)}


def load_stage(stage):
    stage = Path(stage).resolve()
    require(stage.is_dir(), f"stage does not exist: {stage}")
    sys.path[:0] = [str(stage / "python"), str(stage), str(stage / "scripts")]
    core = importlib.import_module("starling._core")
    require(Path(core.__file__).resolve().is_relative_to(stage),
            f"native core did not load from stage: {core.__file__}")
    return core


def _config_from_args(core, args):
    return build_native_adapter(core, model=args.model, timeout_ms=args.timeout_ms,
                                endpoint=getattr(args, "endpoint", None),
                                credential_env=getattr(args, "credential_env", None))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("inspect", "preflight", "probe", "preview", "extract", "check",
                   "select-scope", "select-timeout"):
        child = subparsers.add_parser(action)
        child.add_argument("--stage", type=Path, required=True)
        child.add_argument("--out", type=Path, required=True)
        if action in ("inspect", "preflight", "probe", "preview", "extract"):
            child.add_argument("--model", default=MODEL)
            child.add_argument("--timeout-ms", type=int, default=60000)
            child.add_argument("--endpoint")
        if action in ("inspect", "preflight", "probe", "extract"):
            child.add_argument("--credential-env", default="DASHSCOPE_API_KEY")
        if action in ("preflight", "probe"):
            child.add_argument("--expected", type=Path, required=True)
        if action in ("preflight", "preview", "extract"):
            child.add_argument("--cases", type=Path, required=True)
        if action in ("check", "extract"):
            child.add_argument("--manifest", type=Path, required=True)
        if action == "extract":
            child.add_argument("--expected-request-sha256", required=True)
        if action == "check":
            child.add_argument("--at", required=True)
        if action in ("select-scope", "select-timeout"):
            child.add_argument("--inputs", type=Path, required=True)
        if action in ("select-scope", "select-timeout"):
            child.add_argument("--calls", type=Path, required=True)
    args = parser.parse_args(argv)
    core = load_stage(args.stage)
    if args.action == "select-scope":
        value = select_scope_sources(core, args.inputs, args.calls)
    elif args.action == "select-timeout":
        value = select_timeout_sources(args.inputs, args.calls)
    elif args.action == "inspect":
        os.environ.setdefault(args.credential_env, "identity-only")
        _llm, config = _config_from_args(core, args)
        value = {"created_at": datetime.now(timezone.utc).isoformat(),
                 "identity": core_identity(core), "config": config}
    elif args.action == "preflight":
        expected = load_json(args.expected)
        preview = capture_preview(core, load_json(args.cases), model=args.model,
            timeout_ms=args.timeout_ms, intended_endpoint=args.endpoint)
        request_hashes = [request["request_sha256"] for request in preview["requests"]]
        verify_frozen_preview(core, preview["config"], expected, request_hashes)
        value = {"created_at": datetime.now(timezone.utc).isoformat(),
                 "identity": core_identity(core), "config": preview["config"],
                 "request_sha256s": request_hashes}
    elif args.action == "probe":
        expected = load_json(args.expected)
        local = capture_preview(core, [], model=args.model,
            timeout_ms=args.timeout_ms, intended_endpoint=args.endpoint)
        local_hashes = [request["request_sha256"] for request in local["requests"]]
        require(local_hashes == expected["probe_request_sha256s"],
                "frozen probe request preflight drift")
        llm, config = _config_from_args(core, args)
        verify_frozen_preview(core, config, expected)
        probe = importlib.import_module("probe_socialmem_output_capability")
        report = probe.collect_report(core, llm, config)
        require(report["request_count"] <= 8, "probe request budget exceeded")
        readiness = probe.check_report(core, report, config, OUTPUT_MODE)
        value = {"created_at": datetime.now(timezone.utc).isoformat(),
                 "identity": core_identity(core), "config": config, "report": report,
                 "readiness": readiness}
    elif args.action == "preview":
        require(args.endpoint, "preview requires intended endpoint")
        value = capture_preview(core, load_json(args.cases), model=args.model,
                                timeout_ms=args.timeout_ms, intended_endpoint=args.endpoint)
    elif args.action == "check":
        manifest = load_json(args.manifest)
        os.environ.setdefault("OPENAI_API_KEY", "identity-only")
        _llm, config = build_native_adapter(core, model=manifest["config"]["model"],
            timeout_ms=manifest["config"]["timeout_ms"],
            endpoint=manifest["config"]["endpoint"])
        report = verify_worker_manifest(core, config, manifest)
        probe = importlib.import_module("probe_socialmem_output_capability")
        at = datetime.fromisoformat(args.at.replace("Z", "+00:00"))
        value = probe.check_report(core, report, config, OUTPUT_MODE, at=at)
    else:
        cases = load_json(args.cases)
        require(len(cases) == 1, "extract accepts exactly one frozen source")
        manifest = load_json(args.manifest)
        local = capture_preview(core, cases, model=args.model,
            timeout_ms=args.timeout_ms, intended_endpoint=args.endpoint,
            include_probe=False)
        verify_worker_manifest(core, local["config"], manifest)
        require(len(local["requests"]) == 1 and
                local["requests"][0]["request_sha256"] == args.expected_request_sha256,
                "frozen extraction request preflight drift")
        llm, config = _config_from_args(core, args)
        verify_worker_manifest(core, config, manifest)
        value = {"created_at": datetime.now(timezone.utc).isoformat(),
                 "identity": core_identity(core),
                 "receipt": extract_once(core, llm, config, cases[0])}
    write_json_new(args.out, value)


if __name__ == "__main__":
    main()
