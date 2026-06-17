#!/usr/bin/env python3
"""Full-ToMBench LLM Theory-of-Mind eval (all 8 tasks / 2,860 items).

A wider, harder companion to ``eval_tom_bench.py --order second`` (which only
covers the templated second-order false-belief subset). This runs an LLM over
the ENTIRE ToMBench benchmark and reports per-task plus overall accuracy — a
capability profile, not a single admission gate.

This measures the LLM's *intrinsic* ToM (faux-pas, irony, scalar implicature,
persuasion, desire/intention/emotion inference, …). Starling's memory machinery
is NOT in the loop: only the False Belief second-order subset maps to Starling's
deterministic nesting (see eval_tom2_starling.py); the other tasks are LLM
reasoning that Starling delegates to the model, so the floor lives here.

Calls are issued concurrently (ToM reasoning is slow; 2,860 sequential calls
would take hours). Reuses build_prompt + call_openai from eval_tom_bench so the
prompt, the 0-3 answer parsing, max_tokens (32768, reasoning-safe) and retry are
identical to track 1.

Usage:
    OPENAI_API_KEY=$DEEPSEEK_API_KEY OPENAI_BASE_URL=https://api.deepseek.com/v1 \\
      python scripts/eval_tombench_full.py \\
        --corpus tests/data/eval_tom_bench/full.jsonl \\
        --model deepseek-v4-pro --concurrency 16 \\
        --report build/eval_tombench_full.md

Exit 0 if overall accuracy >= --threshold (default 0.0 = report-only), else 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_tom_bench import build_prompt, call_openai  # noqa: E402


def _predict_one(rec: dict[str, Any], base_url: str, api_key: str,
                 model: str) -> int:
    try:
        return call_openai(build_prompt(rec), base_url, api_key, model)
    except Exception as exc:  # noqa: BLE001 — count failures as wrong
        print(f"WARN qid={rec.get('question_id')}: {exc}", file=sys.stderr)
        return -1


def run(records: list[dict[str, Any]], *, base_url: str, api_key: str,
        model: str, concurrency: int) -> list[int]:
    preds: list[int] = [-1] * len(records)
    done = 0
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        fut_to_idx = {
            ex.submit(_predict_one, rec, base_url, api_key, model): i
            for i, rec in enumerate(records)
        }
        for fut in as_completed(fut_to_idx):
            preds[fut_to_idx[fut]] = fut.result()
            done += 1
            if done % 100 == 0:
                rate = done / max(time.monotonic() - t0, 1e-9)
                eta = (len(records) - done) / max(rate, 1e-9)
                print(f"  [{done}/{len(records)}] {rate:.1f}/s "
                      f"eta {eta/60:.1f}m", file=sys.stderr)
    return preds


def aggregate(records: list[dict[str, Any]], preds: list[int]) -> dict:
    per_task: dict[str, list[int]] = {}
    correct = 0
    for rec, pred in zip(records, preds):
        ok = int(pred == int(rec["answer"]))
        correct += ok
        per_task.setdefault(rec["task"], [0, 0])
        per_task[rec["task"]][0] += ok
        per_task[rec["task"]][1] += 1
    return {
        "overall": (correct, len(records)),
        "per_task": per_task,
    }


def write_report(path: Path, agg: dict, model: str, threshold: float) -> None:
    c, n = agg["overall"]
    overall = c / n if n else 0.0
    lines = [
        "# Full ToMBench eval (LLM ToM capability profile)", "",
        f"model: **{model}** · items: **{n}** · "
        f"overall: **{overall:.4f}** ({c}/{n})", "",
        "| task | n | correct | accuracy |", "|---|---|---|---|",
    ]
    for task in sorted(agg["per_task"]):
        tc, tn = agg["per_task"][task]
        lines.append(f"| {task} | {tn} | {tc} | {tc / tn:.4f} |")
    lines.append(f"| **OVERALL** | **{n}** | **{c}** | **{overall:.4f}** |")
    if threshold > 0:
        verdict = "PASS" if overall >= threshold else "**FAIL**"
        lines += ["", f"threshold {threshold:.2f} → {verdict}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Full ToMBench LLM eval.")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--max-items", type=int, default=None)
    p.add_argument("--threshold", type=float, default=0.0,
                   help="overall-accuracy gate (default 0.0 = report-only)")
    p.add_argument("--report", type=Path,
                   default=Path("build/eval_tombench_full.md"))
    args = p.parse_args(argv)

    records = [json.loads(l) for l in args.corpus.read_text().splitlines()
               if l.strip()]
    if args.max_items is not None:
        records = records[: args.max_items]
    if not records:
        print("ERROR: corpus is empty", file=sys.stderr)
        return 1

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    print(f"Running {len(records)} items @ concurrency {args.concurrency} "
          f"({args.model})", file=sys.stderr)
    preds = run(records, base_url=base_url, api_key=api_key, model=args.model,
                concurrency=args.concurrency)
    agg = aggregate(records, preds)
    write_report(args.report, agg, args.model, args.threshold)

    c, n = agg["overall"]
    overall = c / n if n else 0.0
    print(f"Report written to {args.report}", file=sys.stderr)
    print(f"OVERALL accuracy {overall:.4f} ({c}/{n})")
    for task in sorted(agg["per_task"]):
        tc, tn = agg["per_task"][task]
        print(f"  {tc/tn:.4f}  {task} ({tc}/{tn})")
    if args.threshold > 0 and overall < args.threshold:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
