"""零模型调用的原生重放编排；人工覆盖注释不参与候选生成或语义校验。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def native_file(stage):
    stage = Path(stage).resolve()
    if stage.is_file():
        return stage
    for directory in (stage / "python/starling", stage / "starling", stage):
        matches = list(directory.glob("_core*.so"))
        if len(matches) == 1:
            return matches[0].resolve()
    raise ValueError("native stage must identify exactly one core")


def load_receipt(record, manifest_dir):
    path = Path(record["receipt_path"])
    if not path.is_absolute():
        path = manifest_dir / path
    if digest(path) != record["receipt_sha256"]:
        raise ValueError("receipt hash mismatch")
    if "line_index" in record:
        lines = path.read_text().splitlines()
        index = record["line_index"]
        if type(index) is not int or not 0 <= index < len(lines):
            raise ValueError("receipt line index out of range")
        value = json.loads(lines[index])
    else:
        value = read(path)
    return value.get("receipt", value)


def replay_worker(core_path, records):
    # 直接载入指定扩展，避免不同环境的 starling/__init__.py 改变导入身份。
    spec = importlib.util.spec_from_file_location("_core", str(core_path))
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    results = []
    for record in records:
        source, holder, receipt = record["passage"], record["holder"], record["receipt"]
        units = json.loads(core.claim_source_units(source))
        result = {"id": record["id"], "source_units": units,
                  "core_sha256": digest(core.__file__),
                  "generated_candidates": None, "raw_statements": None,
                  "parse_result": None, "wire_error": None,
                  "historical_parse_result": receipt.get("parse_result"),
                  "historical_diagnostics_status": "available" if "row_diagnostics" in (receipt.get("parse_result") or {}) else "unknown",
                  "historical_followup_status": record.get("historical_followup_status", "unknown"),
                  "admission_status": "not_executed", "persistence_status": "not_executed",
                  "retrieval_status": "not_executed", "coverage": []}
        if receipt["ok"]:
            raw = receipt["raw_response"]
            result["wire_error"] = core.structured_output_validation_error(raw, core.OutputContractKind.ClaimExtractionV2)
            result["parse_result"] = json.loads(core.claim_parse_response(raw, source, holder))
            # JSON 是统计载体；是否符合结构只取 C++ wire 校验结果。
            if not result["wire_error"]:
                result["raw_statements"] = json.loads(raw)["statements"]
                result["generated_candidates"] = len(result["raw_statements"])
        result["extraction_prompt_sha256"] = hashlib.sha256(core.claim_extraction_prompt(source, holder).encode()).hexdigest()
        result["receipt_sha256"] = record["receipt_sha256"]
        result["source_sha256"] = record["source_sha256"]
        results.append(result)
    return results


def run_analysis(input_manifest, annotations, native_stage, output_dir):
    input_manifest, annotations, output_dir = map(Path, (input_manifest, annotations, output_dir))
    if output_dir.exists():
        raise FileExistsError(output_dir)
    manifest, notes = read(input_manifest), read(annotations)
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported analysis manifest")
    core_path = native_file(native_stage)
    if digest(core_path) != manifest["native_core_sha256"]:
        raise ValueError("core hash mismatch")
    records, ids = [], set()
    for record in manifest["records"]:
        if record["id"] in ids:
            raise ValueError("duplicate record id")
        ids.add(record["id"])
        if hashlib.sha256(record["passage"].encode()).hexdigest() != record["source_sha256"]:
            raise ValueError("source hash mismatch")
        receipt = load_receipt(record, input_manifest.resolve().parent)
        if type(receipt.get("ok")) is not bool:
            raise ValueError("receipt completion status missing")
        if receipt["ok"] and not isinstance(receipt.get("raw_response"), str):
            raise ValueError("complete receipt must contain raw response")
        for field in ("holder", "source_sha256"):
            if field in receipt and receipt[field] != record[field]:
                raise ValueError("receipt source identity mismatch")
        records.append({**record, "receipt": receipt})
    command = [sys.executable, "-S", str(Path(__file__).resolve()), "--worker", str(core_path)]
    process = subprocess.run(command, input=json.dumps(records), text=True, capture_output=True, timeout=120)
    if process.returncode:
        raise RuntimeError("native replay failed: " + process.stderr[-3000:])
    results = json.loads(process.stdout)
    by_id = {r["id"]: r for r in results}
    annotated = set()
    for note in notes:
        key = (note["record_id"], note["state_id"])
        if key in annotated or note["record_id"] not in by_id:
            raise ValueError("duplicate state or unknown record annotation")
        annotated.add(key)
        result = by_id[note["record_id"]]
        if not any(u["clause_id"] == note["clause_id"] for u in result["source_units"]):
            raise ValueError("annotation clause absent from source")
        if not note.get("reason"):
            raise ValueError("manual annotation requires a reason")
        indexes = note["raw_indexes"]
        if any(type(i) is not int or i < 0 for i in indexes) or len(indexes) != len(set(indexes)):
            raise ValueError("invalid raw indexes")
        rows = result["raw_statements"]
        if rows is None:
            if indexes:
                raise ValueError("unknown response cannot have matched indexes")
            status = "unknown"
        else:
            for index in indexes:
                if index >= len(rows):
                    raise ValueError("annotation raw index out of range")
                row = rows[index]
                if row["evidence"]["clause_id"] != note["clause_id"] or row["predicate"] != note["predicate"]:
                    raise ValueError("annotation row identity mismatch")
            status = "generated" if indexes else "not_generated"
        parsed = result["parse_result"]
        diagnosis = None if parsed is None else parsed.get("row_diagnostics")
        result["coverage"].append({**note, "generation_status": status,
            "parse_status": "unknown" if parsed is None else "batch_rejected" if parsed["errors"] else "parsed",
            "matched_row_diagnostics": None if diagnosis is None else [d for d in diagnosis if d["index"] in indexes]})
    report = {"schema_version": 1, "status": "offline_native_replay", "external_requests": 0,
              "quality": None, "native_core_sha256": digest(core_path),
              "input_manifest_sha256": digest(input_manifest), "annotations_sha256": digest(annotations),
              "records": results}
    # 所有身份、来源和注释检查完成后才创建输出，失败不留下假成功报告。
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        print(json.dumps(replay_worker(Path(sys.argv[2]), json.load(sys.stdin)), ensure_ascii=False))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--native-stage", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = run_analysis(args.input_manifest, args.annotations, args.native_stage, args.output_dir)
    print(json.dumps({"status": report["status"], "records": len(report["records"]), "external_requests": 0}))


if __name__ == "__main__":
    main()
