#!/usr/bin/env python3
"""离线汇总冻结评测，并在完整同协议运行之间进行网络级配对分析。"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_socialmem_baseline import summarize, TERMINAL_STATUSES


COMMON_CONFIG = (
    "extract_model", "extract_endpoint", "answer_model", "answer_endpoint",
    "embedding_model", "embedding_endpoint", "embedding_dim", "max_retries",
    "timeout_ms", "extract_max_tokens", "answer_max_tokens", "judge_max_tokens",
    "k", "lifecycle", "query_time", "created_at", "seed", "scoring",
)


def check_common_config(base: dict, candidate: dict) -> None:
    changed = [key for key in COMMON_CONFIG if base.get(key) != candidate.get(key)]
    if changed:
        raise ValueError("changed comparison protocol: " + ", ".join(changed))


def index_results(results: list[dict]) -> dict[str, dict]:
    indexed = {}
    for row in results:
        key = str(row["item_id"])
        if key in indexed:
            raise ValueError(f"duplicate archived item: {key}")
        indexed[key] = row
    return indexed


def _complete(record: dict | None) -> bool:
    return record is not None and record.get("status") in TERMINAL_STATUSES


def paired(records: list[dict], baseline: list[dict], candidate: list[dict],
           *, samples: int = 5000, seed: int = 0) -> dict:
    old, new = index_results(baseline), index_results(candidate)
    by_network = defaultdict(lambda: [0, 0])
    wins = losses = old_correct = new_correct = 0
    for record in records:
        key = str(record["item_id"])
        if not _complete(old.get(key)) or not _complete(new.get(key)):
            raise ValueError(f"incomplete paired run: {key}")
        a, b = int(bool(old[key]["correct"])), int(bool(new[key]["correct"]))
        old_correct += a
        new_correct += b
        wins += int(b > a)
        losses += int(b < a)
        group = by_network[record["source"]["network_id"]]
        group[0] += b - a
        group[1] += 1
    if not records or samples < 100:
        raise ValueError("nonempty records and at least 100 bootstrap samples required")
    groups = list(by_network.values())
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        selected = [rng.choice(groups) for _ in groups]
        deltas.append(sum(g[0] for g in selected) / sum(g[1] for g in selected))
    deltas.sort()
    return {
        "total": len(records), "networks": len(groups),
        "baseline_correct": old_correct, "candidate_correct": new_correct,
        "baseline_accuracy": old_correct / len(records),
        "candidate_accuracy": new_correct / len(records),
        "newly_correct": wins, "newly_incorrect": losses,
        "delta": (new_correct - old_correct) / len(records),
        "network_bootstrap_95ci": [deltas[int(.025 * (samples - 1))],
                                   deltas[int(.975 * (samples - 1))]],
        "bootstrap_samples": samples, "bootstrap_seed": seed,
    }


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prompt_hashes(work: Path) -> dict:
    result = {}
    for filename, names in {
        "eval_ladder.py": ("_ladder_prompt", "_ladder_prompt_free"),
        "eval_judge_audit.py": ("_judge_prompt", "_parse_judge_verdict"),
        "eval_longmemeval.py": ("_parse_option_index",),
    }.items():
        tree = ast.parse((work / "frozen/scripts" / filename).read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                result[node.name] = hashlib.sha256(ast.dump(node).encode()).hexdigest()
    if len(result) != 5:
        raise ValueError("missing frozen answer/scoring function")
    return result


def read_run(work: Path) -> tuple[list[dict], list[dict], dict]:
    identity = json.loads((work / "identity.json").read_text())
    for name, key in (("corpus.jsonl", "corpus_sha256"), ("config.json", "config_sha256"),
                      ("scope-manifest.json", "scope_manifest_sha256")):
        if _hash(work / name) != identity[key]:
            raise ValueError(f"changed frozen artifact: {name}")
    records = [json.loads(line) for line in (work / "corpus.jsonl").read_text().splitlines()]
    known = {r["item_id"] for r in records}
    if len(known) != len(records):
        raise ValueError("duplicate corpus identity")
    results = [json.loads(path.read_text()) for path in sorted((work / "runs").glob("*/questions/*.json"))]
    index_results(results)
    for row in results:
        if row["item_id"] not in known:
            raise ValueError("foreign result outside frozen corpus")
        for key in ("corpus_sha256", "config_sha256", "scope_manifest_sha256", "core_sha256"):
            if row.get("fingerprint", {}).get(key) != identity[key]:
                raise ValueError(f"result fingerprint mismatch: {row['item_id']}/{key}")
    return records, results, identity


def extraction_observations(work: Path) -> dict:
    attempts = []
    completed_scopes = failed_scopes = 0
    for directory in sorted((work / "runs").glob("*")):
        finished = (directory / "scope.json").exists()
        failed = (directory / "scope.failure.json").exists()
        completed_scopes += int(finished)
        failed_scopes += int(failed)
        db = directory / "network.db"
        if not db.exists():
            continue
        with sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='extraction_attempt'").fetchone():
                continue
            unique = {}
            for row in conn.execute("SELECT * FROM extraction_attempt"):
                key = (row["pipeline_run_id"], row["attempt_number"])
                current = unique.setdefault(key, {"error": row["error"], "tokens": 0, "latency_ms": 0})
                current["tokens"] += row["total_tokens"] or 0
                current["latency_ms"] = max(current["latency_ms"], row["latency_ms"] or 0)
                current["error"] = current["error"] or row["error"]
            attempts.extend(unique.values())
    return {
        "completed_scopes": completed_scopes, "failed_scopes": failed_scopes,
        "persisted_logical_attempts": len(attempts),
        "persisted_timeout_attempts": sum("Timeout" in str(a["error"]) for a in attempts),
        "observed_total_tokens": sum(a["tokens"] for a in attempts),
        "usage_unknown_attempts": sum(bool(a["error"]) and a["tokens"] == 0 for a in attempts),
        "errors": dict(Counter(a["error"] for a in attempts if a["error"])),
        "counting_limit": "持久化 belief/general_fact 逻辑尝试；不包含不可观察的 episodic 回执，不是完整 HTTP 总量",
    }


def analyze(work: Path, compare: Path | None = None) -> dict:
    records, results, identity = read_run(work)
    summary = summarize(records, results)
    report = {"state": "complete" if summary["executed"] == len(records) else "partial",
              "corpus_sha256": identity["corpus_sha256"], "summary": summary,
              "status_counts": dict(Counter(r["status"] for r in results)),
              "extraction": extraction_observations(work)}
    split_path = work / "network-split.json"
    if split_path.exists():
        split = json.loads(split_path.read_text())
        report["splits"] = {}
        for name, field in (("development", "development_networks"), ("reserved", "reserved_networks")):
            selected = [r for r in records if r["source"]["network_id"] in split[field]]
            report["splits"][name] = summarize(selected, results)
    if compare is not None:
        new_records, new_results, new_identity = read_run(compare)
        if records != new_records or identity["scope_manifest_sha256"] != new_identity["scope_manifest_sha256"]:
            raise ValueError("changed comparison corpus or scope")
        base_config = json.loads((work / "config.json").read_text())
        new_config = json.loads((compare / "config.json").read_text())
        check_common_config(base_config, new_config)
        report["candidate_configuration_changes"] = {
            key: {"baseline": base_config.get(key), "candidate": new_config.get(key)}
            for key in sorted(base_config.keys() | new_config.keys())
            if base_config.get(key) != new_config.get(key)
        }
        if _prompt_hashes(work) != _prompt_hashes(compare):
            raise ValueError("changed comparison answer/scoring prompt")
        report["paired"] = paired(records, results, new_results)
        if split_path.exists():
            report["paired_splits"] = {}
            for name, field in (("development", "development_networks"), ("reserved", "reserved_networks")):
                selected = [r for r in records if r["source"]["network_id"] in split[field]]
                report["paired_splits"][name] = paired(selected, results, new_results)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.work, args.compare)
    target = args.output or args.work / "analysis.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(target)
    print(json.dumps({"state": report["state"],
                      **{key: report["summary"][key] for key in ("total", "executed", "correct", "failed", "unexecuted")},
                      "extraction": report["extraction"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
