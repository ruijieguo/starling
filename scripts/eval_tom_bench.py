#!/usr/bin/env python3
"""ToMBench first-order easy-subset evaluation harness for Starling P2.a.

Reads a JSONL corpus where each record is a multiple-choice Theory-of-Mind
question. For each question the harness either calls an LLM (via the OpenAI
API) or, in fixture mode, uses a deterministic mock that always returns the
correct answer so the CI self-test passes without real API credentials.

Usage (real mode):
    python scripts/eval_tom_bench.py \\
        --corpus tests/data/eval_tom_bench/first_order.jsonl \\
        --rounds 3 \\
        --report build/eval_tom_bench.md \\
        --backend openai \\
        --model gpt-4o-mini

Usage (fixture / CI self-test):
    python scripts/eval_tom_bench.py \\
        --corpus path/to/tiny.jsonl \\
        --rounds 3 \\
        --report build/eval_tom_bench.md \\
        --fixture-mode

Corpus record format (JSONL, one JSON object per line):
    {
      "question_id": "tb-001",
      "context":  "<story text>",
      "question": "<question>",
      "options":  ["A", "B", "C", "D"],   // exactly 4 options
      "answer":   2,                       // 0-based index into options
      "ability":  "unexpected-outcome"     // one of the first-order abilities
    }

First-order easy-subset abilities (others are skipped):
    unexpected-outcome, desire, persuade, world-knowledge

Exit code:
    0  last-round accuracy >= 0.55
    1  last-round accuracy <  0.55  (BLOCKED)
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIRST_ORDER_ABILITIES = frozenset(
    ["unexpected-outcome", "desire", "persuade", "world-knowledge"]
)

ACCURACY_THRESHOLD = 0.55

# Deterministic seed used by the fixture mock so results are reproducible.
_FIXTURE_CORRECT_RATE = 0.70  # 70 % correct → well above 0.55 threshold

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_MC_PROMPT = """\
You are answering a Theory-of-Mind multiple-choice question.

Story:
{context}

Question:
{question}

Options (0-based index):
0. {opt0}
1. {opt1}
2. {opt2}
3. {opt3}

