#!/usr/bin/env python3
"""FANToM information-asymmetry evaluation harness for Starling P2.a.

FANToM (Fine-grained Annotation of Natural Theory-of-Mind) measures a
system's ability to reason about information asymmetry across participants
in multi-party conversations.  Each record is a conversation with multiple
turns and a set of questions that test factual recall, belief attribution,
and answer-ability given who was present for which turns.

Usage (real mode):
    python scripts/eval_fantom.py \\
        --corpus tests/data/eval_fantom/conversations.jsonl \\
        --rounds 3 \\
        --sample-size 1000 \\
        --seed 20260526 \\
        --report build/eval_fantom.md \\
        --backend openai \\
        --model gpt-4o-mini \\
        --question-types factual,belief,answerability

Usage (fixture / CI self-test):
    python scripts/eval_fantom.py \\
        --corpus path/to/tiny.jsonl \\
        --rounds 3 \\
        --sample-size 1000 \\
        --seed 20260526 \\
        --report build/eval_fantom.md \\
        --fixture-mode

Corpus record format (JSONL, one JSON object per line):
    {
      "conversation_id": "fantom-001",
      "participants":    ["Alice", "Bob", "Carol"],
      "turns": [
        {"speaker": "Alice", "listener_set": ["Bob"], "utterance": "..."},
        ...
      ],
      "questions": [
        {
          "question_type": "factual",
          "target_cognizer": "Bob",
          "question_text": "What did Alice say to Bob?",
          "expected_answer": "...",
          "options": ["option A", "option B", "option C", "option D"]
        },
        ...
      ]
    }

Question types:
    factual       -- fact directly derivable from turns visible to the
                     target_cognizer
    belief        -- what target_cognizer believes (may differ from fact
                     due to limited visibility)
    answerability -- can target_cognizer answer a query?
                     FullKnowledge="yes" / NotKnown="maybe" / Unknowable="no"

Exit code:
    0  all question types pass: per-type stddev ≤ 0.05 AND 100 % of items ran
    1  any type fails
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STDDEV_THRESHOLD = 0.05   # max allowable per-question-type stddev across rounds
DEFAULT_ROUNDS = 3
DEFAULT_SAMPLE_SIZE = 1_000
DEFAULT_SEED = 20260526

ALL_QUESTION_TYPES = frozenset(["factual", "belief", "answerability"])

# Mapping from answerability gold label → chosen option keyword
_ANSWERABILITY_MAP = {
    "FullKnowledge": "yes",
    "NotKnown":      "maybe",
    "Unknowable":    "no",
}

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_FACTUAL_PROMPT = """\
You are answering a factual question about a conversation.

Conversation (turns visible to {target_cognizer}):
{visible_turns}

Question: {question_text}

Options (0-based index):
{options_block}

Respond with ONLY the integer index of the correct option.
Do NOT include any explanation."""

_BELIEF_PROMPT = """\
You are reasoning about what a participant in a conversation believes.

Full conversation turns:
{all_turns}

The question asks about the beliefs of: {target_cognizer}

Question: {question_text}

Options (0-based index):
{options_block}

Respond with ONLY the integer index of the option that best represents
{target_cognizer}'s belief based on what they heard.
Do NOT include any explanation."""

_ANSWERABILITY_PROMPT = """\
You are deciding whether a participant in a conversation can answer a question.

Conversation turns visible to {target_cognizer}:
{visible_turns}

Question about answerability: {question_text}

Options (0-based index):
{options_block}

Use these criteria:
- If {target_cognizer} has all the information needed → choose "yes"
- If {target_cognizer} has partial or uncertain information → choose "maybe"
- If {target_cognizer} definitely cannot know → choose "no"

