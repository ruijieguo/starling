#!/usr/bin/env python3
"""claim 合同通道真实模型探针：固定用例重复抽取与准入，逐次记录终态与协议形状。

只做评测编排。提示、解析、作用域守卫、准入、持久化全在 C++ 核心；本脚本不实现语义判断，
不重试，gold 答案不进入提示。准入响应是否为合法 JSON 只按字面 json.loads 判定，
不修复、不截取。冻结的扩展标签及其哈希不受影响，也不产生任何准确率。
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

import eval_ladder as ladder
import eval_socialmem_claim_contract as claim
import eval_socialmem_controls as controls
import eval_socialmem_predicates as pred
import eval_socialmem_temporal as temporal
import probe_socialmem_negation_scope as base

DEFAULT_MODEL = "qwen3.8-27b"
MODES = ("legacy", "json_object")
DEFAULT_CASES = ("negative_target_scope", "preference_contrast", "emotion_negative",
                 "reported_distrust", "decision_change", "mixed_emotions")
# 传输档位。deepseek-2026-09-12 复刻 2026-09-12 轮次记录的抽取传输（见 generation 分析 JSON 的
# extract_transport）；json_object 由 --modes 选择，不在档位里。
PROFILES = {
    "default": {"max_tokens": 8192, "timeout_ms": 120000, "max_retries": 0, "enable_thinking": False},
    "deepseek-2026-09-12": {"max_tokens": 4096, "timeout_ms": 60000, "max_retries": 3, "enable_thinking": None},
}


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_cases(ids):
    ids = tuple(ids)
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("case ids must be nonempty and unique")
    sources = {case["id"]: case for case in pred.synthetic_cases()}
    unknown = [name for name in ids if name not in sources]
    if unknown:
        raise ValueError(f"unknown synthetic case ids: {unknown}")
    return [{**sources[name], "track": "synthetic"} for name in ids]


def resolve_case_ids(ids):
    """`all` 展开为冻结的全部 synthetic 用例；其余原样返回。"""
    ids = list(ids)
    if ids == ["all"]:
        return tuple(case["id"] for case in pred.synthetic_cases())
    return tuple(ids)


def admission_shape(raw):
    """准入原文的字面形状；解析失败就是失败，不尝试修复。"""
    text = raw or ""
    try:
        json.loads(text)
        parsable = True
    except ValueError:
        parsable = False
    return {"length": len(text), "parsable": parsable, "ends_with_brace": text.rstrip().endswith("}"),
            "brace_balance": text.count("{") - text.count("}")}


def candidate_view(attempt):
    """只读 C++ 已解析的候选；不在 Python 里重新解析模型原文。"""
    candidates = attempt.get("candidates")
    statements = candidates.get("statements") if isinstance(candidates, dict) else None
    return [{"predicate": row.get("predicate"), "object": row.get("object"), "polarity": row.get("polarity"),
             "scope_markers": (row.get("evidence") or {}).get("scope_markers"),
             "topic": (row.get("evidence") or {}).get("topic")} for row in (statements or [])]


def rejection_detail(item):
    if isinstance(item, dict):
        return str(item.get("detail") or item.get("reason") or item)
    return str(item)


def run_one(core, llm, case, mode, repeat, out):
    with tempfile.TemporaryDirectory(prefix="claim-channel-probe-") as tmp:
        with pred.archived_runtime(Path(tmp) / "case.db") as (rt, working):
            committed, receipt = claim.native_persist(core, rt.adapter, case, llm)
            rows = temporal.statement_rows(working)
    attempt = receipt["attempts"][0]
    extraction, admission = attempt["extraction"], attempt["admission"]
    called = bool(admission.get("called"))
    admission_raw = admission.get("raw_response") or ""
    record = {
        "id": case["id"], "mode": mode, "repeat": repeat,
        "outcome": claim.outcome(receipt, committed),
        "failure_category": committed["failure_category"], "failure_detail": committed["failure_detail"],
        "attempt_errors": attempt["errors"], "semantic_rejections": attempt["semantic_rejections"],
        "retained": len(attempt["retained"]),
        "extraction": {"ok": bool(extraction.get("ok")), "finish_reason": extraction.get("finish_reason"),
                       "completion_tokens": extraction.get("completion_tokens") or 0,
                       "total_tokens": extraction.get("total_tokens") or 0,
                       "raw": extraction.get("raw_response") or ""},
        "admission": {"called": called, "ok": bool(admission.get("ok")),
                      "finish_reason": admission.get("finish_reason"),
                      "completion_tokens": admission.get("completion_tokens") or 0,
                      "total_tokens": admission.get("total_tokens") or 0, "raw": admission_raw,
                      **(admission_shape(admission_raw) if called else {})},
        "candidates": candidate_view(attempt),
        "stored": [{"predicate": row["predicate"], "object": row["object_value"], "polarity": row["polarity"]}
                   for row in rows],
    }
    record["tokens"] = record["extraction"]["total_tokens"] + record["admission"]["total_tokens"]
    ladder.append_journal(out / "runs.jsonl", record)
    return record


def summarize(records):
    cells = {}
    for case_id, mode in sorted({(r["id"], r["mode"]) for r in records}):
        mine = [r for r in records if (r["id"], r["mode"]) == (case_id, mode)]
        called = [r for r in mine if r["admission"]["called"]]
        cells[f"{case_id}|{mode}"] = {
            "runs": len(mine),
            "outcomes": dict(sorted(Counter(r["outcome"] for r in mine).items())),
            "failure_details": dict(sorted(Counter(r["failure_detail"] for r in mine if r["failure_detail"]).items())),
            "rejection_details": dict(sorted(Counter(
                rejection_detail(x) for r in mine for x in r["semantic_rejections"]).items())),
            "admission_called": len(called),
            "admission_unparsable": sum(not r["admission"]["parsable"] for r in called),
            "retained_rows": sum(r["retained"] for r in mine)}
    return {"cells": cells, "runs": len(records),
            "requests": sum(1 + r["admission"]["called"] for r in records),
            "tokens": sum(r["tokens"] for r in records)}


def run(core, llms, transports, out, *, case_ids=DEFAULT_CASES, repeats=3, profile="default"):
    if repeats < 1:
        raise ValueError("repeats must be positive")
    modes = tuple(llms)
    if not modes or any(mode not in MODES for mode in modes) or set(transports) != set(modes):
        raise ValueError("modes must be a nonempty subset of legacy/json_object with matching transports")
    cases = load_cases(case_ids)
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"status": "running", "claim_level": "claim_channel_protocol_probe", "profile": profile,
                "started_at": datetime.now(timezone.utc).isoformat(), "repeats": repeats,
                "cases": [c["id"] for c in cases], "modes": list(modes), "transports": transports,
                "max_requests": repeats * len(cases) * len(modes) * 2,
                "source_sha256": {c["id"]: sha256_text(c["passage"]) for c in cases},
                "core_sha256": controls.digest(Path(core.__file__)),
                "script_sha256": controls.digest(Path(__file__)),
                "protocol": "Repeat-major, case, mode order, mode order alternates per repeat. One extraction and at "
                            "most one admission per cell, no content retries (transport retries follow the recorded transport), no gold in prompts. Admission JSON validity is "
                            "judged by a literal json.loads only; nothing is repaired or truncated. Technical "
                            "failures stay in the denominator. No accuracy is produced."}
    controls.dump(out / "manifest.json", manifest)
    records = []
    try:
        for repeat in range(repeats):
            order = modes if repeat % 2 == 0 else modes[::-1]
            for case in cases:
                for mode in order:
                    records.append(run_one(core, llms[mode], case, mode, repeat, out))
        summary = summarize(records)
        controls.dump(out / "results.json", summary)
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        controls.dump(out / "manifest.json", manifest)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cases", nargs="+", default=list(DEFAULT_CASES))
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--profile", choices=sorted(PROFILES), default="default")
    args = parser.parse_args(argv)
    from starling import _core

    llms, transports = {}, {}
    for mode in args.modes:
        llms[mode], transports[mode] = base.build_llm(_core, args.model, json_object=(mode == "json_object"),
                                                           **PROFILES[args.profile])
    summary = run(_core, llms, transports, args.out, case_ids=resolve_case_ids(args.cases),
                  repeats=args.repeats, profile=args.profile)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
