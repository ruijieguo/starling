#!/usr/bin/env python3
"""Prepare an explicitly reviewed SocialMemBench diagnostic cohort, offline."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import eval_adapters as adapters
import eval_ladder as ladder
from eval_socialmem_controls import digest, dump


def apply_review(record: dict, review: dict, protocol_id: str) -> dict:
    for key, expected in (("item_id", record["item_id"]), ("question", record["question"]),
                          ("network_id", record["source"]["network_id"])):
        if review.get(key) != expected:
            raise ValueError(f"stale review {key}: {record['item_id']}")
    if review.get("status") not in ("include", "exclude") or not review.get("reason"):
        raise ValueError("review needs include/exclude status and a reason")
    result = deepcopy(record)
    if "evaluation_protocol" in result:
        raise ValueError("review must be applied to the original, unfiltered record")
    if "sessions" not in review:
        raise ValueError("review must explicitly choose sessions or null for full history")
    sessions = review["sessions"]
    available = {t["session_index"] for t in record["history"]}
    if sessions is not None and (
        not isinstance(sessions, list) or not sessions or
        any(type(s) is not int for s in sessions) or len(set(sessions)) != len(sessions) or
        not set(sessions) <= available
    ):
        raise ValueError("review sessions must be distinct existing integer session indices")
    kept = available if sessions is None else set(sessions)
    if review["status"] == "include":
        result["history"] = [t for t in result["history"] if t["session_index"] in kept]
        turns = {t["turn_id"]: t for t in result["history"]}
        for gold in result.get("gold_statements", []):
            turn = turns.get(gold.get("turn_id"))
            if turn is None or turn["session_index"] != gold.get("session_index"):
                raise ValueError(f"gold evidence outside reviewed history: {record['item_id']}")
    kept_ids = {t["turn_id"] for t in result["history"]}
    result["evaluation_protocol"] = {
        "id": protocol_id, "status": review["status"], "reason": review["reason"],
        "sessions": sorted(kept) if review["status"] == "include" else sorted(available),
        "source_record_hash": ladder.corpus_hash([record]),
        "source_turn_count": len(record["history"]),
        "omitted_turn_ids": [t["turn_id"] for t in record["history"] if t["turn_id"] not in kept_ids],
    }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    import pyarrow.parquet as parquet

    review = json.loads(args.review.read_text())
    sources = {name: args.data / name for name in ("qa.parquet", "conversations.parquet")}
    hashes = {name: digest(path) for name, path in sources.items()}
    if hashes != review["source_sha256"]:
        raise ValueError("source files differ from the reviewed public dataset snapshot")
    records = adapters.adapt_socialmembench(
        parquet.read_table(sources["qa.parquet"]).to_pylist(),
        parquet.read_table(sources["conversations.parquet"]).to_pylist())
    by_id = {r["item_id"]: r for r in records}
    if len(by_id) != len(records):
        raise ValueError("duplicate QA IDs")
    selected, excluded = [], []
    reviewed = set()
    for item in review["items"]:
        if item["item_id"] in reviewed:
            raise ValueError("duplicate review item")
        reviewed.add(item["item_id"])
        rec = apply_review(by_id[item["item_id"]], item, review["protocol_id"])
        (selected if item["status"] == "include" else excluded).append(rec)
    queue = [{"item_id": r["item_id"], "network_id": r["source"]["network_id"],
              "query_type": r["query_type"], "question": r["question"],
              "options": r["options"], "reference_answer": r["source"]["reference_answer"],
              "status": "unreviewed",
              "review_axis": "temporal_scope" if r["query_type"] == "Q9" else "mc_semantics"}
             for r in records if r["item_id"] not in reviewed and
             (r["query_type"] == "Q9" or r["answer_format"] == "multiple_choice")]
    args.out.mkdir(parents=True, exist_ok=False)
    for name, rows in (("corpus.jsonl", selected), ("excluded.jsonl", excluded),
                       ("normalized_all.jsonl", records)):
        (args.out / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    dump(args.out / "review.json", review)
    dump(args.out / "review_queue.json", queue)
    manifest = {
        "status": "complete", "claim_level": "diagnostic_only", "protocol_id": review["protocol_id"],
        "source_sha256": hashes, "review_sha256": digest(args.out / "review.json"),
        "code_sha256": {p.name: digest(p) for p in (Path(__file__), Path(adapters.__file__))},
        "corpus_hash": ladder.corpus_hash(selected), "source_questions": len(records),
        "query_types": dict(Counter(r["query_type"] for r in records)),
        "included": [{"item_id": r["item_id"], "turns": len(r["history"]),
                      "sessions": r["evaluation_protocol"]["sessions"]} for r in selected],
        "excluded": [r["item_id"] for r in excluded],
        "unreviewed": len(records) - len(reviewed),
        "priority_review_queue": dict(Counter(r["review_axis"] for r in queue)),
        "selection": "Previously diagnosed cases only; not a stratified benchmark sample.",
    }
    dump(args.out / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