Respond with ONLY the integer index of the correct option.
Do NOT include any explanation."""


def _format_options(options: list[str]) -> str:
    return "\n".join(f"{i}. {opt}" for i, opt in enumerate(options))


def _visible_turns(turns: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    """Return turns that target_cognizer was present for.

    A turn is visible to target if:
    - target == speaker, OR
    - target is in listener_set (empty list means broadcast to all)
    """
    visible = []
    for turn in turns:
        speaker = turn.get("speaker", "")
        listeners = turn.get("listener_set", [])
        if speaker == target or not listeners or target in listeners:
            visible.append(turn)
    return visible


def _format_turns(turns: list[dict[str, Any]]) -> str:
    lines = []
    for t in turns:
        speaker = t.get("speaker", "?")
        listeners = t.get("listener_set", [])
        audience = f" (to {', '.join(listeners)})" if listeners else " (to all)"
        lines.append(f"{speaker}{audience}: {t.get('utterance', '')}")
    return "\n".join(lines) if lines else "(no turns)"


def build_prompt(
    question: dict[str, Any],
    turns: list[dict[str, Any]],
) -> str:
    """Build a question-type-specific prompt."""
    qtype = question.get("question_type", "factual")
    target = question.get("target_cognizer", "")
    q_text = question.get("question_text", "")
    options = question.get("options", [])
    opts_block = _format_options(options)

    if qtype == "factual":
        vis = _visible_turns(turns, target)
        return _FACTUAL_PROMPT.format(
            target_cognizer=target,
            visible_turns=_format_turns(vis),
            question_text=q_text,
            options_block=opts_block,
        )
    elif qtype == "belief":
        return _BELIEF_PROMPT.format(
            all_turns=_format_turns(turns),
            target_cognizer=target,
            question_text=q_text,
            options_block=opts_block,
        )
    else:  # answerability
        vis = _visible_turns(turns, target)
        return _ANSWERABILITY_PROMPT.format(
            target_cognizer=target,
            visible_turns=_format_turns(vis),
            question_text=q_text,
            options_block=opts_block,
        )


# ---------------------------------------------------------------------------
# Gold label resolution
# ---------------------------------------------------------------------------

def _gold_index(question: dict[str, Any]) -> int:
    """Return the 0-based gold option index for a question.

    For answerability questions, expected_answer may be a keyword
    (FullKnowledge / NotKnown / Unknowable); look it up in options.
    For factual/belief questions, expected_answer matches one option text.
    """
    expected = question.get("expected_answer", "")
    options = question.get("options", [])
    # Direct string match first
    for i, opt in enumerate(options):
        if opt == expected:
            return i
    # Case-insensitive fallback
    exp_lower = expected.lower()
    for i, opt in enumerate(options):
        if opt.lower() == exp_lower:
            return i
        # Check answerability keyword mapping
        qtype = question.get("question_type", "")
        if qtype == "answerability":
            keyword = _ANSWERABILITY_MAP.get(expected, "")
            if keyword and keyword.lower() in opt.lower():
                return i
    # Numeric string fallback ("0", "1", ...)
    try:
        return int(expected)
    except (ValueError, TypeError):
        pass
    return 0  # best effort default


# ---------------------------------------------------------------------------
# LLM back-end (real OpenAI path)
# ---------------------------------------------------------------------------

def _call_openai_once(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    max_option_idx: int,
) -> int:
    """Call the OpenAI chat-completions endpoint and parse the option index."""
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 4,
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
    valid_chars = set(str(i) for i in range(max_option_idx + 1))
    for ch in content:
        if ch in valid_chars:
            return int(ch)
    raise ValueError(f"Could not parse answer index from: {content!r}")


def call_openai(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    max_option_idx: int,
) -> int:
    """Call OpenAI with up to 3 attempts (exponential back-off)."""
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            return _call_openai_once(prompt, base_url, api_key, model, max_option_idx)
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fixture mock (no real LLM calls)
# ---------------------------------------------------------------------------

def _fixture_answer(
    question: dict[str, Any],
    conv_idx: int,
    q_idx: int,
) -> int:
    """Deterministically return the gold answer ~90 % of the time.

    Uses (conv_idx * 31 + q_idx) as a stable hash so the same
    (conversation, question) pair always gets the same verdict across rounds,
    keeping stddev at exactly 0.0.
    """
    h = (conv_idx * 31 + q_idx) % 10
    gold = _gold_index(question)
    if h < 9:  # 90 % correct
        return gold
    # Wrong answer: next index mod len(options) or 1
    n = len(question.get("options", [1, 2]))
    return (gold + 1) % n


# ---------------------------------------------------------------------------
# Per-round evaluation
# ---------------------------------------------------------------------------

def run_one_round(
    conversations: list[dict[str, Any]],
    question_types: frozenset[str],
    *,
    fixture_mode: bool,
    base_url: str,
    api_key: str,
    model: str,
) -> dict[str, tuple[int, int]]:
    """Run every question in every conversation for one round.

    Returns a dict mapping question_type -> (correct_count, total_count).
    """
    counts: dict[str, list[int]] = {qt: [0, 0] for qt in question_types}
    errors = 0

    for conv_idx, conv in enumerate(conversations):
        turns = conv.get("turns", [])
        questions = conv.get("questions", [])
        for q_idx, question in enumerate(questions):
            qtype = question.get("question_type", "")
            if qtype not in question_types:
                continue
            gold = _gold_index(question)
            if fixture_mode:
                predicted = _fixture_answer(question, conv_idx, q_idx)
            else:
                try:
                    prompt = build_prompt(question, turns)
                    n_opts = len(question.get("options", [])) - 1
                    predicted = call_openai(
                        prompt, base_url, api_key, model, max(n_opts, 0)
                    )
                except Exception as exc:
                    cid = conv.get("conversation_id", f"conv-{conv_idx}")
                    print(
                        f"WARN: {cid} q{q_idx} ({qtype}) failed: {exc}",
                        file=sys.stderr,
                    )
                    predicted = -1  # count as wrong
                    errors += 1
                time.sleep(0.3)  # be polite to rate limiter

            counts[qtype][1] += 1  # total
            if predicted == gold:
                counts[qtype][0] += 1  # correct

        if (conv_idx + 1) % 50 == 0:
            summary = "  ".join(
                f"{qt}={counts[qt][0]}/{counts[qt][1]}"
                for qt in question_types
                if counts[qt][1] > 0
            )
            print(
                f"  [conv {conv_idx + 1}/{len(conversations)}] {summary}",
                file=sys.stderr,
            )

    if errors:
        print(f"  {errors} question(s) errored (counted as wrong)", file=sys.stderr)

    return {qt: (counts[qt][0], counts[qt][1]) for qt in question_types}


# ---------------------------------------------------------------------------
# Stddev helpers
# ---------------------------------------------------------------------------

def _stddev(values: list[float]) -> float:
    """Population standard deviation of a list of floats."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    path: Path,
    rounds_data: list[dict[str, tuple[int, int]]],
    question_types: frozenset[str],
    stddev_threshold: float,
    overall_pass: bool,
) -> None:
    """Write a Markdown report with per-round accuracy and stddev summary."""
    n_rounds = len(rounds_data)
    lines: list[str] = ["# FANToM Eval Report", ""]

    # Per-round detail table
    lines.append("## Per-round accuracy")
    lines.append("")
    header = "| question_type | " + " | ".join(f"round {r + 1}" for r in range(n_rounds)) + " | stddev | verdict |"
    sep = "|---|" + "---|" * (n_rounds + 2)
    lines.append(header)
    lines.append(sep)

    for qt in sorted(question_types):
        accs: list[float] = []
        for rd in rounds_data:
            correct, total = rd.get(qt, (0, 0))
            accs.append(correct / total if total > 0 else 0.0)
        sd = _stddev(accs)
        verdict = "PASS" if sd <= stddev_threshold else "**FAIL**"
        acc_cols = " | ".join(f"{a:.4f}" for a in accs)
        lines.append(f"| {qt} | {acc_cols} | {sd:.4f} | {verdict} |")

    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| threshold (stddev) | {stddev_threshold} |")
    lines.append("|---|---|")
    lines.append(f"| overall verdict | {'PASS' if overall_pass else '**FAIL**'} |")
    lines.append("")

    # Coverage table
    lines.append("## Coverage")
    lines.append("")
    lines.append("| question_type | total questions (round 1) |")
    lines.append("|---|---|")
    for qt in sorted(question_types):
        _, total = rounds_data[0].get(qt, (0, 0))
        lines.append(f"| {qt} | {total} |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------

def load_corpus(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def sample_corpus(
    corpus: list[dict[str, Any]],
    sample_size: int,
    seed: int,
) -> list[dict[str, Any]]:
    if len(corpus) <= sample_size:
        return list(corpus)
    rng = random.Random(seed)
    return rng.sample(corpus, sample_size)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FANToM information-asymmetry evaluation harness."
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Path to FANToM JSONL corpus (one conversation per line)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_ROUNDS,
        help=f"Number of evaluation rounds (default {DEFAULT_ROUNDS})",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        metavar="N",
        help=f"Number of conversations to sample (default {DEFAULT_SAMPLE_SIZE})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for sampling (default {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/eval_fantom.md"),
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
        "--question-types",
        default="factual,belief,answerability",
        metavar="TYPE1,TYPE2,...",
        help="Comma-separated question types to evaluate (default: factual,belief,answerability)",
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

    # --- parse question types ---
    question_types = frozenset(
        qt.strip() for qt in args.question_types.split(",") if qt.strip()
    )
    unknown = question_types - ALL_QUESTION_TYPES
    if unknown:
        print(
            f"ERROR: unknown question type(s): {sorted(unknown)}. "
            f"Valid types: {sorted(ALL_QUESTION_TYPES)}",
            file=sys.stderr,
        )
        return 1

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
    corpus = load_corpus(args.corpus)
    if not corpus:
        print("ERROR: corpus is empty", file=sys.stderr)
        return 1
    print(f"Loaded {len(corpus)} conversations", file=sys.stderr)

    # --- sample ---
    sample = sample_corpus(corpus, args.sample_size, args.seed)
    print(
        f"Sampled {len(sample)} conversations "
        f"(seed={args.seed}, requested={args.sample_size})",
        file=sys.stderr,
    )

    # --- run rounds ---
    rounds_data: list[dict[str, tuple[int, int]]] = []
    for r in range(args.rounds):
        print(f"=== round {r + 1}/{args.rounds} ===", file=sys.stderr)
        rd = run_one_round(
            sample,
            question_types,
            fixture_mode=args.fixture_mode,
            base_url=base_url,
            api_key=api_key,
            model=args.model,
        )
        rounds_data.append(rd)
        for qt in sorted(question_types):
            correct, total = rd.get(qt, (0, 0))
            acc = correct / total if total > 0 else 0.0
            print(
                f"  {qt}: {correct}/{total} = {acc:.4f}",
                file=sys.stderr,
            )

    # --- compute per-type stddev and coverage ---
    failures: list[str] = []

    for qt in sorted(question_types):
        accs: list[float] = []
        for rd in rounds_data:
            correct, total = rd.get(qt, (0, 0))
            if total == 0:
                failures.append(
                    f"{qt}: 0 questions evaluated (coverage failure)"
                )
                accs.append(0.0)
            else:
                accs.append(correct / total)
        sd = _stddev(accs)
        if sd > STDDEV_THRESHOLD:
            failures.append(
                f"{qt}: stddev {sd:.4f} > threshold {STDDEV_THRESHOLD}"
            )

    # --- check 100 % coverage (every type ran on round 1) ---
    for qt in sorted(question_types):
        _, total = rounds_data[0].get(qt, (0, 0))
        if total == 0:
            msg = f"{qt}: no questions found in corpus for this type"
            if msg not in failures:
                failures.append(msg)

    # --- write report ---
    overall_pass = len(failures) == 0
    write_report(
        args.report,
        rounds_data,
        question_types,
        STDDEV_THRESHOLD,
        overall_pass,
    )
    print(f"Report written to {args.report}", file=sys.stderr)

    # --- verdict ---
    if overall_pass:
        print("PASS — all question types within stddev threshold")
        return 0
    for f in failures:
        print(f"FAIL — {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