Respond with ONLY the integer index (0, 1, 2, or 3) of the correct answer.
Do NOT include any explanation."""


def build_prompt(record: dict[str, Any]) -> str:
    opts = record["options"]
    return _MC_PROMPT.format(
        context=record["context"],
        question=record["question"],
        opt0=opts[0],
        opt1=opts[1],
        opt2=opts[2],
        opt3=opts[3],
    )


# ---------------------------------------------------------------------------
# LLM back-end (real OpenAI path)
# ---------------------------------------------------------------------------

def _call_openai_once(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
) -> int:
    """Call the OpenAI chat-completions endpoint and parse the answer index."""
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            # 512 (not 4) so reasoning models (deepseek-v4-*, o1-style) have room to
            # emit a visible answer; the parser below grabs the first 0-3 digit, so
            # extra/reasoning text is harmless.
            "max_tokens": 512,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"].strip()
    # Extract the first digit character from the response.
    for ch in content:
        if ch in "0123":
            return int(ch)
    raise ValueError(f"Could not parse answer index from: {content!r}")


def call_openai(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
) -> int:
    """Call OpenAI with up to 3 attempts (exponential back-off)."""
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            return _call_openai_once(prompt, base_url, api_key, model)
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fixture mock (no real LLM calls)
# ---------------------------------------------------------------------------

def _fixture_answer(record: dict[str, Any], item_index: int) -> int:
    """Deterministically return correct ~70 % of the time.

    Uses item_index as a stable input so the same record always gets the same
    verdict across rounds.
    """
    # 7 out of every 10 items are "correct"
    if item_index % 10 < 7:
        return int(record["answer"])
    # wrong answer: return the next index mod 4
    return (int(record["answer"]) + 1) % 4


# ---------------------------------------------------------------------------
# Single round
# ---------------------------------------------------------------------------

def run_one_round(
    corpus: list[dict[str, Any]],
    *,
    fixture_mode: bool,
    base_url: str,
    api_key: str,
    model: str,
) -> float:
    """Run every record in corpus and return accuracy (0.0–1.0)."""
    correct = 0
    total = 0
    for idx, record in enumerate(corpus):
        ability = record.get("ability", "")
        if ability not in FIRST_ORDER_ABILITIES:
            # skip abilities outside the easy first-order subset
            continue
        total += 1
        gold = int(record["answer"])
        if fixture_mode:
            predicted = _fixture_answer(record, idx)
        else:
            prompt = build_prompt(record)
            try:
                predicted = call_openai(prompt, base_url, api_key, model)
            except Exception as exc:
                print(
                    f"WARN: question_id={record.get('question_id')} failed: {exc}",
                    file=sys.stderr,
                )
                predicted = -1  # count as wrong
        if predicted == gold:
            correct += 1
        if (idx + 1) % 20 == 0:
            print(
                f"  [{idx + 1}/{len(corpus)}] running total "
                f"{correct}/{total} correct",
                file=sys.stderr,
            )
        if not fixture_mode:
            time.sleep(0.5)  # be polite to the rate limiter
    if total == 0:
        print("WARN: no records matched first-order abilities; accuracy=0.0", file=sys.stderr)
        return 0.0
    return correct / total


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    path: Path,
    round_accuracies: list[float],
    threshold: float,
) -> None:
    """Write a Markdown table with one column per round + verdict."""
    n = len(round_accuracies)
    header_cols = " | ".join(f"round {i + 1}" for i in range(n))
    sep_cols = "---|" * (n + 2)

    lines = ["# ToMBench Eval Report", ""]
    lines.append(f"| metric | {header_cols} | threshold | verdict |")
    lines.append(f"|---| {sep_cols}")

    row = ["accuracy"]
    for acc in round_accuracies:
        row.append(f"{acc:.4f}")
    row.append(f"{threshold:.2f}")
    last = round_accuracies[-1]
    row.append("PASS" if last >= threshold else "**FAIL**")
    lines.append("| " + " | ".join(row) + " |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ToMBench first-order easy-subset accuracy harness."
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Path to JSONL corpus (one record per line)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Number of evaluation rounds (default 3)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/eval_tom_bench.md"),
        help="Markdown report output path",
    )
    parser.add_argument(
        "--backend",
        default="openai",
        choices=["openai"],
        help="LLM back-end (default openai)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model name passed to the back-end (default gpt-4o-mini)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Limit corpus to first N items (useful for quick test runs)",
    )
    parser.add_argument(
        "--fixture-mode",
        action="store_true",
        help=(
            "Use a deterministic mock instead of real LLM calls. "
            "Designed for CI self-tests; always passes threshold."
        ),
    )
    args = parser.parse_args(argv)

    # --- validate API key (not needed in fixture mode) ---
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not args.fixture_mode and not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    # --- load corpus ---
    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 1
    corpus = [
        json.loads(line)
        for line in args.corpus.read_text().splitlines()
        if line.strip()
    ]
    if args.max_items is not None:
        corpus = corpus[: args.max_items]
    if not corpus:
        print("ERROR: corpus is empty", file=sys.stderr)
        return 1
    print(f"Loaded {len(corpus)} corpus records", file=sys.stderr)

    # --- run rounds ---
    round_accuracies: list[float] = []
    for r in range(args.rounds):
        print(f"=== round {r + 1}/{args.rounds} ===", file=sys.stderr)
        acc = run_one_round(
            corpus,
            fixture_mode=args.fixture_mode,
            base_url=base_url,
            api_key=api_key,
            model=args.model,
        )
        round_accuracies.append(acc)
        print(
            f"round {r + 1} accuracy: {acc:.4f}",
            file=sys.stderr,
        )

    # --- write report ---
    write_report(args.report, round_accuracies, ACCURACY_THRESHOLD)
    print(f"Report written to {args.report}", file=sys.stderr)

    # --- verdict ---
    last_acc = round_accuracies[-1]
    if last_acc >= ACCURACY_THRESHOLD:
        print(
            f"PASS — last-round accuracy {last_acc:.4f} >= threshold {ACCURACY_THRESHOLD}",
        )
        return 0
    print(
        f"BLOCKED — last-round accuracy {last_acc:.4f} < threshold {ACCURACY_THRESHOLD}",
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
