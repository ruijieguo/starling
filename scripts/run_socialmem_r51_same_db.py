#!/usr/bin/env python3
"""SocialMemBench R5.1：同一 R5.0 数据库上的 v6/v7 检索上下文对照。

本脚本只编排冻结 provenance、临时 SQLite 副本和 C++ ObserverRetriever。
回答与裁判请求不在本阶段执行；``--embedding dashscope`` 只调用查询 embedding。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / "build/socialmem_20260925_r50_semantic_real_retry4"
DEFAULT_OUT = ROOT / "build/socialmem_20260925_r51_same_db_v6_v7"
STRATEGIES = ("evidence_profile_v6", "evidence_profile_v7")
REQUIRED_PARENT_FILES = (
    "config.json", "identity.json", "scope-manifest.json", "sample.json", "groups.json", "summary.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_strategy(strategy: str) -> str:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}: {strategy!r}")
    return strategy


def validate_parent(parent: Path) -> dict[str, Any]:
    """Validate the complete retry4 identity before loading any adapter."""
    parent = Path(parent).resolve()
    if not parent.is_dir():
        raise ValueError(f"parent directory missing: {parent}")
    missing = [name for name in REQUIRED_PARENT_FILES if not (parent / name).is_file()]
    if missing:
        raise ValueError(f"parent manifest missing: {missing}")
    config = read_json(parent / "config.json")
    identity = read_json(parent / "identity.json")
    if config.get("core_sha256") != identity.get("core_sha256"):
        raise ValueError("identity/config core hash mismatch")
    for name, key in (("config.json", "config_sha256"), ("scope-manifest.json", "scope_manifest_sha256")):
        expected = identity.get(key)
        if not expected or sha256(parent / name) != expected:
            raise ValueError(f"identity {name} hash mismatch")
    frozen = parent / "frozen"
    files = identity.get("frozen_files")
    if not isinstance(files, dict) or not files:
        raise ValueError("identity frozen file manifest missing")
    for relative, expected in files.items():
        path = frozen / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"frozen file hash mismatch: {relative}")
    groups = read_json(parent / "groups.json")
    if len(groups) != 7:
        raise ValueError(f"R5.0 retry4 must contain 7 groups, got {len(groups)}")
    group_ids = []
    for group in groups:
        group_id = str(group.get("group_id", ""))
        if not group_id or group_id in group_ids:
            raise ValueError("group manifest has missing or duplicate group_id")
        group_ids.append(group_id)
        # retry4 的 answer/judge 回执来自 runs/；source-databases 可能是旧复用副本。
        db = parent / "runs" / group_id / "frozen.db"
        if not db.is_file():
            raise ValueError(f"runs source snapshot missing: {group_id}")
        if Path(str(db) + "-wal").exists() or Path(str(db) + "-shm").exists():
            raise ValueError(f"runs source snapshot is not sealed: {group_id}")
    sample = read_json(parent / "sample.json")
    if len(sample) != 57 or {r.get("item_id") for r in sample} != {
        r.get("item_id") for g in groups for r in g.get("records", [])
    }:
        raise ValueError("sample/groups question manifest mismatch")
    return {
        "parent": str(parent),
        "config": config,
        "identity": identity,
        "group_ids": group_ids,
        "sample_count": len(sample),
        "database_sha256": {gid: sha256(parent / "runs" / gid / "frozen.db") for gid in group_ids},
    }


def _validate_recall_shape(recall: dict[str, Any]) -> None:
    if not isinstance(recall, dict) or not isinstance(recall.get("source_refs"), list):
        raise ValueError("recall source_refs missing")
    if not isinstance(recall.get("block"), str):
        raise ValueError("recall block missing")
    if not isinstance(recall.get("source_diagnostics", {}), dict):
        raise ValueError("recall source_diagnostics missing")


def validate_arm_row(row: dict[str, Any], strategy: str, database_sha256: str, core_sha256: str) -> None:
    validate_strategy(strategy)
    if row.get("strategy") != strategy:
        raise ValueError("arm row strategy mismatch")
    if row.get("database_sha256") != database_sha256:
        raise ValueError("arm row database snapshot mismatch")
    if row.get("core_sha256") != core_sha256:
        raise ValueError("arm row core hash mismatch")
    if row.get("terminal") is not True:
        raise ValueError("arm row is not terminal")
    if row.get("status") == "ok":
        _validate_recall_shape(row.get("recall", {}))
    elif row.get("status") != "error":
        raise ValueError("arm row has invalid status")


def _profile(recall: dict[str, Any]) -> dict[str, Any]:
    diagnostics = recall.get("source_diagnostics", {})
    return diagnostics.get("evidence_profile", {}) if isinstance(diagnostics, dict) else {}


def _lane_counts(recall: dict[str, Any]) -> dict[str, int]:
    selected = _profile(recall).get("lane_selected", {})
    return {str(k): int(v) for k, v in selected.items() if isinstance(v, (int, float))}


def compare_rows(v6_rows: list[dict[str, Any]], v7_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result = {}
        for row in rows:
            item_id = str(row.get("item_id", ""))
            if not item_id or item_id in result:
                raise ValueError("question rows missing or duplicate")
            result[item_id] = row
        return result

    left, right = index(v6_rows), index(v7_rows)
    if set(left) != set(right):
        raise ValueError("question rows do not align")
    selected_by: dict[str, int] = {}
    semantic_links = event_candidates = event_selected = 0
    rows = []
    for item_id in sorted(left):
        a, b = left[item_id], right[item_id]
        if a.get("status") != "ok" or b.get("status") != "ok":
            rows.append({"item_id": item_id, "v6_status": a.get("status"), "v7_status": b.get("status"),
                         "source_changed": False, "block_changed": False})
            continue
        ar, br = a["recall"], b["recall"]
        source_a = json.dumps(ar.get("source_refs", []), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        source_b = json.dumps(br.get("source_refs", []), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        source_changed = source_a != source_b
        block_changed = hashlib.sha256(ar["block"].encode()).hexdigest() != hashlib.sha256(br["block"].encode()).hexdigest()
        profile = _profile(br)
        for lane, count in _lane_counts(br).items():
            selected_by[lane] = selected_by.get(lane, 0) + count
        semantic_links += int(profile.get("semantic_links", 0))
        event_candidates += int(profile.get("event_candidates", 0))
        event_selected += int(profile.get("event_selected", 0))
        rows.append({
            "item_id": item_id,
            "source_changed": source_changed,
            "block_changed": block_changed,
            "v6_source_count": len(ar.get("source_refs", [])),
            "v7_source_count": len(br.get("source_refs", [])),
            "v6_block_sha256": hashlib.sha256(ar["block"].encode()).hexdigest(),
            "v7_block_sha256": hashlib.sha256(br["block"].encode()).hexdigest(),
            "v6_lanes": _lane_counts(ar),
            "v7_lanes": _lane_counts(br),
        })
    return {
        "questions": len(rows),
        "changed_questions": sum(r.get("source_changed") or r.get("block_changed") for r in rows),
        "source_changed_questions": sum(bool(r.get("source_changed")) for r in rows),
        "block_changed_questions": sum(bool(r.get("block_changed")) for r in rows),
        "semantic_links_v7": semantic_links,
        "event_candidates_v7": event_candidates,
        "event_selected_v7": event_selected,
        "selected_by_v7": selected_by,
        "rows": rows,
    }


def _load_frozen_modules(parent: Path):
    path = ROOT / "scripts/run_socialmem_r50_offline.py"
    spec = importlib.util.spec_from_file_location("r50_frozen_loader", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.frozen_modules(parent)


def _build_embedder(core: Any, config: dict[str, Any], kind: str):
    if kind == "stub":
        return core.StubEmbeddingAdapter(int(config["embedding_dim"]))
    if kind != "dashscope":
        raise ValueError(f"unsupported embedding kind: {kind}")
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("missing DASHSCOPE_API_KEY")
    old_key, old_base = os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_BASE_URL")
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = str(config["embedding_endpoint"])
    try:
        cfg = core.OpenAIEmbeddingConfig.from_env()
        cfg.model = str(config["embedding_model"])
        cfg.dim = int(config["embedding_dim"])
        cfg.timeout_ms = int(config["timeout_ms"])
        cfg.max_retries = int(config["max_retries"])
        return core.OpenAIEmbeddingAdapter(cfg)
    finally:
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_base is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = old_base


def recall_arm(parent: Path, out: Path, strategy: str, embedding_kind: str, modules=None) -> list[dict[str, Any]]:
    strategy = validate_strategy(strategy)
    provenance = validate_parent(parent)
    parent = Path(parent).resolve()
    config = provenance["config"]
    core, runtime, pipeline = modules or _load_frozen_modules(parent)
    groups = read_json(parent / "groups.json")
    arm = "v6" if strategy.endswith("v6") else "v7"
    arm_dir = Path(out) / arm
    if arm_dir.exists():
        raise ValueError(f"arm output already exists: {arm_dir}")
    (arm_dir / "recalls").mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for group in groups:
        group_id = str(group["group_id"])
        source_db = parent / "runs" / group_id / "frozen.db"
        source_db_sha = sha256(source_db)
        for record in group["records"]:
            item_id = str(record["item_id"])
            row: dict[str, Any] = {
                "item_id": item_id, "group_id": group_id, "strategy": strategy,
                "database_sha256": source_db_sha, "core_sha256": config["core_sha256"],
                "embedding_kind": embedding_kind, "status": "error", "terminal": False,
            }
            try:
                with tempfile.TemporaryDirectory(prefix="socialmem-r51-") as tmp:
                    db = Path(tmp) / "query.db"
                    shutil.copyfile(source_db, db)
                    rt = runtime._build_local_store_sqlite_runtime(db)
                    rt.start()
                    try:
                        holders = sorted({str(turn["speaker"]) for turn in record["history"]})
                        embedder = _build_embedder(core, config, embedding_kind)
                        before = int(getattr(embedder, "request_count", 0))
                        recall = pipeline.recall_observer_block(
                            core, adapter=rt.adapter, embedder=embedder,
                            index=core.SqliteBlobVectorIndex(), question=record["question"],
                            allowed_holders=holders, mode=config["recall_mode"],
                            now_iso=config["query_time"], k=int(config["k"]),
                            max_context_bytes=int(config["max_context_bytes"]),
                            include_unknown_time=bool(config["include_unknown_time"]),
                            source_strategy=strategy,
                            min_source_items=int(config["min_source_items"]),
                            source_seed_k=int(config["source_seed_k"]),
                            source_seed_max_context_bytes=int(config["source_seed_max_context_bytes"]),
                            source_dialogue_radius=int(config["source_dialogue_radius"]),
                        )
                        row.update({"recall": recall, "embedding_requests": int(getattr(embedder, "request_count", 0)) - before,
                                    "status": "ok"})
                    finally:
                        stop = getattr(rt, "stop", None)
                        if callable(stop):
                            stop()
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["terminal"] = True
            validate_arm_row(row, strategy, source_db_sha, config["core_sha256"])
            write_json(arm_dir / "recalls" / (hashlib.sha256(item_id.encode()).hexdigest() + ".json"), row)
            rows.append(row)
    write_json(arm_dir / "summary.json", {
        "strategy": strategy, "embedding_kind": embedding_kind, "rows": len(rows),
        "status_counts": {status: sum(r["status"] == status for r in rows) for status in ("ok", "error")},
        "embedding_requests": sum(int(r.get("embedding_requests", 0)) for r in rows),
    })
    return rows


def reuse_v7_summary(parent: Path, out: Path) -> list[dict[str, Any]]:
    """Reuse v7 contexts already used by retry4 answer/judge receipts."""
    provenance = validate_parent(parent)
    summary = read_json(Path(parent) / "summary.json")
    if summary.get("state") != "complete":
        raise ValueError("retry4 summary is not complete")
    if summary.get("fingerprint", {}).get("core_sha256") != provenance["config"]["core_sha256"]:
        raise ValueError("retry4 summary core hash mismatch")
    by_item: dict[str, dict[str, Any]] = {}
    group_ids = set(provenance["group_ids"])
    for group in summary.get("groups", []):
        group_id = str(group.get("group", ""))
        if group_id not in group_ids:
            raise ValueError("retry4 summary group mismatch")
        for result in group.get("results", []):
            item_id = str(result.get("item_id", ""))
            if not item_id or item_id in by_item:
                raise ValueError("retry4 summary question missing or duplicate")
            if result.get("terminal") is not True or result.get("status") != "ok":
                raise ValueError(f"retry4 v7 result is not healthy: {item_id}")
            row = {
                "item_id": item_id, "group_id": group_id,
                "strategy": "evidence_profile_v7",
                "database_sha256": provenance["database_sha256"][group_id],
                "core_sha256": provenance["config"]["core_sha256"],
                "embedding_kind": "dashscope_reused_retry4",
                "embedding_requests": int(result.get("embedding_request_delta", 0)),
                "status": "ok", "terminal": True, "reused_from": "retry4/summary.json",
                "recall": result["recall"],
            }
            validate_arm_row(row, "evidence_profile_v7", row["database_sha256"], row["core_sha256"])
            by_item[item_id] = row
    if len(by_item) != 57:
        raise ValueError(f"retry4 v7 summary must contain 57 rows, got {len(by_item)}")
    arm_dir = Path(out) / "v7"
    (arm_dir / "recalls").mkdir(parents=True, exist_ok=True)
    rows = [by_item[item_id] for item_id in sorted(by_item)]
    for row in rows:
        write_json(arm_dir / "recalls" / (hashlib.sha256(row["item_id"].encode()).hexdigest() + ".json"), row)
    write_json(arm_dir / "summary.json", {
        "strategy": "evidence_profile_v7", "embedding_kind": "dashscope_reused_retry4",
        "rows": len(rows), "status_counts": {"ok": len(rows), "error": 0},
        "embedding_requests": sum(r["embedding_requests"] for r in rows),
        "reused_from": "retry4/summary.json",
    })
    return rows


def run(parent: Path, out: Path, embedding_kind: str) -> dict[str, Any]:
    parent = Path(parent).resolve()
    out = Path(out).resolve()
    if out.exists():
        raise ValueError(f"output already exists: {out}")
    provenance = validate_parent(parent)
    out.mkdir(parents=True)
    write_json(out / "execution-plan.json", {
        "parent": str(parent), "parent_identity": provenance["identity"],
        "strategies": list(STRATEGIES), "embedding_kind": embedding_kind,
        "generated_strategies": ["evidence_profile_v6"],
        "reused_strategies": ["evidence_profile_v7"],
        "answer_requests": 0, "judge_requests": 0,
    })
    rows = {}
    modules = _load_frozen_modules(parent)
    rows["evidence_profile_v6"] = recall_arm(parent, out, "evidence_profile_v6", embedding_kind, modules=modules)
    rows["evidence_profile_v7"] = reuse_v7_summary(parent, out)
    comparison = compare_rows(rows[STRATEGIES[0]], rows[STRATEGIES[1]])
    write_json(out / "comparison.json", comparison)
    seal_files = {
        "execution-plan.json": sha256(out / "execution-plan.json"),
        "comparison.json": sha256(out / "comparison.json"),
    }
    for arm in ("v6", "v7"):
        seal_files[f"{arm}/summary.json"] = sha256(out / arm / "summary.json")
    write_json(out / "seal.json", {"state": "complete", "files": seal_files, "parent": provenance})
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--embedding", choices=("stub", "dashscope"), default="stub")
    args = parser.parse_args()
    print(json.dumps(run(args.parent, args.out, args.embedding), ensure_ascii=False))


if __name__ == "__main__":
    main()
