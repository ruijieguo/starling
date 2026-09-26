#!/usr/bin/env python3
"""显式调用 C++ 能力探测并归档；不含 schema、语义或重试实现。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mode_value(core, name):
    return {"legacy": core.OutputMode.Legacy, "json_object": core.OutputMode.JsonObject,
            "json_schema_strict": core.OutputMode.JsonSchemaStrict}[name]


def contract_values(core):
    return {"claim_extraction_v2": core.OutputContractKind.ClaimExtractionV2,
            "claim_admission_v1": core.OutputContractKind.ClaimAdmissionV1}


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect_report(core, llm, transport):
    capabilities = []
    schemas = {name: {"schema": json.loads(core.structured_output_schema(kind)),
                      "sha256": core.structured_output_schema_sha256(kind)}
               for name, kind in contract_values(core).items()}
    for mode in ("json_object", "json_schema_strict"):
        for kind in contract_values(core).values():
            evidence = llm.probe_structured_output(core.StructuredOutputRequest(kind, mode_value(core, mode)))
            capabilities.append(json.loads(core.capability_evidence_json(evidence)))
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "core_sha256": file_sha(core.__file__),
        "transport": {key: transport[key] for key in ("endpoint", "model")},
        "schemas": schemas, "capabilities": capabilities,
        "request_count": sum(e["request_count"] for e in capabilities),
        "probe_max_retries": 0, "quality": None}


def check_report(core, report, transport, output_mode, *, at=None, check_freshness=True):
    """只核验归档的身份、哈希、计数和前置条件；契约校验调用 C++。"""
    require(report["schema_version"] == 1 and output_mode in ("json_object", "json_schema_strict"),
            "invalid capability report version/mode")
    require(report["core_sha256"] == file_sha(core.__file__), "capability native core drift")
    expected_transport = {key: transport[key] for key in ("endpoint", "model")}
    require(report["transport"] == expected_transport, "capability endpoint/model drift")
    require(report["probe_max_retries"] == 0, "capability retry policy drift")
    kinds = contract_values(core)
    for name, kind in kinds.items():
        schema = report["schemas"][name]
        require(schema["sha256"] == core.structured_output_schema_sha256(kind) and
                schema["schema"] == json.loads(core.structured_output_schema(kind)), "capability schema drift")
    now = at or datetime.now(timezone.utc)
    seen, selected = set(), []
    total = 0
    for evidence in report["capabilities"]:
        key = evidence["output_mode"], evidence["output_contract"]
        require(key not in seen and key[0] in ("json_object", "json_schema_strict") and key[1] in kinds,
                "duplicate or unknown capability identity")
        seen.add(key)
        native_error = core.validate_capability_evidence_json(json.dumps(evidence, ensure_ascii=False))
        require(not native_error, f"capability evidence invalid: {native_error}")
        require(evidence["endpoint"] == transport["endpoint"] and evidence["model"] == transport["model"],
                "capability evidence endpoint/model drift")
        require(evidence["schema_sha256"] == report["schemas"][key[1]]["sha256"], "capability evidence schema drift")
        total += evidence["request_count"]
        if key[0] == output_mode:
            selected.append(evidence)
    require(len(seen) == 4 and type(report["request_count"]) is int and report["request_count"] == total <= 8,
            "capability total request count drift")
    reasons = []
    for evidence in selected:
        if evidence["state"] != "observed_conformant":
            reasons.append(f"{evidence['output_contract']}:{evidence['state']}:{evidence['error']}")
        observed = datetime.fromisoformat(evidence["observed_at"].replace("Z", "+00:00"))
        age = (now - observed).total_seconds()
        if check_freshness and not 0 <= age < 600:
            reasons.append(f"{evidence['output_contract']}:capability_report_expired")
    return {"ready": not reasons, "reasons": reasons,
            "evidence_ids": {e["output_contract"]: e["evidence_id"] for e in selected}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="deepseek-v3", help="Explicit extraction/admission model; no fallback")
    args = parser.parse_args()
    require(not args.out.exists(), "capability output already exists")
    from starling import _core
    from eval_socialmem_extraction import build_llm
    llm, transport = build_llm(_core, model=args.model)
    report = collect_report(_core, llm, transport)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"request_count": report["request_count"], "states": [
        {key: e[key] for key in ("output_mode", "output_contract", "state", "error")}
        for e in report["capabilities"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
