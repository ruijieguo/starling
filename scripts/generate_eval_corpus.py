#!/usr/bin/env python3
"""One-shot generator for the M0.7 EVAL corpus.

Calls GPT-5.5 via OPENAI_BASE_URL/OPENAI_API_KEY to produce 50 records
covering the §15.3.3 coverage matrix:
  - ~12 records each for FIRST_PERSON / QUOTED / HEARSAY / INFERRED
  - ~10 records with nesting_depth=1 (2nd-order ToM)
  - ~5 each for COMMITMENT / NORM (overlap allowed)
  - ~50/50 split EN/ZH

The output is committed once; do NOT re-run unless the corpus must be
regenerated. Re-running will produce a different distribution and force
a fresh EVAL baseline.

Usage:
    python scripts/generate_eval_corpus.py \\
        --out tests/data/eval_p1_corpus.jsonl

Exits non-zero if OPENAI_API_KEY is unset or any record fails JSON validation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import urllib.request
import urllib.error


@dataclass(frozen=True)
class Slot:
    record_id: str
    perspective: str       # FIRST_PERSON | QUOTED | HEARSAY | INFERRED
    language: str          # en | zh
    has_nesting: bool
    has_commitment: bool
    has_norm: bool


def build_slots() -> list[Slot]:
    """Construct the deterministic 50-slot coverage plan."""
    slots = []
    counts = {"FIRST_PERSON": 13, "QUOTED": 12, "HEARSAY": 12, "INFERRED": 13}
    idx = 0
    for persp, n in counts.items():
        for i in range(n):
            language = "en" if (idx % 2 == 0) else "zh"
            has_nesting = (idx % 5 == 0)
            has_commitment = (idx % 7 == 0 and idx > 0)
            has_norm = (idx % 11 == 0 and idx > 0)
            slots.append(Slot(
                record_id=f"eval-{idx:03d}",
                perspective=persp,
                language=language,
                has_nesting=has_nesting,
                has_commitment=has_commitment,
                has_norm=has_norm))
            idx += 1
    assert len(slots) == 50, f"Expected 50 slots, got {len(slots)}"
    return slots


def slot_prompt(slot: Slot) -> str:
    """Render a per-slot GPT-5.5 prompt for one corpus record."""
    nesting_clause = (
        "Include exactly one 2nd-order ToM Statement (Alice believes Bob believes X)."
        if slot.has_nesting else "")
    commitment_clause = (
        "Include exactly one COMMITMENT Statement (someone promises something)."
        if slot.has_commitment else "")
    norm_clause = (
        "Include exactly one NORM Statement (a rule or policy)."
        if slot.has_norm else "")

    return f"""You are generating one record for a memory-system EVAL corpus.

OUTPUT FORMAT: a single JSON object, no surrounding markdown, no commentary.

Constraints:
- id: "{slot.record_id}"
- language: {slot.language} ({"English" if slot.language == "en" else "Chinese (Mandarin)"})
- The conversation should contain 2-4 turns between 2-3 speakers.
- holder_perspective for the primary Statement: {slot.perspective}
- {nesting_clause}
- {commitment_clause}
- {norm_clause}

Schema:
{{
  "id": "{slot.record_id}",
  "language": "{slot.language}",
  "conversation": [
    {{"speaker": "Alice", "text": "...", "observed_at": "2026-04-15T10:30:00Z"}},
    ...
  ],
  "ground_truth_statements": [
    {{
      "holder": "Alice",
      "holder_perspective": "{slot.perspective}",
      "subject": "Bob",
      "predicate": "responsible_for",
      "object": "auth",
      "modality": "BELIEVES",
      "polarity": "POS",
      "nesting_depth": 0,
      "confidence_hint": 0.85,
      "valid_from_hint": "2026-04-15"
    }}
  ],
  "tags": ["{slot.perspective.lower()}", "{slot.language}"]
}}

predicate must be one of: responsible_for, knows, prefers, promises, forbids, requires, located_at, member_of, believes, doubts.
modality must be one of: BELIEVES, DESIRES, INTENDS, COMMITS, ENFORCES, OBSERVES.
polarity must be one of: POS, NEG, UNKNOWN.

Now produce the JSON object."""


def call_gpt(prompt: str, base_url: str, api_key: str, max_attempts: int = 3) -> str:
    """Single HTTP call to OPENAI-compatible /chat/completions, with retry on transient errors.

    Retries up to max_attempts on:
      - HTTPError 429 / 5xx
      - URLError (network/transport)
      - timeout
    Backoff: 1s, 2s, 4s. Re-raises after the final attempt.
    Never logs api_key.
    """
    payload = json.dumps({
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        req = urllib.request.Request(
            url=f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 or 500 <= e.code < 600:
                if attempt < max_attempts - 1:
                    sleep_s = 1 << attempt  # 1, 2, 4
                    print(f"  retry {attempt+1}/{max_attempts} after HTTP {e.code} (sleep {sleep_s}s)", file=sys.stderr)
                    time.sleep(sleep_s)
                    continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < max_attempts - 1:
                sleep_s = 1 << attempt
                print(f"  retry {attempt+1}/{max_attempts} after transport error (sleep {sleep_s}s)", file=sys.stderr)
                time.sleep(sleep_s)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("call_gpt exhausted without exception")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)

    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    slots = build_slots()

    # Incremental writes: open the file once, fsync each line so a mid-run
    # crash leaves a partial-but-valid JSONL we can resume from later.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.out.open("w") as f:
        for slot in slots:
            prompt = slot_prompt(slot)
            raw = call_gpt(prompt, base_url, api_key)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json\n"):
                    raw = raw[len("json\n"):]
            rec = json.loads(raw)
            if rec.get("id") != slot.record_id:
                print(f"WARN: slot {slot.record_id} returned id={rec.get('id')}; fixing", file=sys.stderr)
                rec["id"] = slot.record_id
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            written += 1
            print(f"[{written}/50] {slot.record_id} ({slot.perspective}, {slot.language})", file=sys.stderr)

    print(f"Wrote {written} records to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
