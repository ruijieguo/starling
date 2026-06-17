#!/usr/bin/env python3
"""Build the FULL ToMBench corpus (all 8 tasks / 2,860 items) for Starling eval.

Source: ToMBench (Chen et al., ACL 2024, MIT). https://github.com/zhchen18/ToMBench
Walks every ``data/*.jsonl`` file and emits one unified JSONL where each record
is a 4-option multiple-choice ToM question in the Starling eval shape, tagged
with its ToMBench task (the file name) and ATOMS ability (the ABILITY field).

ToMBench is evaluation-only (do not train on it). This corpus feeds
``scripts/eval_tombench_full.py`` to measure an LLM's overall Theory-of-Mind
accuracy across all 8 tasks.

Transformation (ToMBench record -> Starling eval record), English side only:
    STORY        -> context
    QUESTION     -> question
    OPTION-A..D  -> options[0..3]
    答案/ANSWER  -> answer  (letter A/B/C/D -> 0-based index; tolerant of "A.")
    ABILITY      -> ability (raw ATOMS string)
    <file name>  -> task

Usage:
    python scripts/build_tombench_full_corpus.py \\
        --tombench-dir /path/to/ToMBench/data \\
        --out tests/data/eval_tom_bench/full.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_LETTER_TO_IDX = {"A": 0, "B": 1, "C": 2, "D": 3}


def _field_key(rec: dict, needle: str) -> str:
    for k in rec:
        if needle in k:
            return k
    raise KeyError(needle)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _answer_idx(raw: str) -> int:
    # tolerant of stray punctuation/whitespace, e.g. "A." -> 0
    for ch in raw.strip().upper():
        if ch in _LETTER_TO_IDX:
            return _LETTER_TO_IDX[ch]
    raise ValueError(f"unparseable answer: {raw!r}")


def build(tombench_dir: Path) -> list[dict]:
    out: list[dict] = []
    for path in sorted(tombench_dir.glob("*.jsonl")):
        task = path.stem
        slug = _slug(task)
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        if not rows:
            continue
        ab_key = _field_key(rows[0], "ABILITY")
        ans_key = _field_key(rows[0], "ANSWER")
        for i, rec in enumerate(rows):
            out.append({
                "question_id": f"tb-{slug}-{i:03d}",
                "context": rec["STORY"].strip(),
                "question": rec["QUESTION"].strip(),
                "options": [rec["OPTION-A"], rec["OPTION-B"],
                            rec["OPTION-C"], rec["OPTION-D"]],
                "answer": _answer_idx(str(rec[ans_key])),
                "ability": str(rec[ab_key]).replace("\n", " ").strip(),
                "task": task,
            })
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tombench-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    rows = build(args.tombench_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tasks = sorted({r["task"] for r in rows})
    print(f"wrote {len(rows)} records ({len(tasks)} tasks) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
