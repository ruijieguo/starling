#!/usr/bin/env python3
"""Run the reviewed diagnostic cohort with fresh ingestion and fixed judge repeats."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit, urlunsplit

import eval_adapters as adapters
import eval_judge_audit as audit
import eval_ladder as ladder
import eval_ladder_pipeline as pipe
import eval_socialmem_controls as controls
import eval_socialmem_protocol as protocol

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("star_immediate", "star_sleep", "full", "rag_speakers")


def repeated_judge(chat, sink, repeats: int):
    if repeats < 1 or repeats % 2 == 0:
        raise ValueError("judge repeats must be a positive odd integer")

    def judge(question, reference, candidate, backbone):
        prompt = audit._judge_prompt(question, reference, candidate)
        votes = []
        for i in range(repeats):
            raw = chat(prompt, backbone, max_tokens=8)
            if raw.strip().upper() not in ("YES", "NO"):
                raise ValueError(f"invalid judge verdict: {raw!r}")
            accepted = audit._parse_judge_verdict(raw)
            sink({"repeat": i, "prompt": prompt, "raw": raw, "accepted": accepted})
            votes.append(accepted)
        return sum(votes) > repeats // 2

    return judge


def evaluate_record(record: dict, config: dict, out: Path):
    review = record.get("evaluation_protocol", {})
    if review.get("status") != "include":
        raise ValueError("only reviewed included records may be evaluated")
    if not record["history"] or any(
        t["session_index"] not in review["sessions"] for t in record["history"]
    ):
        raise ValueError("history is outside reviewed session scope")
    now = ladder.normalize_eval_time(config["now_iso"])
    core = config["core"]
    source = out / "ingested.db"
    print(f"[scoped] {record['item_id']} ingest {len(record['history'])} turns", flush=True)
    started = time.perf_counter()
    adapter, embedder, index = config["make_pipeline"](str(source))
    outcomes = config["extract"](adapter, record, config["backbone"])
    with sqlite3.connect(source) as conn:
        conn.row_factory = sqlite3.Row
        pipelines = [dict(r) for r in conn.execute(
            "SELECT id,status,input_ref,metadata_json FROM pipeline_run ORDER BY id")]
    if any(r["status"] != "finished" for r in pipelines):
        controls.dump(out / "extraction_failure.json", {"outcomes": outcomes, "pipelines": pipelines})
        raise ValueError("extraction pipeline did not finish successfully")
    embedding = pipe.embed_seeded(core, adapter, embedder, index, now)
    if embedding.get("final_health", {}).get("complete") is not True:
        raise ValueError("embedding failures in frozen ingestion")
    frozen = out / "frozen.db"
    controls.backup_database(source, frozen)
    before = controls.snapshot(frozen)
    if any(datetime.fromisoformat(r[field]) > datetime.fromisoformat(now)
           for r in before["statements"] for field in ("created_at", "updated_at")):
        raise ValueError("query time precedes actual ingestion; select a later --now-iso")
    fingerprint = controls.frozen_database_hash(frozen)
    controls.dump(out / "ingestion.json", {
        "item_id": record["item_id"], "record_hash": ladder.corpus_hash([record]),
        "embedding": embedding, "wall_seconds": time.perf_counter() - started,
        "extraction_outcomes": outcomes, "extraction_pipelines": pipelines,
        "frozen_sha256": fingerprint, "state": before,
        "source_turn_ids": [t["turn_id"] for t in record["history"]],
    })
    for variant in VARIANTS:
        print(f"[scoped] {record['item_id']} {variant}", flush=True)
        if variant == "full":
            trace = {}
            start = time.perf_counter()
            ok = ladder._real_answer("S_full", record, 0, {**config, "diagnostics": trace})
            row = {"item_id": record["item_id"], "variant": variant, "ok": ok,
                   "wall_seconds": time.perf_counter() - start, "trace": trace,
                   "after": controls.snapshot(Path(trace["db_path"]))}
            row["source_turn_ids"] = [t["turn_id"] for t in record["history"]]
        else:
            row = controls.evaluate_variant(record, variant, frozen, config)
            if variant.startswith("star_") and row["before"] != before:
                raise ValueError("frozen input changed before a lifecycle condition")
            if variant == "rag_speakers":
                turn_ids = {f"{record['item_id']}-h{i}": t["turn_id"]
                            for i, t in enumerate(record["history"])}
                row["source_turn_ids"] = [turn_ids[sid] for sid in row["trace"]["recall"]["statement_ids"]]
        target = out / f"{variant}.db"
        controls.backup_database(Path(row["trace"]["db_path"]), target)
        row["trace"]["db_path"] = str(target)
        row["database_sha256"] = controls.digest(target)
        if controls.frozen_database_hash(frozen) != fingerprint:
            raise ValueError("frozen source changed during evaluation")
        if row["trace"]["embedding"].get("final_health", {}).get("complete") is not True:
            raise ValueError("embedding failures in evaluation variant")
        yield row


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-run", action="store_true", required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now-iso", required=True)
    parser.add_argument("--backbone", default="gpt-5.5")
    parser.add_argument("--judge-repeats", type=int, default=3)
    args = parser.parse_args(argv)
    from starling import _core

    prepared = json.loads((args.prepared / "manifest.json").read_text())
    corpus = audit.load_corpus(args.prepared / "corpus.jsonl")
    review = json.loads((args.prepared / "review.json").read_text())
    if (prepared["status"] != "complete" or not corpus or
        ladder.corpus_hash(corpus) != prepared["corpus_hash"] or
        controls.digest(args.prepared / "review.json") != prepared["review_sha256"]):
        raise ValueError("prepared cohort fingerprint mismatch")
    originals = {r["item_id"]: r for r in audit.load_corpus(args.prepared / "normalized_all.jsonl")}
    expected = [protocol.apply_review(originals[r["item_id"]], r, review["protocol_id"])
                for r in review["items"] if r["status"] == "include"]
    if corpus != expected:
        raise ValueError("cohort does not reproduce the reviewed source scope")
    now = ladder.normalize_eval_time(args.now_iso)
    if args.judge_repeats < 1 or args.judge_repeats % 2 == 0:
        raise ValueError("judge repeats must be a positive odd integer")
    args.out.mkdir(parents=True, exist_ok=False)
    for name in ("corpus.jsonl", "excluded.jsonl", "review.json", "manifest.json"):
        shutil.copyfile(args.prepared / name, args.out / f"prepared_{name}")
    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    os.environ["OPENAI_BASE_URL"] = urlunsplit(url._replace(path="/v1"))
    os.environ["EMBEDDING_MODEL"] = "qwen3.7-text-embedding"
    os.environ["EMBEDDING_DIM"] = "1024"
    config = ladder.build_real_config(_core, 10, [0], "off", [args.backbone],
                                      "qwen3.7-text-embedding", "deepseek-v3", "dashscope")
    config.update(now_iso=now, backbone=args.backbone)
    sources = [Path(__file__), Path(protocol.__file__), Path(adapters.__file__),
               Path(controls.__file__), Path(ladder.__file__), Path(pipe.__file__), Path(audit.__file__),
               ROOT / "python/starling/extractor/config.py"]
    (args.out / "source_archive").mkdir()
    for path in sources:
        shutil.copyfile(path, args.out / "source_archive" / path.name)
    manifest = {
        "status": "running", "claim_level": "diagnostic_only",
        "protocol_id": review["protocol_id"], "variants": list(VARIANTS),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {str(p.relative_to(ROOT)): controls.digest(p) for p in sources},
        "core_sha256": controls.digest(Path(_core.__file__)),
        "prepared_manifest_sha256": controls.digest(args.prepared / "manifest.json"),
        "corpus_hash": ladder.corpus_hash(corpus), "config": ladder._serializable_config(config),
        "judge_repeats": args.judge_repeats,
        "scoring": "Fixed odd-number repeats; majority primary, first and unanimous sensitivity.",
        "selection": prepared["selection"], "excluded": prepared["excluded"],
        "lifecycle": "Fresh extraction once per item; pre-query snapshot shared by both Starling variants.",
        "embedding_dim": 1024, "chat_api_path": "/v1",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    controls.dump(args.out / "manifest.json", manifest)
    votes = []

    def sink(row):
        votes.append(row)
        ladder.append_journal(args.out / "judge_calls.jsonl", row)

    config["judge"] = repeated_judge(audit._chat_completion, sink, args.judge_repeats)
    results = []
    try:
        for i, record in enumerate(corpus):
            out = args.out / f"item_{i}"
            out.mkdir()
            previous = len(votes)
            for row in evaluate_record(record, config, out):
                row["judge_calls"] = votes[previous:]
                previous = len(votes)
                accepted = [v["accepted"] for v in row["judge_calls"]]
                if accepted:
                    row["judge_acceptances"] = sum(accepted)
                    row["first_ok"] = accepted[0]
                    row["unanimous_ok"] = all(accepted)
                else:
                    row.update(first_ok=row["ok"], unanimous_ok=row["ok"])
                ladder.append_journal(args.out / "journal.jsonl", row)
                results.append(row)
                print(f"  majority={row['ok']} votes={accepted} "
                      f"eligible={row['after']['state_review_eligible']}", flush=True)
        summary = {variant: {"scored": sum(r["variant"] == variant for r in results),
                             **{metric: sum(bool(r[metric]) for r in results if r["variant"] == variant)
                                for metric in ("ok", "first_ok", "unanimous_ok")}}
                   for variant in VARIANTS}
        controls.dump(args.out / "results.json", {"claim_level": "diagnostic_only", "variants": summary})
        manifest.update(status="complete", completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        controls.dump(args.out / "manifest.json", manifest)
        return 0
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        controls.dump(args.out / "manifest.json", manifest)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
