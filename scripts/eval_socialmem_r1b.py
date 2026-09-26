#!/usr/bin/env python3
"""R1/B 有界评测编排；抽取、解析和准入均由 C++ 原生核心执行。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from eval_socialmem_scope_latency import extract_once, require  # noqa: E402


class Budget:
    """单次运行的请求计数器，任何超限都立即失败。"""

    def __init__(self, *, max_probe=16, max_extract=16, max_admission=16):
        self.limits = {"probe": int(max_probe), "extract": int(max_extract),
                       "admission": int(max_admission)}
        self.used = {name: 0 for name in self.limits}

    @property
    def total(self):
        return sum(self.used.values())

    def consume(self, kind, count=1):
        if kind not in self.limits:
            raise ValueError(f"unknown budget kind: {kind}")
        if type(count) is not int or count < 0:
            raise ValueError("budget increment must be a non-negative integer")
        if self.used[kind] + count > self.limits[kind]:
            raise ValueError(f"{kind} request budget exceeded")
        self.used[kind] += count

    def snapshot(self):
        return {"used": dict(self.used), "limits": dict(self.limits), "total": self.total}


def capability_gate(reports):
    """两臂均 ready 才允许进入抽取阶段。"""
    return all(bool(reports.get(arm, {}).get("ready")) for arm in ("D0", "D1"))


def schedule_samples(cases, *, arms=("D0", "D1"), repetitions=2, capabilities=None):
    """按来源、重复和臂交替生成固定计划；门槛失败由 supervisor 返回空计划。"""
    if capabilities is not None and not capability_gate(capabilities):
        return []
    if len(arms) != 2 or repetitions < 1:
        raise ValueError("R1/B requires two arms and positive repetitions")
    rows = []
    for case in cases:
        for repetition in range(repetitions):
            for arm in arms if repetition % 2 == 0 else tuple(reversed(arms)):
                rows.append({"arm": arm, "repetition": repetition,
                             "case_id": case["id"], "case": case})
    return rows


def _policy(core):
    policy = core.ValidationPolicy()
    policy.semantic_claim_contract = True
    policy.claim_allow_code_fence = False
    policy.preserve_text_objects = True
    policy.attribute_first_order_mental_to_holder = False
    policy.claim_output_mode = core.OutputMode.JsonSchemaStrict
    policy.validate()
    return policy


def _response_record(response, *, prompt, prompt_input_hash):
    value = {"prompt": prompt, "prompt_input_hash": prompt_input_hash,
             "raw_response": getattr(response, "raw_xml", ""),
             "ok": bool(getattr(response, "ok", False)),
             "error": getattr(response, "error", "")}
    for name in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
        value[name] = getattr(response, name, None)
    if hasattr(response, "structured_metadata_json"):
        value["structured_output"] = json.loads(response.structured_metadata_json())
        metadata = value["structured_output"]
        if "attempt_count" in metadata:
            require(type(metadata["attempt_count"]) is int and metadata["attempt_count"] <= 1,
                    "native admission retry budget drift")
    return value


def _set_fake(fake, core, prompt, raw, ok=True, error=""):
    fake.set_response(core.Extractor.compute_prompt_input_hash(prompt), raw, ok, error)


def admission_status(record):
    if not record.get("ok"):
        return "admission_transport_failure"
    if record.get("wire_error"):
        return "admission_protocol_failure"
    if record.get("parse_errors"):
        return "admission_parse_failure"
    return "admission_rejected"


def worker_sample(core, llm, config, case, *, admission_llm=None,
                  artifact_dir=None, before_request=None):
    """完成一个来源的一次抽取和至多一次 C++ 准入请求。"""
    if admission_llm is None:
        admission_llm = llm
    if not all(isinstance(adapter, core.FakeLLMAdapter) for adapter in (llm, admission_llm)):
        from socialmem_run_guard import GuardedRequestGate
        require(type(before_request) is GuardedRequestGate and artifact_dir is not None,
                "real worker requires identity/budget guard and archive")
    if before_request is None:
        before_request = lambda _kind: None
    before_request("extract")
    extraction = extract_once(core, llm, config, case)
    result = {"id": case["id"], "holder": case["holder"],
              "source_sha256": extraction["source_sha256"],
              "schema_sha256": core.structured_output_schema_sha256(core.OutputContractKind.ClaimExtractionV2),
              "extraction": extraction, "admission": {"called": False},
              "retained": [], "status": "extraction_failure"}
    _write_exclusive(artifact_dir, "extraction.json", extraction)
    if not extraction["ok"]:
        result["status"] = "transport_failure"
        return _persist(result, artifact_dir)
    parsed = extraction.get("parse_result") or {}
    if extraction.get("wire_error") or parsed.get("errors"):
        result["status"] = "parse_failure"
        return _persist(result, artifact_dir)
    candidates = parsed.get("statements", [])
    if not candidates:
        result["status"] = "empty_candidates"
        return _persist(result, artifact_dir)

    # Fake 只重放同一份抽取原文，以便由 C++ 发现准入提示和候选集合。
    fake = core.FakeLLMAdapter()
    fake.set_default_response("", False, "unrecorded native replay request")
    _set_fake(fake, core, extraction["prompt"], extraction["raw_response"])
    adapter = core.SqliteAdapter.open(":memory:")
    policy = _policy(core)
    probe = core.memory_extract_llm(adapter, fake, "", case["holder"],
                                    case["passage"].encode(), policy)
    probe_receipt = json.loads(core.claim_extraction_receipt(probe))
    attempt = probe_receipt["attempts"][0]
    request = attempt["admission"]
    if not request.get("called"):
        result["status"] = "native_rejection"
        result["receipt"] = probe_receipt
        return _persist(result, artifact_dir)

    result["admission"] = {"called": True, "prompt": request["prompt"],
        "schema_sha256": core.structured_output_schema_sha256(core.OutputContractKind.ClaimAdmissionV1),
        "prompt_input_hash": request["prompt_input_hash"],
        "prompt_sha256": hashlib.sha256(request["prompt"].encode()).hexdigest(),
        "candidates": candidates,
        "candidates_sha256": hashlib.sha256(json.dumps(candidates, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    _write_exclusive(artifact_dir, "admission_preview.json", result["admission"])
    before_request("admission")
    try:
        response = admission_llm.extract_with_contract(
            request["prompt"], request["prompt_input_hash"],
            core.StructuredOutputRequest(core.OutputContractKind.ClaimAdmissionV1,
                                         core.OutputMode.JsonSchemaStrict))
        actual = _response_record(response, prompt=request["prompt"],
                                  prompt_input_hash=request["prompt_input_hash"])
    except Exception as exc:
        actual = {"prompt": request["prompt"], "prompt_input_hash": request["prompt_input_hash"],
                  "raw_response": "", "ok": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    result["admission"].update(actual)
    try:
        result["admission"]["wire_error"] = core.structured_output_validation_error(
            actual.get("raw_response", ""), core.OutputContractKind.ClaimAdmissionV1) \
            if actual.get("ok") else None
    except Exception:
        result["admission"]["wire_error"] = "schema_failure:validation_exception"
    _set_fake(fake, core, request["prompt"], actual.get("raw_response", ""),
              actual.get("ok", False), actual.get("error", ""))
    final = core.memory_extract_llm(adapter, fake, "", case["holder"],
                                    case["passage"].encode(), policy)
    receipt = json.loads(core.claim_extraction_receipt(final))
    result["receipt"] = receipt
    result["retained"] = receipt["attempts"][-1].get("retained", [])
    result["admission"]["parse_errors"] = receipt["attempts"][-1].get("errors", [])
    result["status"] = "admitted" if result["retained"] else admission_status(result["admission"])
    return _persist(result, artifact_dir)


def _persist(value, artifact_dir):
    if artifact_dir is None:
        return value
    root = Path(artifact_dir); root.mkdir(parents=True, exist_ok=True)
    path = root / f"sample_{value['id']}.json"
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    value["artifact"] = str(path)
    return value


def _write_exclusive(artifact_dir, name, value):
    if artifact_dir is None:
        return
    root = Path(artifact_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
