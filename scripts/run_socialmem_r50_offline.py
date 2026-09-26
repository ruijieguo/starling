#!/usr/bin/env python3
"""R5.0 只读离线检索：用冻结 R4.9 source DB 和 StubEmbeddingAdapter 比较 v7。"""
from __future__ import annotations
import argparse
import atexit
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "build/socialmem_20260924_r49b_topic_member_offline"
OUT_DEFAULT = ROOT / "build/socialmem_20260924_r50_semantic_offline"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def frozen_modules(work: Path):
    """Load frozen R4.9 orchestration with the current candidate C++ core.

    The parent archive intentionally contains its own v6 ``_core``.  Loading
    that extension would make this candidate a no-op, so stage only the small
    frozen import tree in a temporary directory and replace its extension with
    the freshly built current one.  The parent archive remains byte-for-byte
    untouched; the staged config/identity hashes are updated together so the
    archive loader still enforces provenance.
    """
    current = sorted((ROOT / "build/python/starling").glob("_core*.so"))
    if not current:
        raise RuntimeError("current build/python/starling/_core*.so is missing")
    staged = Path(tempfile.mkdtemp(prefix="r50-frozen-"))
    atexit.register(shutil.rmtree, staged, ignore_errors=True)
    shutil.copytree(work / "frozen", staged / "frozen")
    for name in ("config.json", "identity.json", "scope-manifest.json"):
        shutil.copyfile(work / name, staged / name)
    staged_core = sorted((staged / "frozen/python/starling").glob("_core*.so"))
    if len(staged_core) != 1:
        raise RuntimeError("frozen archive must contain exactly one _core extension")
    shutil.copyfile(current[0], staged_core[0])
    staged_config = json.loads((staged / "config.json").read_text())
    staged_config["core_sha256"] = sha(current[0])
    write(staged / "config.json", staged_config)
    staged_identity = json.loads((staged / "identity.json").read_text())
    staged_identity["config_sha256"] = sha(staged / "config.json")
    relative_core = staged_core[0].relative_to(staged / "frozen").as_posix()
    staged_identity["frozen_files"][relative_core] = sha(staged_core[0])
    write(staged / "identity.json", staged_identity)
    sys.path.insert(0, str(staged / "frozen/python"))
    baseline = load(staged / "frozen/scripts/run_socialmem_baseline.py", "r50_offline_baseline")
    imports = baseline._frozen_imports(staged, staged_config, staged_identity)
    core, runtime, _, _, pipeline, _ = imports
    return core, runtime, pipeline


def recall(work: Path, out: Path, embedding_kind: str = "stub"):
    if out.exists():
        raise RuntimeError(f"output already exists: {out}")
    sample = json.loads((work / "sample.json").read_text())
    groups = json.loads((work / "groups.json").read_text())
    config = json.loads((work / "config.json").read_text())
    core, runtime, pipeline = frozen_modules(work)
    records_by_group = {g["group_id"]: g for g in groups}
    out.mkdir(parents=True)
    for name in ("sample.json", "groups.json", "network-split.json", "corpus.jsonl", "scope-manifest.json"):
        shutil.copyfile(work / name, out / name)
    candidate_config = {**config, "arm": "r50_semantic_event", "source_strategy": "evidence_profile_v7"}
    write(out / "config.json", candidate_config)
    write(out / "parent-config.json", config)
    write(out / "identity.json", {
        "core_sha256": sha(ROOT / "build/python/starling/_core.cpython-314-darwin.so"),
        "parent_core_sha256": config["core_sha256"],
        "parent": str(work),
        "source_databases": {
            g["group_id"]: sha(work / "source-databases" / g["group_id"] / "frozen.db") for g in groups
        },
    })
    if embedding_kind == "stub":
        embedding_factory = lambda: core.StubEmbeddingAdapter(1024)
    elif embedding_kind == "dashscope":
        # The live candidate uses the same C++ OpenAI-compatible adapter as the
        # production runner.  Python only selects the provider and records its
        # request count; query embedding and all semantic selection stay native.
        def build_dashscope_embedder():
            saved_key = os.environ.get("OPENAI_API_KEY")
            saved_base = os.environ.get("OPENAI_BASE_URL")
            os.environ["OPENAI_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
            os.environ["OPENAI_BASE_URL"] = os.environ.get(
                "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            try:
                cfg = core.OpenAIEmbeddingConfig.from_env()
                cfg.model = os.environ.get("EMBEDDING_MODEL", "qwen3.7-text-embedding")
                cfg.dim = int(os.environ.get("EMBEDDING_DIM", "1024"))
                cfg.max_retries = 0
                cfg.timeout_ms = 120000
                return core.OpenAIEmbeddingAdapter(cfg)
            finally:
                if saved_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = saved_key
                if saved_base is None:
                    os.environ.pop("OPENAI_BASE_URL", None)
                else:
                    os.environ["OPENAI_BASE_URL"] = saved_base
        embedding_factory = build_dashscope_embedder
    else:
        raise ValueError(f"unsupported embedding kind: {embedding_kind}")
    total_network_requests = 0
    for group in groups:
        group_dir = work / "source-databases" / group["group_id"]
        for record in group["records"]:
            with tempfile.TemporaryDirectory(prefix="r50-offline-") as tmp:
                db = Path(tmp) / "query.db"
                shutil.copyfile(group_dir / "frozen.db", db)
                rt = runtime._build_local_store_sqlite_runtime(db)
                rt.start()
                holders = sorted({str(t["speaker"]) for t in record["history"]})
                embedding = embedding_factory()
                before_requests = int(getattr(embedding, "request_count", 0))
                result = pipeline.recall_observer_block(
                    core, adapter=rt.adapter, embedder=embedding,
                    index=core.SqliteBlobVectorIndex(), question=record["question"],
                    allowed_holders=holders, mode="hybrid", now_iso=config["query_time"],
                    k=config["k"], max_context_bytes=config["max_context_bytes"],
                    include_unknown_time=config["include_unknown_time"],
                    source_strategy="evidence_profile_v7", min_source_items=config["min_source_items"],
                    source_seed_k=config["source_seed_k"],
                    source_seed_max_context_bytes=config["source_seed_max_context_bytes"],
                    source_dialogue_radius=config["source_dialogue_radius"])
                row = {"item_id": record["item_id"], "group_id": group["group_id"],
                       "status": "ok", "terminal": True,
                       "embedding_requests": int(getattr(embedding, "request_count", 0))-before_requests,
                       "embedding_kind": embedding_kind,
                       "recall": result}
                total_network_requests += row["embedding_requests"]
                write(out / "recalls" / (hashlib.sha256(record["item_id"].encode()).hexdigest() + ".json"), row)
    recall_files = {str(p.relative_to(out)): sha(p) for p in sorted((out / "recalls").glob("*.json"))}
    write(out / "recall-seal.json", {"questions": len(sample), "files": recall_files,
                                    "status_counts": {"ok": len(sample)},
                                    "network_requests": total_network_requests,
                                    "embedding_kind": embedding_kind})
    return {"questions": len(sample), "network_requests": total_network_requests,
            "embedding_kind": embedding_kind, "output": str(out)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=PARENT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--embedding", choices=("stub", "dashscope"), default="stub")
    args = parser.parse_args()
    print(json.dumps(recall(args.parent.resolve(), args.out.resolve(), args.embedding), ensure_ascii=False))


if __name__ == "__main__":
    main()
