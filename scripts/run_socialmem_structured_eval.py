#!/usr/bin/env python3
"""SocialMemBench 结构化声明/来源双臂受控评测入口。

``prepare`` 和 ``check`` 是纯离线操作；只有 ``run`` 才会构造 provider
adapter 并产生 DashScope 请求。每个 arm 都有自己的冻结代码、配置、来源
快照引用、请求账本和结果目录，避免污染历史实验。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "build/socialmem_20260917_source_speaker"
ARMS = ("sources", "statements", "statements_fenced", "hybrid_fenced", "hybrid_dialogue",
        "hybrid_dialogue_expanded", "hybrid_coverage", "hybrid_protocol_retry",
        "hybrid_holder_isolation")
NETWORKS = (
    "grp_0d1e2f3a", "grp_2b3c4d5e", "grp_3c4d5e6f", "grp_4d5e6f7a",
    "grp_9c0d1e2f", "grp_a3b4c5d6",
)
ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QUESTIONS = 57
GROUPS = 7
SOURCE_HTTP_BUDGET = 101
STATEMENT_HTTP_BUDGET = 1200
# The frozen baseline runner is loaded from an isolated path at runtime. Its
# worker function is therefore not importable by multiprocessing's pickle
# protocol; serial execution keeps the frozen module boundary auditable.
EXECUTION_WORKERS = 1


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _live_runner():
    return load_module(ROOT / "scripts/run_socialmem_baseline.py", "structured_live_baseline")


def _frozen_runner(work: Path):
    return load_module(work / "frozen/scripts/run_socialmem_baseline.py",
                       f"structured_frozen_{work.name}")


def select_records(records: list[dict]) -> list[dict]:
    selected = [row for row in records
                if str(row.get("source", {}).get("network_id", "")) in NETWORKS]
    request_bound = sum(1 + int(row.get("answer_format") != "multiple_choice")
                        for row in selected)
    if (len(selected) != QUESTIONS
            or len({str(row.get("item_id")) for row in selected}) != QUESTIONS
            or len({str(row["source"]["network_id"]) for row in selected}) != len(NETWORKS)
            or request_bound != SOURCE_HTTP_BUDGET):
        raise ValueError("structured evaluation question set changed")
    return selected


def select_groups(runner, records: list[dict]) -> list[dict]:
    selected = select_records(records)
    wanted = {str(row["item_id"]) for row in selected}
    groups = runner.prepare_groups(records)
    groups = [group for group in groups
              if any(str(row["item_id"]) in wanted for row in group["records"])]
    if (len(groups) != GROUPS
            or sum(len(group["records"]) for group in groups) != QUESTIONS
            or sum(1 + int(row.get("answer_format") != "multiple_choice")
                   for group in groups for row in group["records"]) != SOURCE_HTTP_BUDGET):
        raise ValueError("structured evaluation scope set changed")
    if any(str(row["item_id"]) not in wanted for group in groups for row in group["records"]):
        raise ValueError("structured evaluation selected an out-of-scope question")
    return groups


def arm_config(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm}")
    recall_mode = ("sources" if arm == "sources" else
                   "hybrid" if arm in ("hybrid_fenced", "hybrid_dialogue", "hybrid_dialogue_expanded", "hybrid_coverage", "hybrid_protocol_retry", "hybrid_holder_isolation")
                   else "statements")
    structured = arm != "sources"
    config = {
        "arm": arm,
        "extract_model": "qwen3.8-27b",
        "extract_endpoint": ENDPOINT,
        "extract_provider": "dashscope",
        "extract_enable_thinking": False,
        "extract_max_tokens": 8192 if structured else 4096,
        "answer_model": "qwen3.8-27b",
        "answer_endpoint": ENDPOINT,
        "answer_key_env": "DASHSCOPE_API_KEY",
        "answer_enable_thinking": False,
        "answer_max_tokens": 512,
        "judge_max_tokens": 64,
        "embedding_model": "qwen3.7-text-embedding",
        "embedding_endpoint": ENDPOINT,
        "embedding_dim": 1024,
        "embedding_max_batch_inputs": 10,
        "max_retries": 0,
        "timeout_ms": 120000,
        "k": 10,
        "max_context_bytes": 8000,
        "lifecycle": "sleep",
        "query_time": "2026-12-08T00:00:00Z",
        "created_at": "2026-06-01T00:00:00Z",
        "workers": 4,
        "http_budget": (SOURCE_HTTP_BUDGET if arm == "sources" else STATEMENT_HTTP_BUDGET),
        "recall_mode": recall_mode,
        "retain_sources": True,
        "preserve_invalid_time": True,
        "include_unknown_time": True,
        "answer_policy": "legacy",
        "source_strategy": ("focused_coverage" if arm in ("hybrid_coverage", "hybrid_holder_isolation")
                             else "focused_dialogue" if arm in ("hybrid_dialogue", "hybrid_dialogue_expanded")
                             else "bm25"),
        "semantic_claim_contract": structured,
        "preserve_text_objects": structured,
        "claim_output_mode": "json_object" if structured else "legacy",
        "claim_allow_code_fence": arm in ("statements_fenced", "hybrid_fenced", "hybrid_dialogue",
                                           "hybrid_dialogue_expanded", "hybrid_coverage", "hybrid_protocol_retry",
                                           "hybrid_holder_isolation"),
        "claim_protocol_retry_budget": 1 if arm == "hybrid_protocol_retry" else 0,
        "holder_isolation": arm == "hybrid_holder_isolation",
        "scoring": "existing_ladder_mc_and_single_yes_no_local_protocol",
    }
    if arm == "hybrid_dialogue_expanded":
        config.update(source_seed_k=5, source_seed_max_context_bytes=4000,
                      source_dialogue_radius=2)
    if arm == "hybrid_coverage":
        config.update(min_source_items=7, source_seed_k=5,
                      source_seed_max_context_bytes=4000, source_dialogue_radius=1)
    if arm == "hybrid_protocol_retry":
        # R3.4 changes only the native protocol retry budget. Keep the R3.3
        # focused-coverage source configuration identical for paired analysis.
        config.update(min_source_items=7, source_seed_k=5,
                      source_seed_max_context_bytes=4000, source_dialogue_radius=1)
    if arm == "hybrid_holder_isolation":
        config.update(min_source_items=7, source_seed_k=5,
                      source_seed_max_context_bytes=4000, source_dialogue_radius=1,
                      claim_protocol_retry_budget=1)
    return config

def validate_arm_config(arm: str, config: dict) -> None:
    expected = arm_config(arm)
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"{arm} configuration drift: {key}")


def _copy_tree(src: Path, dst: Path) -> None:
    for path in src.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.name.endswith(".pyc"):
            continue
        relative = path.relative_to(src)
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _run_fingerprint(identity: dict) -> dict:
    return {
        "corpus_sha256": identity["corpus_sha256"],
        "config_sha256": identity["config_sha256"],
        "scope_manifest_sha256": identity["scope_manifest_sha256"],
        "core_sha256": identity["core_sha256"],
        "frozen_files_sha256": hashlib.sha256(
            json.dumps(identity["frozen_files"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def _frozen_files(work: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in (work / "frozen").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc"):
            files[str(path.relative_to(work / "frozen"))] = sha(path)
    return dict(sorted(files.items()))


def _copy_frozen_runtime(work: Path) -> None:
    frozen = work / "frozen"
    _copy_tree(ROOT / "python/starling", frozen / "python/starling")
    import starling._core as core
    core_target = frozen / "python/starling" / Path(core.__file__).name
    core_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(core.__file__, core_target)
    for name in ("run_socialmem_baseline.py", "eval_judge_audit.py", "eval_ladder.py",
                 "eval_ladder_pipeline.py", "eval_longmemeval.py", "eval_adapters.py"):
        target = frozen / "scripts" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts" / name, target)


def _copy_inputs(work: Path) -> None:
    for name in ("corpus.jsonl", "scope-manifest.json", "network-split.json"):
        shutil.copy2(PARENT / name, work / name)


def _copy_source_snapshot(parent: Path, work: Path, groups: list[dict], fingerprint: dict) -> None:
    for group in groups:
        group_id = group["group_id"]
        source_dir = parent / "runs" / group_id
        if not (source_dir / "frozen.db").is_file():
            # A structured parent may have a technical scope failure and
            # therefore no terminal runs/<group>/frozen.db.  Its immutable
            # source snapshot remains the authorized input for the next arm.
            source_dir = parent / "source-snapshots" / group_id
        if not (source_dir / "frozen.db").is_file():
            raise ValueError(f"source snapshot missing: {group_id}")
        target = work / "source-snapshots" / group_id
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_dir / "frozen.db", target / "frozen.db")
        metadata = read_json(source_dir / "scope.json")
        metadata["fingerprint"] = fingerprint
        write_json(target / "scope.json", metadata)


def _write_sources_scope(work: Path, groups: list[dict], fingerprint: dict) -> None:
    for group in groups:
        group_id = group["group_id"]
        source = work / "source-snapshots" / group_id
        target = work / "runs" / group_id
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / "frozen.db", target / "frozen.db")
        write_json(target / "scope.json", read_json(source / "scope.json"))


def prepare_arm(work: Path, arm: str, parent: Path = PARENT) -> None:
    work = Path(work).resolve()
    parent = Path(parent).resolve()
    if work.exists():
        raise ValueError("prepare refuses to overwrite an existing experiment directory")
    if not (parent / "corpus.jsonl").is_file():
        raise ValueError(f"source parent missing: {parent}")
    records = [json.loads(line) for line in (parent / "corpus.jsonl").read_text().splitlines() if line]
    config = arm_config(arm)
    work.mkdir(parents=True)
    _copy_inputs(work)
    _copy_frozen_runtime(work)
    shutil.copy2(Path(__file__), work / "run.py")
    write_json(work / "config.json", config)
    import starling._core as core
    identity = {
        "created_at": "2026-09-19T00:00:00+08:00",
        "core_path": str(Path(core.__file__).resolve()),
        "core_sha256": sha(Path(core.__file__)),
        "corpus_sha256": sha(work / "corpus.jsonl"),
        "scope_manifest_sha256": sha(work / "scope-manifest.json"),
        "source_parent": str(parent),
        "source_parent_identity_sha256": sha(parent / "identity.json"),
        "questions": QUESTIONS,
        "groups": GROUPS,
        "frozen_files": _frozen_files(work),
    }
    config["core_sha256"] = identity["core_sha256"]
    write_json(work / "config.json", config)
    identity["config_sha256"] = sha(work / "config.json")
    write_json(work / "identity.json", identity)
    fingerprint = _run_fingerprint(identity)
    runner = _frozen_runner(work)
    groups = select_groups(runner, records)
    _copy_source_snapshot(parent, work, groups, fingerprint)
    if arm == "sources":
        _write_sources_scope(work, groups, fingerprint)
    plan = {
        "arm": arm,
        "parent_work": str(parent),
        "parent_identity_sha256": sha(parent / "identity.json"),
        "driver_sha256": sha(work / "run.py"),
        "core_sha256": identity["core_sha256"],
        "questions": QUESTIONS,
        "groups": GROUPS,
        "http_budget": config["http_budget"],
        "scope_ids": [group["group_id"] for group in groups],
        "question_ids": [row["item_id"] for row in select_records(records)],
        "files": {},
    }
    plan["files"] = _manifest_files(work)
    write_json(work / "execution-plan.json", plan)


def _manifest_files(work: Path) -> dict[str, str]:
    excluded = {"execution-plan.json"}
    files = {}
    for path in sorted(work.rglob("*")):
        if path.is_file() and path.name not in excluded and "__pycache__" not in path.parts:
            files[str(path.relative_to(work))] = sha(path)
    return files


def _verify_files(work: Path, files: dict[str, str]) -> None:
    for name, expected in files.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"invalid manifest path: {name}")
        actual = work / path
        if not actual.is_file() or sha(actual) != expected:
            raise ValueError(f"manifest artifact mismatch: {name}")


def _validate_structured_scope(scope_dir: Path, group: dict) -> None:
    """评测覆盖门禁；空声明合法，仅来源和缺失 holder 不能冒充结构化执行。"""
    if not scope_dir.exists():
        return  # 尚未开始，可以按当前冻结配置执行抽取。
    failure = scope_dir / "scope.failure.json"
    if failure.is_file():
        metadata = read_json(failure)
        if metadata.get("group") != group["group_id"]:
            raise ValueError("structured scope failure identity mismatch")
        # A terminal extraction failure is a scored technical failure.  It is
        # not a completed structured scope, but it must remain auditable and
        # must not be mistaken for a missing/unstarted scope.
        return
    if not (scope_dir / "scope.json").is_file() or not (scope_dir / "frozen.db").is_file():
        raise ValueError("incomplete structured scope artifacts")
    metadata = read_json(scope_dir / "scope.json")
    expected = {str(turn.get("speaker") or "unknown").strip() or "unknown"
                for turn in group["history"]}
    extraction = metadata.get("extraction")
    if (metadata.get("group") != group["group_id"]
            or metadata.get("ingestion_mode") == "source_only"
            or not isinstance(extraction, list)):
        raise ValueError("structured scope has no structured ingestion")
    holders = [row.get("holder") for row in extraction if isinstance(row, dict)]
    if len(holders) != len(extraction) or len(holders) != len(expected) or set(holders) != expected:
        raise ValueError("structured scope holder coverage mismatch")
    scope_state = metadata.get("scope_state", "complete")
    if scope_state not in ("complete", "partial"):
        raise ValueError("structured scope state invalid")
    failures = metadata.get("holder_failures", [])
    failure_holders = {str(row.get("holder")) for row in failures if isinstance(row, dict)}
    if scope_state == "partial" and not failure_holders:
        raise ValueError("partial structured scope has no holder failures")
    for row in extraction:
        failed = row.get("extraction_failed") is True
        if (row.get("source_preserved") is not True
                or not isinstance(row.get("catalog_version"), str)
                or not row["catalog_version"]
                or row.get("outcome") not in ("accepted", "idempotent")
                or (failed and (scope_state != "partial" or row.get("holder") not in failure_holders
                                or not row.get("failure_category")))
                or (not failed and row.get("extraction_failed") is not False)):
            raise ValueError("structured scope extraction is failed or unverified")


def check_arm(work: Path, parent: Path = PARENT):
    work = Path(work).resolve()
    plan = read_json(work / "execution-plan.json")
    arm = plan.get("arm")
    if arm not in ARMS:
        raise ValueError("unknown structured evaluation arm")
    if sha(work / "run.py") != plan.get("driver_sha256") or sha(Path(__file__)) != plan.get("driver_sha256"):
        raise ValueError("structured evaluation driver drift")
    _verify_files(work, plan.get("files", {}))
    config, identity = read_json(work / "config.json"), read_json(work / "identity.json")
    validate_arm_config(arm, config)
    if config.get("core_sha256") != plan.get("core_sha256"):
        raise ValueError("core identity drift")
    if sha(parent / "identity.json") != plan.get("parent_identity_sha256"):
        raise ValueError("source parent identity drift")
    records = [json.loads(line) for line in (work / "corpus.jsonl").read_text().splitlines() if line]
    select_records(records)
    runner = _frozen_runner(work)
    fingerprint = runner._verify_identity(work, config)
    groups = select_groups(runner, records)
    if [group["group_id"] for group in groups] != plan.get("scope_ids"):
        raise ValueError("structured evaluation scope order drift")
    if plan.get("question_ids") != [row["item_id"] for row in select_records(records)]:
        raise ValueError("structured evaluation question order drift")
    # Both arms carry the same immutable source snapshots. The statements arm
    # keeps them under source-snapshots and builds its own native statement DB.
    for group in groups:
        if arm != "sources":
            _validate_structured_scope(work / "runs" / group["group_id"], group)
        source = work / "source-snapshots" / group["group_id"]
        if runner.scope_state(source, fingerprint) != "terminal":
            raise ValueError("source snapshot is not terminal")
        parent_source = parent / "runs" / group["group_id"]
        if not (parent_source / "frozen.db").is_file():
            parent_source = parent / "source-snapshots" / group["group_id"]
        if sha(source / "frozen.db") != sha(parent_source / "frozen.db"):
            raise ValueError("source snapshot differs from parent")
        if arm == "sources":
            scope = work / "runs" / group["group_id"]
            if runner.scope_state(scope, fingerprint) != "terminal":
                raise ValueError("sources arm scope is not terminal")
            if sha(scope / "frozen.db") != sha(source / "frozen.db"):
                raise ValueError("sources arm snapshot differs from source snapshot")
    return runner, groups, config, identity


def refresh_manifest(work: Path) -> None:
    plan = read_json(work / "execution-plan.json")
    plan["files"] = _manifest_files(work)
    write_json(work / "execution-plan.json", plan)


def run_arm(work: Path, parent: Path = PARENT) -> dict:
    runner, groups, config, _ = check_arm(work, parent)
    report = runner.run(work, groups=groups, workers=EXECUTION_WORKERS)
    refresh_manifest(Path(work))
    selected_records = [row for group in groups for row in group["records"]]
    result_rows = [row for group in report["groups"] for row in group["results"]]
    summary = runner.summarize(selected_records, result_rows)
    selected = {
        "arm": config["arm"],
        "state": "complete" if summary["executed"] == QUESTIONS else "partial",
        "summary": summary,
        "ledger": report["ledger"],
        "scope_ids": [group["group_id"] for group in groups],
    }
    write_json(Path(work) / "selected-summary.json", selected)
    refresh_manifest(Path(work))
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "check", "run"))
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--parent", type=Path, default=PARENT)
    args = parser.parse_args(argv)
    if args.mode == "prepare":
        prepare_arm(args.work, args.arm, args.parent)
        print(json.dumps({"prepared": True, "arm": args.arm, "questions": QUESTIONS,
                          "groups": GROUPS, "http_budget": arm_config(args.arm)["http_budget"]}))
        return 0
    check_arm(args.work, args.parent)
    if args.mode == "check":
        print(json.dumps({"verified": True, "arm": args.arm, "questions": QUESTIONS,
                          "groups": GROUPS, "http_budget": arm_config(args.arm)["http_budget"],
                          "requests": 0}))
        return 0
    print(json.dumps(run_arm(args.work, args.parent), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
