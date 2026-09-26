#!/usr/bin/env python3
"""固定开发集k30单变量实验；复用冻结C++核心和评分，不实现检索业务逻辑。"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
PARENT_SEAL = "e3bf3cd1d7fac5958d8f3ced2d94b772271a2d7bec7f0f7f337b17f8fda701bf"
CORE = "6f5dcfac904a77d5402c1f59fecb6b67e00a0d169d1c0ccfba681be0e73dad6f"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def validate_config(parent, candidate):
    expected = {**parent, "k": 30, "http_budget": 1314}
    if (parent.get("core_sha256") != CORE or parent.get("k") != 10
            or parent.get("recall_mode") != "sources"
            or json.dumps(candidate, sort_keys=True) != json.dumps(expected, sort_keys=True)):
        raise ValueError("k30 only permits k and selected-set request budget changes")


def select_records(records, split):
    dev, reserved = set(split["development_networks"]), set(split["reserved_networks"])
    if len(dev) != 33 or len(reserved) != 10 or dev & reserved:
        raise ValueError("development/reserved split changed")
    if len(records) != 1031 or len({r["item_id"] for r in records}) != 1031:
        raise ValueError("canonical question set incomplete or duplicated")
    selected = [r for r in records if r["source"]["network_id"] in dev]
    if (len(selected) != 733 or {r["source"]["network_id"] for r in selected} != dev
            or sum(1 + (r["answer_format"] != "multiple_choice") for r in selected) != 1314):
        raise ValueError("development question selection or request bound changed")
    return selected


def validate_code_delta(parent, candidate):
    if parent["frozen_files"] != candidate["frozen_files"]:
        raise ValueError("k30 requires identical frozen implementation and prompts")


def verify_files(work, files):
    work = Path(work).resolve()
    for name, digest in files.items():
        relative = Path(name)
        path = work / relative
        if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(work):
            raise ValueError("archive path escapes work directory")
        if not path.is_file() or sha(path) != digest:
            raise ValueError(f"artifact hash mismatch: {name}")


def verify_manifest(work, plan):
    files = plan.get("files", {})
    scopes = plan.get("scope_ids", [])
    required = {"run.py", "config.json", "identity.json", "corpus.jsonl", "scope-manifest.json", "network-split.json"}
    required.update(f"runs/{scope}/{name}" for scope in scopes for name in ["scope.json", "frozen.db"])
    if len(scopes) != 39 or len(set(scopes)) != 39 or not required <= files.keys():
        raise ValueError("incomplete k30 source manifest; extraction fallback prohibited")
    verify_files(work, files)
    identity = read(Path(work) / "identity.json")
    if "scripts/run_socialmem_baseline.py" not in identity["frozen_files"]:
        raise ValueError("frozen runner missing")
    for name, digest in identity["frozen_files"].items():
        if files.get("frozen/" + name) != digest:
            raise ValueError("frozen identity omitted from manifest")


def verify_parent(parent):
    if sha(parent / "completion-seal.json") != PARENT_SEAL:
        raise ValueError("k30 baseline parent seal changed")
    seal = read(parent / "completion-seal.json")
    verify_files(parent, seal["files"])
    if (seal["questions"], seal["correct"], seal["ingestion_failures"]) != (1031, 211, 0):
        raise ValueError("parent baseline incomplete")


def load_runner(work):
    scripts = (work / "frozen/scripts").resolve()
    sys.path.insert(0, str(scripts))
    runner = importlib.import_module("run_socialmem_baseline")
    if Path(runner.__file__).resolve() != scripts / "run_socialmem_baseline.py":
        raise ValueError("runner loaded outside frozen directory")
    return runner


def prepare(work, parent):
    work, parent = Path(work).resolve(), Path(parent).resolve()
    verify_parent(parent)
    if work.exists():
        raise ValueError("prepare requires a new directory; existing experiments are never overwritten")
    work.mkdir(parents=True)
    original = read(parent / "identity.json")
    for name in original["frozen_files"]:
        target = work / "frozen" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent / "frozen" / name, target)
    for name in ["corpus.jsonl", "scope-manifest.json", "network-split.json"]:
        shutil.copyfile(parent / name, work / name)
    config = {**read(parent / "config.json"), "k": 30, "http_budget": 1314}
    validate_config(read(parent / "config.json"), config)
    write(work / "config.json", config)
    identity = {**original, "config_sha256": sha(work / "config.json"),
                "parent_baseline_seal_sha256": PARENT_SEAL,
                "candidate_change": "仅k10改k30；预算调整为全部开发题；冻结核心与来源保持"}
    write(work / "identity.json", identity)
    runner = load_runner(work)
    fingerprint = runner._verify_identity(work, config)
    records = runner._read_jsonl(work / "corpus.jsonl")
    selected = select_records(records, read(work / "network-split.json"))
    wanted = {r["item_id"] for r in selected}
    groups = [g for g in runner.prepare_groups(records) if g["records"][0]["item_id"] in wanted]
    assert len(groups) == 39
    for group in groups:
        folder = work / "runs" / group["group_id"]
        folder.mkdir(parents=True)
        old = parent / "runs" / group["group_id"]
        shutil.copyfile(old / "frozen.db", folder / "frozen.db")
        metadata = read(old / "scope.json")
        metadata["fingerprint"] = fingerprint
        write(folder / "scope.json", metadata)
    shutil.copyfile(Path(__file__), work / "run.py")
    for name in ["tests/python/test_k30_controlled_guard.py",
                 "docs/superpowers/specs/2026-09-17-socialmem-k30-controlled-design.md",
                 "docs/superpowers/plans/2026-09-17-socialmem-k30-controlled.md"]:
        target = work / "execution-sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    plan = {"parent_work": str(parent), "parent_seal_sha256": PARENT_SEAL,
            "driver_sha256": sha(work / "run.py"), "core_sha256": CORE,
            "questions": 733, "groups": 39, "http_budget": 1314,
            "scope_ids": [g["group_id"] for g in groups],
            "question_ids": [r["item_id"] for r in selected]}
    plan["files"] = {str(p.relative_to(work)): sha(p) for p in sorted(work.rglob("*"))
                     if p.is_file() and "__pycache__" not in p.parts}
    write(work / "execution-plan.json", plan)


def check(work):
    work = Path(work).resolve()
    plan = read(work / "execution-plan.json")
    if sha(Path(__file__)) != plan["driver_sha256"] or plan["parent_seal_sha256"] != PARENT_SEAL:
        raise ValueError("k30 driver/parent identity changed")
    verify_manifest(work, plan)
    parent = Path(plan["parent_work"])
    verify_parent(parent)
    config, identity = read(work / "config.json"), read(work / "identity.json")
    validate_config(read(parent / "config.json"), config)
    validate_code_delta(read(parent / "identity.json"), identity)
    for name in ["corpus.jsonl", "scope-manifest.json", "network-split.json"]:
        if sha(work / name) != sha(parent / name):
            raise ValueError("k30 input/split differs from baseline")
    runner = load_runner(work)
    fingerprint = runner._verify_identity(work, config)
    records = runner._read_jsonl(work / "corpus.jsonl")
    selected = select_records(records, read(work / "network-split.json"))
    wanted = {r["item_id"] for r in selected}
    groups = [g for g in runner.prepare_groups(records) if g["records"][0]["item_id"] in wanted]
    if ([g["group_id"] for g in groups] != plan["scope_ids"]
            or [r["item_id"] for r in selected] != plan["question_ids"]
            or (plan["questions"], plan["groups"], plan["http_budget"], plan["core_sha256"]) != (733, 39, 1314, CORE)):
        raise ValueError("k30 selected set or execution plan changed")
    for group in groups:
        folder = work / "runs" / group["group_id"]
        if runner.scope_state(folder, fingerprint) != "terminal" or (folder / "scope.failure.json").exists():
            raise ValueError("k30 source snapshot unavailable; extraction prohibited")
        if sha(folder / "frozen.db") != sha(parent / "runs" / group["group_id"] / "frozen.db"):
            raise ValueError("k30 source snapshot changed")
    bound = sum(runner.question_request_bound(r, config, work / "runs" / g["group_id"] / "frozen.db")
                for g in groups for r in g["records"])
    if bound != 1314:
        raise ValueError("k30 native request budget changed")
    return runner, groups


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["prepare", "check", "run"])
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--parent", type=Path, default=ROOT / "build/socialmem_20260917_baseline_recovered")
    args = p.parse_args()
    if args.mode == "prepare":
        prepare(args.work, args.parent)
    runner, groups = check(args.work)
    if args.mode != "run":
        print(json.dumps({"verified": True, "questions": 733, "groups": 39, "http_limit": 1314, "requests": 0}))
        return
    report = runner.run(args.work, groups=groups, workers=4)
    records = [r for g in groups for r in g["records"]]
    results = [r for g in report["groups"] for r in g["results"]]
    summary = runner.summarize(records, results)
    selected = {"state": "complete" if summary["executed"] == 733 else "partial",
                "summary": summary, "ledger": report["ledger"], "scope_ids": [g["group_id"] for g in groups]}
    runner._json_write(args.work / "selected-summary.json", selected)
    print(json.dumps(selected, ensure_ascii=False))


if __name__ == "__main__":
    main()
