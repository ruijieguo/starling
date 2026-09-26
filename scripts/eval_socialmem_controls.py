#!/usr/bin/env python3
"""Paired SocialMemBench diagnostics from a completed probe's frozen databases."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit, urlunsplit

import eval_judge_audit as audit
import eval_ladder as ladder

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("star_immediate", "star_sleep", "rag_legacy", "rag_speakers")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def frozen_database_hash(path: Path) -> str:
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError(f"source archive has an uncheckpointed WAL: {path.name}")
    return digest(path)


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def backup_database(source: Path, target: Path) -> None:
    # Exclusive creation prevents accidental overwrite of an archive or source.
    target.touch(exist_ok=False)
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)


def snapshot(path: Path) -> dict:
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"database integrity check failed: {path.name}")
        rows = [dict(r) for r in conn.execute(
            "SELECT id,tenant_id,holder_id,subject_id,predicate,object_value,modality,"
            "provenance,review_status,consolidation_state,replay_count,created_at,"
            "updated_at,observed_at FROM statements WHERE tenant_id='default' ORDER BY id")]
        vectors = [dict(r) for r in conn.execute(
            "SELECT model,dim,status,COUNT(*) AS count FROM statement_vectors "
            "WHERE tenant_id='default' GROUP BY model,dim,status")]
    return {
        "statement_count": len(rows),
        "state_review_eligible": sum(
            r["consolidation_state"] in ("consolidated", "archived") and
            r["review_status"] not in ("rejected", "pending_review") for r in rows),
        "states": dict(Counter(r["consolidation_state"] for r in rows)),
        "reviews": dict(Counter(r["review_status"] for r in rows)),
        "vectors": vectors, "statements": rows,
    }


def evaluate_variant(record: dict, variant: str, source_db: Path, config: dict) -> dict:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    frozen = variant.startswith("star_")
    before = None
    make_pipeline = config["make_pipeline"]

    def make_copy(db_path):
        nonlocal before
        if frozen:
            backup_database(source_db, Path(db_path))
            before = snapshot(Path(db_path))
        return make_pipeline(db_path)

    trace = {}
    run_config = {**config, "make_pipeline": make_copy, "diagnostics": trace,
                  "star_replay_mode": "sleep" if variant == "star_sleep" else "immediate",
                  "rag_speaker_labels": variant == "rag_speakers"}
    if frozen:
        run_config["extract"] = lambda adapter, item, backbone: None
    started = time.perf_counter()
    ok = ladder._real_answer("S_star" if frozen else "S_rag", record, 0, run_config)
    return {"item_id": record["item_id"], "variant": variant, "ok": ok,
            "wall_seconds": time.perf_counter() - started,
            "before": before, "after": snapshot(Path(trace["db_path"])), "trace": trace}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-run", action="store_true", required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now-iso", required=True)
    parser.add_argument("--backbone", default="gpt-5.5")
    parser.add_argument("--chat-api-path", default="/v1")
    parser.add_argument("--judge-controls", type=Path)
    args = parser.parse_args(argv)
    from starling import _core

    parent = json.loads((args.probe / "manifest.json").read_text())
    corpus = audit.load_corpus(args.probe / "corpus.jsonl")
    if parent["status"] != "complete" or ladder.corpus_hash(corpus) != parent["corpus_hash"]:
        raise ValueError("expected a completed probe with matching corpus fingerprint")
    if digest(Path(_core.__file__)) != parent["core_sha256"]:
        raise ValueError("the frozen-ingest control requires the source probe's core binary")
    if [r["item_id"] for r in corpus] != [r["id"] for r in parent["items"]]:
        raise ValueError("probe item manifest does not match corpus")
    sources = {r["item_id"]: args.probe / "databases" / f"{r['item_id']}.db" for r in corpus}
    source_hashes = {key: frozen_database_hash(path) for key, path in sources.items()}
    args.now_iso = ladder.normalize_eval_time(args.now_iso)
    query_time = datetime.fromisoformat(args.now_iso)
    for path in sources.values():
        state = snapshot(path)
        for row in state["statements"]:
            for field in ("created_at", "updated_at"):
                if datetime.fromisoformat(row[field]) > query_time:
                    raise ValueError("query time precedes a frozen database write")
        if any(v["model"] != parent["config"]["embedder"] or
               v["dim"] != parent["embedding_dim"] or v["status"] != "embedded"
               for v in state["vectors"]):
            raise ValueError("stored vectors do not match the probe embedding configuration")

    controls = []
    for record in corpus:
        if record["answer_format"] != "multiple_choice":
            controls.extend([
                {"item_id": record["item_id"], "kind": "exact_reference",
                 "candidate": record["answer"], "expected": True},
                {"item_id": record["item_id"], "kind": "no_answer",
                 "candidate": "I don't know.", "expected": False},
            ])
    if args.judge_controls:
        controls.extend(json.loads(args.judge_controls.read_text()))
    by_id = {r["item_id"]: r for r in corpus}
    for control in controls:
        if control["item_id"] not in by_id or not isinstance(control["expected"], bool):
            raise ValueError("invalid judge control")

    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "databases").mkdir()
    dump(args.out / "corpus.json", corpus)
    dump(args.out / "judge_control_inputs.json", controls)
    base_url = urlsplit(os.environ["OPENAI_BASE_URL"])
    os.environ["OPENAI_BASE_URL"] = urlunsplit(base_url._replace(path=args.chat_api_path))
    os.environ["EMBEDDING_MODEL"] = parent["config"]["embedder"]
    os.environ["EMBEDDING_DIM"] = str(parent["embedding_dim"])
    config = ladder.build_real_config(
        _core, parent["config"]["k"], [0], "off", [args.backbone],
        parent["config"]["embedder"], extract_model=parent["config"]["extract_model"],
        extract_provider=parent["config"]["extract_provider"])
    config.update(backbone=args.backbone, now_iso=args.now_iso)
    source_files = [Path(__file__), ROOT / "scripts/eval_ladder.py",
                    ROOT / "scripts/eval_ladder_pipeline.py", ROOT / "scripts/eval_judge_audit.py"]
    code_archive = args.out / "source_archive"
    code_archive.mkdir()
    for path in source_files:
        shutil.copyfile(path, code_archive / path.name)
    manifest = {
        "status": "running", "claim_level": "diagnostic_only",
        "protocol": "frozen-ingest-native-sleep-speaker-rag-v1", "variants": list(VARIANTS),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in source_files},
        "core_sha256": digest(Path(_core.__file__)),
        "parent_manifest_sha256": digest(args.probe / "manifest.json"),
        "source_database_sha256": source_hashes, "parent_probe": str(args.probe.resolve()),
        "parent_config": parent["config"], "config": ladder._serializable_config(config),
        "corpus_hash": ladder.corpus_hash(corpus), "chat_api_path": args.chat_api_path,
        "judge_controls_sha256": digest(args.out / "judge_control_inputs.json"),
        "embedding_dim": parent["embedding_dim"], "seed": 0,
        "lifecycle": "One run_sleep with native defaults, llm=None; frozen post-query source snapshots.",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    dump(args.out / "manifest.json", manifest)
    observations = []
    judge_calls = []

    def judge(question, reference, candidate, backbone):
        prompt = audit._judge_prompt(question, reference, candidate)
        raw = audit._chat_completion(prompt, backbone, max_tokens=8)
        accepted = audit._parse_judge_verdict(raw)
        receipt = {"question": question, "reference": reference, "candidate": candidate,
                   "prompt": prompt, "raw": raw, "accepted": accepted}
        judge_calls.append(receipt)
        ladder.append_journal(args.out / "judge_calls.jsonl", receipt)
        return accepted

    config["judge"] = judge
    try:
        for record in corpus:
            for variant in VARIANTS:
                print(f"[controls] {record['item_id']} {variant}", flush=True)
                judge_start = len(judge_calls)
                row = evaluate_variant(record, variant, sources[record["item_id"]], config)
                archive = args.out / "databases" / f"{record['item_id']}_{variant}.db"
                backup_database(Path(row["trace"]["db_path"]), archive)
                row["trace"]["db_path"] = str(archive)
                row["database_sha256"] = digest(archive)
                row["judge_calls"] = judge_calls[judge_start:]
                ladder.append_journal(args.out / "journal.jsonl", row)
                observations.append(row)
                print(f"  ok={row['ok']} eligible={row['after']['state_review_eligible']} "
                      f"recalled={len(row['trace']['recall']['statement_ids'])} "
                      f"seconds={row['wall_seconds']:.1f}", flush=True)

        for control in controls:
            record = by_id[control["item_id"]]
            accepted = judge(record["question"], str(record["answer"]),
                             control["candidate"], args.backbone)
            ladder.append_journal(args.out / "judge_controls.jsonl",
                                  {**control, "accepted": accepted, "raw": judge_calls[-1]["raw"]})
            print(f"[judge] {control['item_id']} {control['kind']} "
                  f"expected={control['expected']} accepted={accepted}", flush=True)

        if source_hashes != {key: frozen_database_hash(path) for key, path in sources.items()}:
            raise RuntimeError("source database fingerprint changed during experiment")
        results = {variant: {"correct": sum(r["ok"] for r in observations if r["variant"] == variant),
                             "scored": sum(r["variant"] == variant for r in observations)}
                   for variant in VARIANTS}
        dump(args.out / "results.json", {"claim_level": "diagnostic_only", "variants": results})
        manifest.update(status="complete", source_databases_unchanged=True,
                        completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        dump(args.out / "manifest.json", manifest)
        print("[controls] complete", flush=True)
        return 0
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        dump(args.out / "manifest.json", manifest)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
