#!/usr/bin/env python3
"""R5.2：在同库 v6/v7 上执行 qwen3.8-27B answer/judge QA 对照。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import random
from pathlib import Path
import sqlite3
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICIES = ("legacy", "grounded_memory_v1")
DEFAULT_CONTEXTS = ROOT / "build/socialmem_20260925_r51_same_db_v6_v7"
DEFAULT_OUT = ROOT / "build/socialmem_20260925_r52_v6_v7_qa"
LEDGER_BUDGET = 500


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def validate_policy(policy: str) -> str:
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}: {policy!r}")
    return policy


def validate_reused_receipt(row: dict[str, Any], item_id: str, prompt: str) -> None:
    if row.get("item_id") != item_id:
        raise ValueError("reused receipt item mismatch")
    if row.get("prompt") != prompt:
        raise ValueError("reused receipt prompt mismatch")
    if row.get("terminal") is not True:
        raise ValueError("reused receipt is not terminal")
    if row.get("status") not in ("ok", "invalid_answer", "answer_failure", "judge_failure", "technical_failure"):
        raise ValueError("reused receipt status invalid")


def compare_scores(v6_rows: list[dict[str, Any]], v7_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result = {}
        for row in rows:
            item = str(row.get("item_id", ""))
            if not item or item in result:
                raise ValueError("duplicate or missing item")
            result[item] = row
        return result

    left, right = index(v6_rows), index(v7_rows)
    if set(left) != set(right):
        raise ValueError("item sets do not align")
    transitions = Counter()
    common_normal = []
    rows = []
    for item in sorted(left):
        a, b = left[item], right[item]
        both = a.get("status") == "ok" and b.get("status") == "ok"
        if both:
            if bool(b.get("correct")) and not bool(a.get("correct")):
                transition = "improved"
            elif bool(a.get("correct")) and not bool(b.get("correct")):
                transition = "regressed"
            else:
                transition = "unchanged"
            transitions[transition] += 1
            common_normal.append(item)
        else:
            transition = "technical_or_invalid"
        rows.append({"item_id": item, "v6_status": a.get("status"), "v7_status": b.get("status"),
                     "v6_correct": bool(a.get("correct")), "v7_correct": bool(b.get("correct")),
                     "transition": transition})
    return {
        "questions": len(rows),
        "v6_correct": sum(bool(r.get("correct")) for r in left.values()),
        "v7_correct": sum(bool(r.get("correct")) for r in right.values()),
        "net_v7_minus_v6": sum(bool(r.get("correct")) for r in right.values()) - sum(bool(r.get("correct")) for r in left.values()),
        "common_normal_questions": len(common_normal),
        "common_normal_v6_correct": sum(bool(left[i].get("correct")) for i in common_normal),
        "common_normal_v7_correct": sum(bool(right[i].get("correct")) for i in common_normal),
        "transitions": {key: int(transitions.get(key, 0)) for key in ("improved", "regressed", "unchanged")},
        "rows": rows,
    }


def _bootstrap(records: list[dict[str, Any]], v6: list[dict[str, Any]], v7: list[dict[str, Any]],
               seed: int = 20260925, repetitions: int = 100000) -> dict[str, Any]:
    by_id = {r["item_id"]: r for r in records}
    left, right = {r["item_id"]: r for r in v6}, {r["item_id"]: r for r in v7}
    networks: dict[str, list[str]] = {}
    for record in records:
        network = str(record.get("source", {}).get("network_id") or record.get("network_id") or "unknown")
        networks.setdefault(network, []).append(str(record["item_id"]))
    names = sorted(networks)
    deltas = []
    rng = random.Random(seed)
    for _ in range(repetitions):
        chosen = [names[rng.randrange(len(names))] for _ in names]
        total = correct_delta = 0
        for network in chosen:
            for item in networks[network]:
                total += 1
                correct_delta += int(bool(right[item].get("correct"))) - int(bool(left[item].get("correct")))
        deltas.append(100.0 * correct_delta / total if total else 0.0)
    deltas.sort()
    lo = deltas[int(0.025 * (repetitions - 1))]
    hi = deltas[int(0.975 * (repetitions - 1))]
    return {"seed": seed, "repetitions": repetitions, "networks": names,
            "network_count": len(names), "delta_percent_v7_minus_v6": 100.0 * (sum(bool(r.get("correct")) for r in v7) - sum(bool(r.get("correct")) for r in v6)) / len(records),
            "ci95_percent": [lo, hi]}


def _load_contexts(contexts: Path):
    contexts = Path(contexts).resolve()
    for name in ("execution-plan.json", "comparison.json", "seal.json"):
        if not (contexts / name).is_file():
            raise ValueError(f"R5.1 context artifact missing: {name}")
    r51 = load(ROOT / "scripts/run_socialmem_r51_same_db.py", "r51_for_r52")
    plan = read_json(contexts / "execution-plan.json")
    parent = Path(plan["parent"]).resolve()
    provenance = r51.validate_parent(parent)
    comparison = read_json(contexts / "comparison.json")
    if comparison.get("questions") != 57 or comparison.get("changed_questions") != 57:
        raise ValueError("R5.1 context comparison is incomplete")
    rows: dict[str, list[dict[str, Any]]] = {}
    for arm in ("v6", "v7"):
        paths = sorted((contexts / arm / "recalls").glob("*.json"))
        if len(paths) != 57:
            raise ValueError(f"R5.1 {arm} recall count mismatch")
        rows[arm] = [read_json(path) for path in paths]
        for row in rows[arm]:
            strategy = "evidence_profile_v6" if arm == "v6" else "evidence_profile_v7"
            r51.validate_arm_row(row, strategy, row["database_sha256"], provenance["config"]["core_sha256"])
    records = {str(r["item_id"]): r for r in read_json(parent / "sample.json")}
    if len(records) != 57:
        raise ValueError("sample record count mismatch")
    return contexts, parent, provenance, rows, records


def _frozen_modules(parent: Path):
    r44 = load(parent / "run_socialmem_r44.py", "r44_for_r52")
    runner, config, modules = r44.worker_modules(parent)
    return runner, config, modules


def _v7_receipts(parent: Path, policy: str, records: dict[str, dict], recalls: dict[str, dict],
                 runner, config, core, audit, ladder) -> list[dict[str, Any]]:
    validate_policy(policy)
    if policy == "legacy":
        summary = read_json(parent / "summary.json")
        source = {str(r["item_id"]): r for g in summary["groups"] for r in g["results"]}
    else:
        native = read_json(parent / "native-answer" / "summary.json")
        if native.get("state") != "complete" or native.get("answer_policy") != "grounded_memory_v1":
            raise ValueError("native v7 archive identity mismatch")
        source = {}
        for path in sorted((parent / "native-answer" / "responses").glob("*.json")):
            row = read_json(path)
            source[str(row["item_id"])] = row
    if set(source) != set(records):
        raise ValueError(f"v7 {policy} archive question set mismatch")
    rows = []
    policy_config = {**config, "answer_policy": policy}
    for item_id in sorted(records):
        prompt = runner.answer_prompt(core, ladder, records[item_id], recalls[item_id], policy_config)
        row = dict(source[item_id])
        validate_reused_receipt(row, item_id, prompt)
        row.update({"item_id": item_id, "arm": "v7", "policy": policy,
                    "context_sha256": hashlib.sha256(recalls[item_id]["block"].encode()).hexdigest(),
                    "reused_from": "retry4/summary.json" if policy == "legacy" else "retry4/native-answer"})
        rows.append(row)
    return rows


def _run_policy(out: Path, arm: str, policy: str, records: dict[str, dict], recalls: dict[str, dict],
                runner, config, modules, ledger, adapters=None) -> list[dict[str, Any]]:
    if arm not in ("v6", "v7"):
        raise ValueError(f"unknown QA arm: {arm}")
    validate_policy(policy)
    core, runtime, audit, ladder, _pipeline, longmem = modules
    if adapters is None:
        _, _, answer_llm, judge_llm = runner._make_native_adapters(core, config)
    else:
        _, _, answer_llm, judge_llm = adapters
    policy_config = {**config, "answer_policy": policy}
    rows = []
    arm_dir = out / "answers" / policy / arm
    for item_id in sorted(records):
        record = records[item_id]
        upper = 1 + int(record.get("answer_format", "multiple_choice") != "multiple_choice")
        reservation = ledger.reserve(f"{arm}/{policy}/{item_id}", "answer", upper)
        row: dict[str, Any] = {"item_id": item_id, "arm": arm, "policy": policy,
                               "context_sha256": hashlib.sha256(recalls[item_id]["block"].encode()).hexdigest(),
                               "correct": False, "status": "budget_failure", "terminal": True,
                               "native_attempt_count": 0}
        if reservation.get("state") != "reserved":
            row["error"] = "request budget exhausted"
            write_json(arm_dir / (hashlib.sha256(item_id.encode()).hexdigest() + ".json"), row)
            rows.append(row)
            continue
        try:
            prompt = runner.answer_prompt(core, ladder, record, recalls[item_id], policy_config)
            row["prompt"] = prompt
            payload, text, error = runner.response_text(answer_llm.extract(prompt, ""), "answer")
            row["answer"] = payload
            if error:
                row.update(status="answer_failure", error=error)
            elif record.get("answer_format", "multiple_choice") == "multiple_choice":
                prediction = longmem._parse_option_index(text, len(record["options"]))
                if prediction is None:
                    row.update(status="invalid_answer", error="invalid option")
                else:
                    row.update(status="ok", prediction=prediction, correct=prediction == int(record["answer"]))
            else:
                judge_prompt = audit._judge_prompt(str(record["question"]), str(record["answer"]), text)
                row["judge_prompt"] = judge_prompt
                judge_payload, judge_text, judge_error = runner.response_text(judge_llm.extract(judge_prompt, ""), "judge")
                row["judge"] = judge_payload
                if judge_error:
                    row.update(status="judge_failure", error=judge_error)
                else:
                    row.update(status="ok", correct=bool(audit._parse_judge_verdict(judge_text)))
            row["native_attempt_count"] = sum(runner._response_attempts(row.get(stage)) for stage in ("answer", "judge"))
            row["terminal"] = True
            row["tokens"] = sum(int(row.get(stage, {}).get("response", {}).get("total_tokens", 0)) for stage in ("answer", "judge"))
            ledger.settle(reservation["id"], row["native_attempt_count"])
        except Exception as exc:
            row.update(status="technical_failure", error=f"{type(exc).__name__}: {exc}", budget_unknown=True,
                       native_attempt_count=0)
            ledger.charge_upper(reservation["id"])
        write_json(arm_dir / (hashlib.sha256(item_id.encode()).hexdigest() + ".json"), row)
        rows.append(row)
    return rows


def _run_v6_policy(out: Path, policy: str, records: dict[str, dict], recalls: dict[str, dict],
                   runner, config, modules, ledger) -> list[dict[str, Any]]:
    """兼容旧调用方的 v6 单臂入口。"""
    return _run_policy(out, "v6", policy, records, recalls, runner, config, modules, ledger)


def _summary(rows: list[dict[str, Any]], policy: str, arm: str) -> dict[str, Any]:
    status = Counter(str(r.get("status")) for r in rows)
    requests = Counter()
    tokens = 0
    for row in rows:
        for stage in ("answer", "judge"):
            if stage in row:
                requests[stage] += int(row[stage].get("response", {}).get("attempt_count", 0))
                tokens += int(row[stage].get("response", {}).get("total_tokens", 0))
    return {"policy": policy, "arm": arm, "total": len(rows),
            "correct": sum(bool(r.get("correct")) for r in rows),
            "accuracy": sum(bool(r.get("correct")) for r in rows) / len(rows) if rows else 0.0,
            "status_counts": dict(status), "requests_by_stage": dict(requests),
            "requests": sum(requests.values()), "tokens": tokens}


def build_execution_plan(contexts: Path, parent: Path, config: dict[str, Any], *, fresh_v7: bool) -> dict[str, Any]:
    """生成可审计的 QA 执行计划，明确 v7 是 fresh 生成还是封存复用。"""
    return {
        "contexts": str(Path(contexts).resolve()),
        "parent": str(Path(parent).resolve()),
        "policies": list(POLICIES),
        "answer_model": config["answer_model"],
        "answer_max_tokens": config["answer_max_tokens"],
        "judge_max_tokens": config["judge_max_tokens"],
        "answer_enable_thinking": config.get("answer_enable_thinking"),
        "generated_arms": ["v6", "v7"] if fresh_v7 else ["v6"],
        "reused_arm": None if fresh_v7 else "v7",
        "fresh_v7": bool(fresh_v7),
        "answer_requests": 0,
        "judge_requests": 0,
    }


def run(contexts: Path, out: Path, *, fresh_v7: bool = False) -> dict[str, Any]:
    contexts, parent, provenance, context_rows, records = _load_contexts(contexts)
    out = Path(out).resolve()
    if out.exists():
        raise ValueError(f"output already exists: {out}")
    out.mkdir(parents=True)
    runner, config, modules = _frozen_modules(parent)
    core, _runtime, audit, ladder, _pipe, _longmem = modules
    plan = build_execution_plan(contexts, parent, config, fresh_v7=fresh_v7)
    write_json(out / "execution-plan.json", plan)
    ledger = runner.BudgetLedger(out / "request-ledger.sqlite", LEDGER_BUDGET)
    all_comparisons = {}
    for policy in POLICIES:
        recalls_v6 = {r["item_id"]: r["recall"] for r in context_rows["v6"]}
        recalls_v7 = {r["item_id"]: r["recall"] for r in context_rows["v7"]}
        adapters = runner._make_native_adapters(core, config)
        v6 = _run_policy(out, "v6", policy, records, recalls_v6, runner, config, modules, ledger, adapters)
        if fresh_v7:
            v7 = _run_policy(out, "v7", policy, records, recalls_v7, runner, config, modules, ledger, adapters)
        else:
            v7 = _v7_receipts(parent, policy, records, recalls_v7, runner, config, core, audit, ladder)
        for row in v7:
            write_json(out / "answers" / policy / "v7" / (hashlib.sha256(row["item_id"].encode()).hexdigest() + ".json"), row)
        comparison = compare_scores(v6, v7)
        comparison["bootstrap"] = _bootstrap(list(records.values()), v6, v7)
        comparison["v6_summary"] = _summary(v6, policy, "v6")
        comparison["v7_summary"] = _summary(v7, policy, "v7")
        write_json(out / "answers" / policy / "comparison.json", comparison)
        all_comparisons[policy] = comparison
    snapshot = ledger.snapshot()
    write_json(out / "summary.json", {"state": "complete", "questions": 57, "policies": all_comparisons,
                                      "ledger": snapshot, "parent_core_sha256": provenance["config"]["core_sha256"]})
    return {"state": "complete", "questions": 57, "ledger": snapshot,
            "policies": {p: {k: all_comparisons[p][k] for k in ("v6_correct", "v7_correct", "net_v7_minus_v6", "common_normal_questions", "transitions", "bootstrap")} for p in POLICIES}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contexts", type=Path, default=DEFAULT_CONTEXTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fresh-v7", action="store_true",
                        help="在同一进程内重新执行 v7 answer/judge，不复用 R5.0 回执")
    args = parser.parse_args()
    print(json.dumps(run(args.contexts, args.out, fresh_v7=args.fresh_v7), ensure_ascii=False))


if __name__ == "__main__":
    main()
