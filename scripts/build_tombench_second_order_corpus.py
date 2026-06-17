#!/usr/bin/env python3
"""Build the ToMBench second-order false-belief eval corpus for Starling P3.a2.

Source
------
ToMBench (Chen et al., *ToMBench: Benchmarking Theory of Mind in Large Language
Models*, ACL 2024). MIT-licensed. https://github.com/zhchen18/ToMBench

We take ``data/False Belief Task.jsonl`` and keep only the records whose ABILITY
field contains ``"Belief: Second-order beliefs"`` — 200 second-order false-belief
items (100 *location* + 100 *content* second-order). These are the classic
Perner & Wimmer (1985) second-order paradigm: "where does A *think* B looks for
the object?", whose answer is the object's original location because A knows B
never saw it moved (A's belief about B's false belief).

Upstream notice: ToMBench is released for EVALUATION ONLY — do not use it for
model training. This corpus is consumed only by ``scripts/eval_tom_bench.py
--order second`` to measure an LLM's second-order Theory-of-Mind accuracy for the
P3.a2 admission gate (precision > 0.70).

Transformation (ToMBench record -> Starling eval record)
--------------------------------------------------------
    STORY        -> context              (English field; bilingual 故事 dropped)
    QUESTION     -> question             (English field)
    OPTION-A..D  -> options[0..3]        (English options)
    答案/ANSWER  -> answer               (letter A/B/C/D -> 0-based index)
    ABILITY      -> ability="second-order"  (constant; eval filters on this subset)

Usage
-----
    python scripts/build_tombench_second_order_corpus.py \\
        --tombench-file "/path/to/ToMBench/data/False Belief Task.jsonl" \\
        --out tests/data/eval_tom_bench/second_order.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_LETTER_TO_IDX = {"A": 0, "B": 1, "C": 2, "D": 3}


def _field_key(rec: dict, needle: str) -> str:
    """ToMBench keys embed a newline (e.g. ``能力\\nABILITY``); match by substring."""
    for k in rec:
        if needle in k:
            return k
    raise KeyError(needle)


def build(tombench_file: Path) -> list[dict]:
    rows = [
        json.loads(line)
        for line in tombench_file.read_text().splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError(f"empty ToMBench file: {tombench_file}")
    ab_key = _field_key(rows[0], "ABILITY")
    ans_key = _field_key(rows[0], "ANSWER")

    out: list[dict] = []
    for rec in rows:
        if "Second-order" not in rec[ab_key]:
            continue
        letter = rec[ans_key].strip()
        out.append(
            {
                "question_id": f"tb-so-{len(out):03d}",
                "context": rec["STORY"].strip(),
                "question": rec["QUESTION"].strip(),
                "options": [
                    rec["OPTION-A"],
                    rec["OPTION-B"],
                    rec["OPTION-C"],
                    rec["OPTION-D"],
                ],
                "answer": _LETTER_TO_IDX[letter],
                "ability": "second-order",
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tombench-file", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    rows = build(args.tombench_file)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
