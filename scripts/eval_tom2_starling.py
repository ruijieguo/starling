#!/usr/bin/env python3
"""Starling-in-the-loop second-order ToM MEMORY eval (P3.a2, track 2).

Track 1 (``scripts/eval_tom_bench.py --order second``) sends ToMBench questions
straight to an LLM and measures the LLM's *intrinsic* second-order ToM. It never
touches Starling. This harness (track 2) measures **Starling's second-order
MEMORY machinery** end to end:

    multi-holder first-order beliefs
      -> _core.belief_tracker_tick           (programmatic depth-1 meta-belief)
      -> mem.tick()                          (consolidation)
      -> _core.what_does_X_think_Y_believes  (META_BELIEF recall)
      -> score recalled inner belief vs the ToMBench gold answer

Why this maps cleanly. A ToMBench second-order item is a false-belief probe:
"where does A think B looks for X?" / "what does A think B expects to find in C?"
The gold answer is B's STALE belief — B left before A moved/swapped the item, so
B still believes the original value L1. Starling represents this correctly
because its deterministic nester models B's belief from B's last first-hand
statement and never rewrites it from A's (different-holder) knowledge. The eval
seeds B's original belief L1 and A's updated knowledge L2, then asserts the
recall of "what A thinks B believes" returns L1, never L2 (holder segregation =
the memory-level false-belief property). The LLM does NOT do the nesting — that
is deterministic C++ — so this number reflects Starling, not a model's reasoning.

Two modes derive the multi-holder beliefs to seed:

  deterministic  Parse the templated question for structure; L1 = gold option,
                 L2 = a distractor option. No LLM in the loop — isolates
                 Starling's production/consolidation/recall/segregation fidelity.

  extracted      Use an LLM (deepseek-v4-pro) to read the raw story and emit
                 {peer, subject, original, new}; seed those. Measures the
                 realistic extraction -> Starling-memory pipeline end to end.
                 Failures are dominated by extraction quality, since the
                 machinery is deterministic (see the deterministic number).

Exit code: 0 if precision >= 0.70 (P3.a2 admission), else 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import starling
from starling import _core

PRECISION_THRESHOLD = 0.70
_NOW = "2026-06-12T10:00:00Z"
_ASOF = "2026-06-13T00:00:00Z"

# ToMBench English translation-drift items: a Chinese near-synonym (橱柜/柜子,
# 手提袋/手提包, 箱子) is rendered one way in the English STORY and another in the
# English OPTIONS, so the English gold option never appears in the English story
# and is unanswerable as labelled (the Chinese side is internally consistent;
# deepseek-v4-pro picks the story-consistent option, not the broken gold). These
# are corpus defects, not model/Starling failures, so they are excluded from the
# clean precision. See tests/data/eval_tom_bench/README.md.
_KNOWN_DRIFT_QIDS = frozenset(
    {"tb-so-002", "tb-so-035", "tb-so-047", "tb-so-053"}
)
# Stub LLM canned reply: never exercised here (we seed statements directly), but
# Memory.open requires an llm; a flat first-order reply keeps it inert.
_CANNED = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"x",'
    '"predicate":"p","object":"o","modality":"BELIEVES","polarity":"POS",'
    '"nesting_depth":0}]'
)
_MAX_ANSWER_TOKENS = 32768

# Templated-question parsers (the corpus has exactly two question shapes).
_RE_LOCATION = re.compile(
    r"where does (.+?) think (.+?) looks? for (?:the |a )?(.+?)\??$", re.I
)
_RE_CONTENT = re.compile(
    r"what does (.+?) think (.+?) (?:expects?|expect) to find "
    r"(?:in|inside) (?:the |a )?(.+?)\??$",
    re.I,
)


# ---------------------------------------------------------------------------
# Structure derivation
# ---------------------------------------------------------------------------

class Case:
    """A seedable second-order scenario derived from one ToMBench record."""

    def __init__(self, *, predicate: str, l1: str, l2: str, gold: str):
        self.predicate = predicate  # "located_in" | "contains" (label only)
        self.l1 = l1                # peer's stale belief value (== gold)
        self.l2 = l2                # observer's updated knowledge (distractor)
        self.gold = gold            # ToMBench gold option string


def derive_deterministic(record: dict[str, Any]) -> Case | None:
    """Derive a Case from the templated question + gold option (no LLM)."""
    q = record["question"].strip()
    if _RE_LOCATION.search(q):
        predicate = "located_in"
    elif _RE_CONTENT.search(q):
        predicate = "contains"
    else:
        return None
    gold = record["options"][int(record["answer"])]
    distractors = [o for o in record["options"] if o != gold]
    if not distractors:
        return None
    return Case(predicate=predicate, l1=gold, l2=distractors[0], gold=gold)


# ---------------------------------------------------------------------------
# Extracted mode: LLM reads the raw story -> structured facts
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """\
Read this short story and the multiple-choice options, then extract the
second-order false-belief structure as JSON.

