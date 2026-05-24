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
        "Include exactly one 2nd-order ToM Statement: holder believes that "
        "another agent believes Z. Encode it as ONE Statement with "
        "predicate='believes', object=Z (the innermost clause as a plain "
        "string), nesting_depth=2."
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
  ({slot.perspective} MUST appear verbatim — do NOT substitute "DIRECT"/"SELF"/"EXPLICIT".)
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

holder_perspective MUST be one of: FIRST_PERSON, QUOTED, HEARSAY, INFERRED.
predicate must be one of: responsible_for, knows, prefers, promises, forbids, requires, located_at, member_of, believes, doubts.
modality must be one of: BELIEVES, DESIRES, INTENDS, COMMITS, ENFORCES, OBSERVES.
polarity must be one of: POS, NEG, UNKNOWN.
nesting_depth must be 0, 1, or 2 (use 2 only for "A believes B believes Z" pattern).
object must be a plain STRING — never a JSON object/dict/array.
For "promises" statements, object is the full action phrase including any temporal qualifier (e.g., "send the report before Friday"), not a noun summary.
For non-"promises" statements with controlled predicates, object is the minimal canonical noun phrase (e.g., "auth" not "auth service").

Now produce the JSON object."""


_ALLOWED_PERSPECTIVES = {"FIRST_PERSON", "QUOTED", "HEARSAY", "INFERRED"}
_ALLOWED_PREDICATES = {
    "responsible_for", "knows", "prefers", "promises", "forbids",
    "requires", "located_at", "member_of", "believes", "doubts",
}
_ALLOWED_MODALITIES = {
    "BELIEVES", "DESIRES", "INTENDS", "COMMITS", "ENFORCES", "OBSERVES",
}
_ALLOWED_POLARITIES = {"POS", "NEG", "UNKNOWN"}


def validate_record(rec: dict, slot: Slot) -> list[str]:
    """Return a list of validation errors for one record. Empty list = valid."""
    errors: list[str] = []
    if not isinstance(rec, dict):
        return ["record is not a JSON object"]
    if rec.get("id") != slot.record_id:
        errors.append(f"id mismatch: got {rec.get('id')!r}, want {slot.record_id!r}")
    convo = rec.get("conversation")
    if not isinstance(convo, list) or not convo:
        errors.append("conversation must be a non-empty list")
    truths = rec.get("ground_truth_statements")
    if not isinstance(truths, list) or not truths:
        return errors + ["ground_truth_statements must be a non-empty list"]
    has_depth_2 = False
    for i, s in enumerate(truths):
        prefix = f"truth[{i}]"
        if not isinstance(s, dict):
            errors.append(f"{prefix}: not a JSON object")
            continue
        for field in ("holder", "subject"):
            v = s.get(field)
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{prefix}.{field} must be a non-empty string, got {v!r}")
        obj = s.get("object")
        if not isinstance(obj, str) or not obj.strip():
            errors.append(f"{prefix}.object must be a non-empty STRING (not dict/list), got {type(obj).__name__}={obj!r}")
        persp = s.get("holder_perspective")
        if persp not in _ALLOWED_PERSPECTIVES:
            errors.append(f"{prefix}.holder_perspective {persp!r} not in {sorted(_ALLOWED_PERSPECTIVES)}")
        pred = s.get("predicate")
        if pred not in _ALLOWED_PREDICATES:
            errors.append(f"{prefix}.predicate {pred!r} not in {sorted(_ALLOWED_PREDICATES)}")
        mod = s.get("modality")
        if mod not in _ALLOWED_MODALITIES:
            errors.append(f"{prefix}.modality {mod!r} not in {sorted(_ALLOWED_MODALITIES)}")
        pol = s.get("polarity")
        if pol not in _ALLOWED_POLARITIES:
            errors.append(f"{prefix}.polarity {pol!r} not in {sorted(_ALLOWED_POLARITIES)}")
        depth = s.get("nesting_depth")
        if depth not in (0, 1, 2):
            errors.append(f"{prefix}.nesting_depth {depth!r} must be 0/1/2")
        if depth == 2:
            has_depth_2 = True
    if slot.has_nesting and not has_depth_2:
        errors.append("has_nesting slot but no truth with nesting_depth=2")
    primary = truths[0]
    if primary.get("holder_perspective") != slot.perspective:
        errors.append(
            f"primary truth holder_perspective {primary.get('holder_perspective')!r} "
            f"does not match slot {slot.perspective!r}")
    return errors


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
            rec = None
            last_errors: list[str] = []
            for schema_attempt in range(3):
                raw = call_gpt(prompt, base_url, api_key)
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.strip("`")
                    if raw.startswith("json\n"):
                        raw = raw[len("json\n"):]
                try:
                    candidate = json.loads(raw)
                except json.JSONDecodeError as e:
                    last_errors = [f"JSON parse failure: {e}"]
                    print(f"  schema-attempt {schema_attempt+1}/3 for {slot.record_id}: JSON parse failed", file=sys.stderr)
                    continue
                if candidate.get("id") != slot.record_id:
                    candidate["id"] = slot.record_id
                last_errors = validate_record(candidate, slot)
                if not last_errors:
                    rec = candidate
                    break
                print(f"  schema-attempt {schema_attempt+1}/3 for {slot.record_id}: {len(last_errors)} validation errors", file=sys.stderr)
                for err in last_errors[:3]:
                    print(f"    - {err}", file=sys.stderr)
            if rec is None:
                print(f"FATAL: slot {slot.record_id} failed schema validation 3 times", file=sys.stderr)
                for err in last_errors:
                    print(f"  - {err}", file=sys.stderr)
                return 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            written += 1
            print(f"[{written}/50] {slot.record_id} ({slot.perspective}, {slot.language})", file=sys.stderr)

    print(f"Wrote {written} records to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
