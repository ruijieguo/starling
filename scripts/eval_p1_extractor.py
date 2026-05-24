#!/usr/bin/env python3
"""P1 EVAL harness — runs N rounds of extraction against the EVAL corpus.

Per spec §15.3.3, runs 3 rounds and takes the LAST round's F1 vector as
the verdict. Exits non-zero if any F1 < its threshold.

Usage:
    python scripts/eval_p1_extractor.py \\
        --corpus tests/data/eval_p1_corpus.jsonl \\
        --rounds 3 \\
        --report build/eval_p1_report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

P1_THRESHOLDS = {
    "holder":              0.85,
    "holder_perspective":  0.80,
    "predicate":           0.75,
    "object":              0.70,
    "nesting_depth_1":     0.60,
}


def f1_score(tp: int, fp: int, fn: int) -> float:
    if tp == 0 and fp == 0 and fn == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_record(record: dict, predicted: list[dict]) -> dict[str, tuple[int, int, int]]:
    """Compute (tp, fp, fn) per field for one record.

    Matches predictions to ground-truth by (predicate, object) since
    that is the most stable pair across language/perspective drift.
    """
    truths = record["ground_truth_statements"]
    counts: dict[str, list[int]] = {
        "holder":             [0, 0, 0],
        "holder_perspective": [0, 0, 0],
        "predicate":          [0, 0, 0],
        "object":              [0, 0, 0],
        "nesting_depth_1":    [0, 0, 0],
    }

    matched_pred_idx: set[int] = set()
    for t in truths:
        match_idx = None
        for i, p in enumerate(predicted):
            if i in matched_pred_idx: continue
            if p.get("predicate") == t.get("predicate") and \
               str(p.get("object")) == str(t.get("object")):
                match_idx = i; break
        if match_idx is None:
            for fld in ("holder", "holder_perspective", "predicate", "object"):
                counts[fld][2] += 1
            if t.get("nesting_depth", 0) >= 1:
                counts["nesting_depth_1"][2] += 1
            continue
        matched_pred_idx.add(match_idx)
        p = predicted[match_idx]
        for fld in ("holder", "holder_perspective", "predicate", "object"):
            if str(p.get(fld)) == str(t.get(fld)):
                counts[fld][0] += 1
            else:
                counts[fld][1] += 1
                counts[fld][2] += 1
        if t.get("nesting_depth", 0) >= 1:
            if p.get("nesting_depth", 0) >= 1:
                counts["nesting_depth_1"][0] += 1
            else:
                counts["nesting_depth_1"][2] += 1
        elif p.get("nesting_depth", 0) >= 1:
            counts["nesting_depth_1"][1] += 1

    for i, p in enumerate(predicted):
        if i in matched_pred_idx: continue
        for fld in ("holder", "holder_perspective", "predicate", "object"):
            counts[fld][1] += 1
        if p.get("nesting_depth", 0) >= 1:
            counts["nesting_depth_1"][1] += 1

    return {k: (v[0], v[1], v[2]) for k, v in counts.items()}


_EXTRACT_PROMPT = """You are an extractor for a Statement-based memory system.

Given a conversation, extract ALL Statements. Output ONLY a JSON array.

Each Statement: {{"holder": str, "holder_perspective": "FIRST_PERSON"|"QUOTED"|"HEARSAY"|"INFERRED", "subject": str, "predicate": str, "object": str, "modality": "BELIEVES"|"DESIRES"|"INTENDS"|"COMMITS"|"ENFORCES"|"OBSERVES", "polarity": "POS"|"NEG"|"UNKNOWN", "nesting_depth": int}}

Conversation:
{convo}

JSON array:"""


def extract_via_gpt(conversation: list[dict], base_url: str, api_key: str, model: str) -> list[dict]:
    convo_str = "\n".join(f'{t["speaker"]}: {t["text"]}' for t in conversation)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": _EXTRACT_PROMPT.format(convo=convo_str)}],
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json\n"):
            content = content[len("json\n"):]
    return json.loads(content)


def run_one_round(corpus: list[dict], base_url: str, api_key: str, model: str) -> dict[str, float]:
    totals: dict[str, list[int]] = {
        k: [0, 0, 0] for k in P1_THRESHOLDS.keys()
    }
    for i, rec in enumerate(corpus, 1):
        try:
            predicted = extract_via_gpt(rec["conversation"], base_url, api_key, model)
        except Exception as e:
            print(f"WARN: record {rec.get('id')} extraction failed: {e}", file=sys.stderr)
            predicted = []
        per = evaluate_record(rec, predicted)
        for k, (tp, fp, fn) in per.items():
            totals[k][0] += tp
            totals[k][1] += fp
            totals[k][2] += fn
        print(f"[{i}/{len(corpus)}] {rec.get('id')}", file=sys.stderr)
        time.sleep(1)
    return {k: f1_score(tp, fp, fn) for k, (tp, fp, fn) in totals.items()}


def write_report(path: Path, rounds: list[dict[str, float]], thresholds: dict[str, float]) -> None:
    lines = ["# P1 EVAL Report", ""]
    lines.append("| field | " + " | ".join(f"round {i+1}" for i in range(len(rounds))) + " | threshold | last >= threshold |")
    lines.append("|---|" + "---|" * (len(rounds) + 2))
    for field in P1_THRESHOLDS:
        row = [f"{field}"]
        for r in rounds:
            row.append(f"{r[field]:.3f}")
        row.append(f"{thresholds[field]:.2f}")
        last = rounds[-1][field]
        row.append("PASS" if last >= thresholds[field] else "**FAIL**")
        lines.append("| " + " | ".join(row) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus",  required=True, type=Path)
    p.add_argument("--rounds",  type=int, default=3)
    p.add_argument("--report",  type=Path, default=Path("build/eval_p1_report.md"))
    p.add_argument("--model",   default="gpt-5.5")
    args = p.parse_args(argv)

    api_key  = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(corpus)} corpus records", file=sys.stderr)

    rounds = []
    for r in range(args.rounds):
        print(f"=== round {r+1}/{args.rounds} ===", file=sys.stderr)
        rounds.append(run_one_round(corpus, base_url, api_key, args.model))
        print(f"round {r+1} F1: {rounds[-1]}", file=sys.stderr)

    write_report(args.report, rounds, P1_THRESHOLDS)
    last = rounds[-1]
    fail = [f for f, v in last.items() if v < P1_THRESHOLDS[f]]
    if fail:
        print(f"BLOCKED: thresholds not met on last round for fields: {fail}", file=sys.stderr)
        return 1
    print("ALL THRESHOLDS PASSED", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