Story:
{context}

Question:
{question}

Options:
{options}

The question asks what character A thinks character B believes. B left or looked
away before A moved/swapped an item, so B still believes the ORIGINAL value while
A knows the NEW value. Return ONLY a JSON object, no prose:

{{"peer": "<B, the character whose stale belief is asked about>",
  "subject": "<the object or container the belief is about>",
  "original": "<the value B still believes — matches one option>",
  "new": "<the value A changed it to>"}}"""


def _extract_via_llm(record: dict[str, Any], base_url: str, api_key: str,
                     model: str) -> Case | None:
    prompt = _EXTRACT_PROMPT.format(
        context=record["context"],
        question=record["question"],
        options="\n".join(f"- {o}" for o in record["options"]),
    )
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": _MAX_ANSWER_TOKENS,
    }).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", content, re.S)
            if not m:
                return None
            data = json.loads(m.group(0))
            orig, new = str(data["original"]).strip(), str(data["new"]).strip()
            gold = record["options"][int(record["answer"])]
            return Case(predicate="located_in", l1=orig, l2=new, gold=gold)
        except Exception as exc:  # noqa: BLE001 — network/parse, retry then skip
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"WARN: extract failed qid={record.get('question_id')}: "
                      f"{exc}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Seed a single isolated Starling db with the multi-holder beliefs
# ---------------------------------------------------------------------------

def _seed(db_path: str, case: Case) -> None:
    import sqlite3
    c = sqlite3.connect(db_path)
    try:
        c.execute("PRAGMA busy_timeout = 5000")
        c.execute(
            "INSERT INTO cognizers(id,tenant_id,kind,canonical_name,"
            "canonical_name_normalized,external_id,created_at,last_seen_at) "
            "VALUES('observer','default','self','Observer','observer','',?,?)",
            (_NOW, _NOW))
        # peer's first-hand (stale) belief: subject=item -> L1
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,"
            "polarity,confidence,observed_at,salience,affect_json,activation,"
            "last_accessed,provenance,evidence_json,consolidation_state,"
            "review_status,nesting_depth,created_at,updated_at) VALUES("
            "'PEER1','default','peer','FIRST_PERSON','entity','item',?,'str',?,"
            "'h-peer1','v1','BELIEVES','POS',0.8,?,0.6,'{}',0.0,?,'user_input',"
            "'[{\"engram_id\":\"eng-peer1\"}]','consolidated','approved',0,?,?)",
            (case.predicate, case.l1, _NOW, _NOW, _NOW, _NOW))
        c.execute(
            "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,"
            "aggregate_id,outbox_sequence,idempotency_key,payload_json,"
            "created_at) VALUES('ev-peer1','default','statement.written',"
            "'PEER1','PEER1',900001,'ik-peer1',"
            "'{\"stmt_id\":\"PEER1\",\"engram_ref_id\":\"eng-peer1\"}',?)",
            (_NOW,))
        # observer's updated knowledge: subject=item -> L2 (the move/swap).
        # Different holder, so it must NOT leak into peer's modeled belief.
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,"
            "polarity,confidence,observed_at,salience,affect_json,activation,"
            "last_accessed,provenance,evidence_json,consolidation_state,"
            "review_status,nesting_depth,created_at,updated_at) VALUES("
            "'OBS1','default','observer','FIRST_PERSON','entity','item',?,'str',"
            "?,'h-obs1','v1','BELIEVES','POS',0.9,?,0.6,'{}',0.0,?,'user_input',"
            "'[{\"engram_id\":\"eng-obs1\"}]','consolidated','approved',0,?,?)",
            (case.predicate, case.l2, _NOW, _NOW, _NOW, _NOW))
        c.commit()
    finally:
        c.close()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _matches(recalled: str, gold: str) -> bool:
    r, g = _norm(recalled), _norm(gold)
    return bool(r) and (r == g or r in g or g in r)


def run_case(case: Case) -> tuple[bool, str]:
    """Seed -> tick -> recall one case. Returns (correct, recalled_value)."""
    db = tempfile.mktemp(suffix=".db")
    mem = starling.Memory.open(
        db, agent="observer", llm=starling.make_stub_llm(default_response=_CANNED))
    try:
        _seed(db, case)
        _core.belief_tracker_tick(mem._rt.adapter)
        mem.tick()
        nested = _core.what_does_X_think_Y_believes(
            mem._rt.adapter, "observer", "peer", "default", _ASOF)
        if not nested:
            return False, "<empty>"
        recalled = getattr(nested[0].inner, "object_value", "") or ""
        # Correct iff recall is peer's stale L1 (== gold). Segregation guard: the
        # recalled value must not be observer's updated L2 — exact-normalized, not
        # substring, so an incidental overlap (e.g. "Cabinet" within "Storage
        # cabinet") is not scored as a false miss.
        correct = _matches(recalled, case.gold) and _norm(recalled) != _norm(case.l2)
        return correct, recalled
    finally:
        mem.close()
        if os.path.exists(db):
            os.remove(db)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(path: Path, mode: str, total: int, correct: int,
                 skipped: int, excluded: int) -> None:
    precision = correct / total if total else 0.0
    verdict = "PASS" if precision >= PRECISION_THRESHOLD else "**FAIL**"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Starling second-order memory eval (track 2)\n\n"
        f"mode: **{mode}**\n\n"
        "| metric | value | threshold | verdict |\n"
        "|---|---|---|---|\n"
        f"| precision (clean) | {precision:.4f} ({correct}/{total}) | "
        f"{PRECISION_THRESHOLD:.2f} | {verdict} |\n"
        f"| excluded (ToMBench EN translation drift) | {excluded} | | |\n"
        f"| skipped (unparseable) | {skipped} | | |\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Starling second-order memory eval.")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--mode", choices=["deterministic", "extracted"],
                   default="deterministic")
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--max-items", type=int, default=None)
    p.add_argument("--report", type=Path,
                   default=Path("build/eval_tom2_starling.md"))
    args = p.parse_args(argv)

    records = [json.loads(l) for l in args.corpus.read_text().splitlines()
               if l.strip()]
    if args.max_items is not None:
        records = records[: args.max_items]
    if not records:
        print("ERROR: corpus is empty", file=sys.stderr)
        return 1

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if args.mode == "extracted" and not api_key:
        print("ERROR: OPENAI_API_KEY not set (needed for --mode extracted)",
              file=sys.stderr)
        return 1

    total = correct = skipped = excluded = 0
    for idx, rec in enumerate(records):
        if rec.get("question_id") in _KNOWN_DRIFT_QIDS:
            excluded += 1
            continue
        if args.mode == "deterministic":
            case = derive_deterministic(rec)
        else:
            case = _extract_via_llm(rec, base_url, api_key, args.model)
            time.sleep(0.3)
        if case is None:
            skipped += 1
            continue
        ok, recalled = run_case(case)
        total += 1
        correct += int(ok)
        if not ok:
            print(f"  MISS qid={rec.get('question_id')} gold={case.gold!r} "
                  f"recalled={recalled!r}", file=sys.stderr)
        if (idx + 1) % 20 == 0:
            print(f"  [{idx + 1}/{len(records)}] {correct}/{total} correct, "
                  f"{skipped} skipped", file=sys.stderr)

    write_report(args.report, args.mode, total, correct, skipped, excluded)
    precision = correct / total if total else 0.0
    print(f"Report written to {args.report} "
          f"(excluded {excluded} drift, skipped {skipped})", file=sys.stderr)
    if precision >= PRECISION_THRESHOLD:
        print(f"PASS — precision {precision:.4f} ({correct}/{total}) "
              f">= {PRECISION_THRESHOLD}")
        return 0
    print(f"BLOCKED — precision {precision:.4f} ({correct}/{total}) "
          f"< {PRECISION_THRESHOLD}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
