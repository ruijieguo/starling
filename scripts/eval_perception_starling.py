#!/usr/bin/env python3
"""Starling-in-the-loop ToMBench False-Belief eval (sub-project B, perception track).

This harness measures **Starling's perception → belief machinery** end to end on
the ToMBench Location-False-Belief subset:

    remember(narrative)                # real model (or a stub in --fixture mode)
      -> EpisodicExtractor             # narrative -> OCCURRED events + episodic_events
      -> PerceptionReconstructor       # events -> per-cognizer perception_state (wired
                                       #            into remember(), best-effort)
      -> what_does_X_think(asked, theme)  # X's last-perceived location of the theme
      -> map the perceived location to a multiple-choice option
      -> score vs record["options"][int(record["answer"])]

Why the Location-False-Belief "where does X look for Y" family maps cleanly. Each
item is a Sally-Anne scene: two characters see containers in a room, the item is
found in container A, one character LEAVES, the other MOVES the item to container
B. "After ... returns, where does X look for the item?" is exactly X's last-
perceived location: the mover (who stayed) looks in B (fresh); the leaver (who
left before the move) looks in A (stale). Starling computes this deterministically
in C++ (perception_state.last_known vs latest_event_location for is_stale), so the
number reflects Starling's machinery — in --fixture mode with NO LLM at all, and
in real mode the extraction → memory pipeline end to end.

Corpus
------
Expected corpus file (the merged ToMBench export):

    tests/data/eval_tom_bench/full.jsonl

filtered to ability == "Belief: Location false beliefs" AND a question of the
"where does <X> look/search for <theme>" shape (100 such items). Each record:

    {"question_id","context","question","options":[...4...],"answer":<0-3 idx>,
     "ability":"Belief: Location false beliefs","task":"False Belief Task"}

Note on the Knowledge ability. ToMBench's "Knowledge: *" abilities (Information-
knowledge links, Percepts-knowledge links, ...) are NUMERIC/counting probes
("how many of these 5 letters contain checks?") whose options are quantities, not
container locations. They do not map onto B's location/content perception model
and are intentionally NOT scored here; B's supported ToMBench surface is the
False-Belief location family. (does_X_know-over-events — Task 5.1 — is wired into
the reconstructor and unit-tested in tests/cpp/test_perception_reconstructor.cpp;
it is not part of this multiple-choice accuracy harness.)

Modes
-----
  --fixture   Deterministic self-test: feed 1+ hand-built fixture items through
              the FULL harness pipeline with a STUB LLM (canned episodic JSON).
              No network. Proves the harness wiring (parse -> remember -> A -> B
              -> what_does_X_think -> option mapping -> score) end to end. This is
              also exercised by tests/python/test_eval_perception_harness.py.

  (real)      Default. Reads --corpus, extracts each narrative with a REAL model,
              runs the pipeline, scores accuracy. Burns API; run on demand only.

On-demand real run (DeepSeek convention; reasoning models need the large cap):

    OPENAI_API_KEY=$DEEPSEEK_API_KEY \\
    OPENAI_BASE_URL=https://api.deepseek.com/v1 \\
    .venv/bin/python scripts/eval_perception_starling.py \\
        --corpus tests/data/eval_tom_bench/full.jsonl \\
        --model deepseek-v4-pro \\
        --report build/eval_perception_starling.md

Exit code: 0 if precision >= PRECISION_THRESHOLD (0.70), else 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import starling
from starling import _core
from starling.tom import what_does_X_think

PRECISION_THRESHOLD = 0.70
_NOW = "2026-06-16T10:00:00Z"
_MAX_ANSWER_TOKENS = 32768  # reasoning models count hidden CoT toward the budget

# The ToMBench ability slug B scores (full-prose slug as it appears in full.jsonl).
LOCATION_FALSE_BELIEF_ABILITY = "Belief: Location false beliefs"

# "where does <X> look/search for <theme>" — capture the asked cognizer + theme.
# The theme may carry a trailing "after <...> returns ..." clause that we strip.
_RE_LOOK = re.compile(
    r"where does (.+?) (?:look|search)(?:es)? for (?:the |a |an )?(.+?)\s*\??$",
    re.I,
)
# Trailing temporal clause that sometimes lands inside the theme capture.
_RE_TRAILING_CLAUSE = re.compile(
    r"\s+(?:after|before|when|once)\b.*$", re.I
)


# ---------------------------------------------------------------------------
# Question parsing
# ---------------------------------------------------------------------------

class Probe:
    """A scorable perception probe derived from one ToMBench record."""

    def __init__(self, *, asked: str, theme: str, gold: str,
                 options: list[str], context: str):
        self.asked = asked      # the cognizer whose belief is queried
        self.theme = theme      # the item the belief is about
        self.gold = gold        # the gold option string
        self.options = options
        self.context = context


def parse_probe(record: dict[str, Any]) -> Probe | None:
    """Parse (asked cognizer, theme) from a 'where does X look for Y' question.

    Returns None for records that are not a location-look false-belief probe.
    """
    if record.get("ability") != LOCATION_FALSE_BELIEF_ABILITY:
        return None
    q = (record.get("question") or "").strip()
    m = _RE_LOOK.search(q)
    if not m:
        return None
    asked = m.group(1).strip()
    theme = _RE_TRAILING_CLAUSE.sub("", m.group(2).strip()).strip()
    if not asked or not theme:
        return None
    options = record.get("options") or []
    ans = record.get("answer")
    if not options or not isinstance(ans, int) or not (0 <= ans < len(options)):
        return None
    return Probe(asked=asked, theme=theme, gold=options[ans], options=options,
                 context=record.get("context", ""))


# ---------------------------------------------------------------------------
# Option mapping
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def map_to_option(perceived: str, options: list[str]) -> str | None:
    """Map a perceived location value to the closest multiple-choice option.

    Exact normalized match first, then containment either way (handles "backpack"
    vs "Backpack", "storage locker" vs "Storage locker"). Returns the option
    string, or None if nothing matches.
    """
    p = _norm(perceived)
    if not p:
        return None
    for opt in options:  # exact normalized match wins
        if _norm(opt) == p:
            return opt
    for opt in options:  # then containment
        o = _norm(opt)
        if o and (p in o or o in p):
            return opt
    return None


# ---------------------------------------------------------------------------
# Per-item pipeline: remember -> A -> B -> what_does_X_think -> score
# ---------------------------------------------------------------------------

def run_probe(probe: Probe, narrative: str, llm) -> tuple[bool, str]:
    """Run ONE probe through the full pipeline. Returns (correct, detail).

    narrative is the text fed to remember(); llm is the adapter that drives the
    extraction (a real model in real mode, a canned-episodic stub in fixture
    mode). The wired remember() runs A (events) then B (reconstruct).
    """
    db = tempfile.mktemp(suffix=".db")
    mem = starling.Memory.open(db, agent="narrator", llm=llm)
    try:
        try:
            mem.remember(narrative, now=_NOW)
        except Exception as exc:  # extraction/remember failure → miss this probe, don't abort
            return False, f"remember failed: {exc}"
        adapter = mem._rt.adapter
        tenant = mem._core.tenant
        frontier = _core.KnowledgeFrontier(adapter)
        belief = what_does_X_think(
            adapter, frontier, x=probe.asked, theme=probe.theme, tenant_id=tenant)
        if not belief.has_belief:
            return False, f"no belief for ({probe.asked!r},{probe.theme!r})"
        picked = map_to_option(belief.state_value, probe.options)
        if picked is None:
            return False, f"perceived={belief.state_value!r} maps to no option"
        correct = _norm(picked) == _norm(probe.gold)
        return correct, (f"perceived={belief.state_value!r} -> option={picked!r} "
                         f"gold={probe.gold!r}")
    finally:
        mem.close()
        if os.path.exists(db):
            os.remove(db)


# ---------------------------------------------------------------------------
# Fixture mode: hand-built items + canned episodic JSON (no LLM)
# ---------------------------------------------------------------------------

def _episodic_json(events: list[dict[str, Any]]) -> str:
    """Serialize episodic events to the canned-response JSON the stub LLM returns.

    The belief/conversation pass parse-fails to empty on these (no subject/
    predicate/object keys); the episodic pass reads them as OCCURRED events.
    """
    return json.dumps(events)


# Two hand-built fixtures exercising the FULL harness pipeline deterministically.
# Each bundles a ToMBench-shaped record + the canned episodic JSON a real model
# WOULD have produced. Self-test proves parse -> remember -> A -> B ->
# what_does_X_think -> option-map -> score is correctly wired without any API.
FIXTURES: list[dict[str, Any]] = [
    {
        # (1) Sally-Anne location false belief — the asked cognizer LEFT before the
        # move, so her last-perceived location is the ORIGINAL (basket). Gold=Basket.
        "record": {
            "question_id": "fx-loc-fb-001",
            "context": ("Sally and Anne are in the room. They find a ball in the "
                        "basket. Sally leaves the room. Anne moves the ball to the box."),
            "question": "After Sally returns to the room, where does Sally look for the ball?",
            "options": ["Box", "Basket", "Drawer", "Shelf"],
            "answer": 1,  # Basket — Sally's stale belief
            "ability": LOCATION_FALSE_BELIEF_ABILITY,
            "task": "False Belief Task",
        },
        "episodic": _episodic_json([
            {"actor": "Sally", "action": "put", "theme": "ball", "location": "basket",
             "participants": ["Sally", "Anne"], "time": None},
            {"actor": "Sally", "action": "leave", "theme": "room", "location": None,
             "participants": ["Sally"], "time": None},
            {"actor": "Anne", "action": "move", "theme": "ball", "location": "box",
             "participants": ["Anne"], "time": None},
        ]),
    },
    {
        # (2) Perception/knowledge item — the asked cognizer STAYED and witnessed the
        # move, so her last-perceived location is the NEW one (box). Gold=Box. This
        # is the "knew because present" complement to the false-belief case.
        "record": {
            "question_id": "fx-loc-kn_001",
            "context": ("Tom and Mary are in the kitchen. They find a key in the "
                        "drawer. Tom leaves the kitchen. Mary moves the key to the cupboard."),
            "question": "Where does Mary look for the key?",
            "options": ["Drawer", "Fridge", "Cupboard", "Sink"],
            "answer": 2,  # Cupboard — Mary witnessed the move
            "ability": LOCATION_FALSE_BELIEF_ABILITY,
            "task": "False Belief Task",
        },
        "episodic": _episodic_json([
            {"actor": "Mary", "action": "put", "theme": "key", "location": "drawer",
             "participants": ["Tom", "Mary"], "time": None},
            {"actor": "Tom", "action": "leave", "theme": "kitchen", "location": None,
             "participants": ["Tom"], "time": None},
            {"actor": "Mary", "action": "move", "theme": "key", "location": "cupboard",
             "participants": ["Mary"], "time": None},
        ]),
    },
]


def run_fixture_self_test() -> tuple[int, int, list[str]]:
    """Run every FIXTURE through the full pipeline with a stub LLM.

    Returns (correct, total, detail_lines). Used by both --fixture CLI mode and
    the pytest self-test. NO network.
    """
    correct = 0
    total = 0
    details: list[str] = []
    for fx in FIXTURES:
        record = fx["record"]
        probe = parse_probe(record)
        if probe is None:
            details.append(f"FAIL parse qid={record['question_id']}: probe is None")
            total += 1
            continue
        llm = starling.make_stub_llm(default_response=fx["episodic"])
        ok, detail = run_probe(probe, record["context"], llm)
        total += 1
        correct += int(ok)
        details.append(
            f"{'OK  ' if ok else 'MISS'} qid={record['question_id']} "
            f"asked={probe.asked!r} theme={probe.theme!r} {detail}")
    return correct, total, details


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(path: Path, mode: str, total: int, correct: int,
                 skipped: int) -> None:
    precision = correct / total if total else 0.0
    verdict = "PASS" if precision >= PRECISION_THRESHOLD else "**FAIL**"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Starling perception ToMBench eval (sub-project B)\n\n"
        f"mode: **{mode}**  |  ability: `{LOCATION_FALSE_BELIEF_ABILITY}`\n\n"
        "Pipeline: remember -> EpisodicExtractor -> PerceptionReconstructor -> "
        "what_does_X_think -> option map -> score.\n\n"
        "| metric | value | threshold | verdict |\n"
        "|---|---|---|---|\n"
        f"| precision | {precision:.4f} ({correct}/{total}) | "
        f"{PRECISION_THRESHOLD:.2f} | {verdict} |\n"
        f"| skipped (unparseable / wrong shape) | {skipped} | | |\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Starling perception ToMBench eval (sub-project B).")
    p.add_argument("--corpus", type=Path,
                   help="Path to ToMBench JSONL (e.g. tests/data/eval_tom_bench/full.jsonl)")
    p.add_argument("--fixture", action="store_true",
                   help="Deterministic self-test with hand-built fixtures (no LLM)")
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--base-url", default=None,
                   help="Override the LLM base url (else OPENAI_BASE_URL or OpenAI)")
    p.add_argument("--max-items", type=int, default=None)
    p.add_argument("--report", type=Path,
                   default=Path("build/eval_perception_starling.md"))
    args = p.parse_args(argv)

    # ---- fixture / deterministic self-test ----
    if args.fixture:
        correct, total, details = run_fixture_self_test()
        for d in details:
            print("  " + d, file=sys.stderr)
        write_report(args.report, "fixture", total, correct, skipped=0)
        precision = correct / total if total else 0.0
        if total > 0 and correct == total:
            print(f"PASS — fixture self-test {correct}/{total} correct "
                  f"(precision {precision:.4f})")
            return 0
        print(f"BLOCKED — fixture self-test {correct}/{total} correct "
              f"(precision {precision:.4f})")
        return 1

    # ---- real mode ----
    if args.corpus is None:
        print("ERROR: --corpus is required in real mode (or pass --fixture)",
              file=sys.stderr)
        return 1
    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 1

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set (needed for real mode). For DeepSeek: "
              "OPENAI_API_KEY=$DEEPSEEK_API_KEY "
              "OPENAI_BASE_URL=https://api.deepseek.com/v1", file=sys.stderr)
        return 1
    base_url = args.base_url or os.environ.get(
        "OPENAI_BASE_URL", "https://api.openai.com/v1")

    records = [json.loads(l) for l in args.corpus.read_text().splitlines()
               if l.strip()]
    if not records:
        print("ERROR: corpus is empty", file=sys.stderr)
        return 1

    # Filter to scorable location-look false-belief probes.
    probes: list[Probe] = []
    skipped = 0
    for rec in records:
        if rec.get("ability") != LOCATION_FALSE_BELIEF_ABILITY:
            continue  # other abilities are out of B's supported surface (not "skipped")
        probe = parse_probe(rec)
        if probe is None:
            skipped += 1  # location-FB but not a "where does X look" shape
            continue
        probes.append(probe)
    if args.max_items is not None:
        probes = probes[: args.max_items]
    if not probes:
        print("ERROR: no scorable location-look false-belief probes in corpus",
              file=sys.stderr)
        return 1
    print(f"Loaded {len(probes)} location-look false-belief probes "
          f"(skipped {skipped} other-shape location-FB)", file=sys.stderr)

    # Build the adapter directly so we can raise max_tokens: reasoning models
    # (deepseek-v4-pro) count hidden chain-of-thought toward the token budget, and
    # the 4096 default truncates extraction to empty (0 events -> every probe would
    # wrongly score has_belief=false). _MAX_ANSWER_TOKENS = 32768. A generous
    # per-call timeout covers slow reasoning responses.
    _cfg = _core.OpenAIAdapterConfig.from_env()
    _cfg.model = args.model
    if base_url:
        _cfg.base_url = base_url
    _cfg.max_tokens = _MAX_ANSWER_TOKENS
    _cfg.timeout_ms = 180000
    llm = _core.OpenAIAdapter(_cfg)

    total = correct = 0
    for idx, probe in enumerate(probes):
        ok, detail = run_probe(probe, probe.context, llm)
        total += 1
        correct += int(ok)
        if not ok:
            print(f"  MISS asked={probe.asked!r} theme={probe.theme!r} {detail}",
                  file=sys.stderr)
        if (idx + 1) % 20 == 0:
            print(f"  [{idx + 1}/{len(probes)}] {correct}/{total} correct",
                  file=sys.stderr)

    write_report(args.report, "real", total, correct, skipped)
    precision = correct / total if total else 0.0
    print(f"Report written to {args.report} (skipped {skipped})", file=sys.stderr)
    if precision >= PRECISION_THRESHOLD:
        print(f"PASS — precision {precision:.4f} ({correct}/{total}) "
              f">= {PRECISION_THRESHOLD}")
        return 0
    print(f"BLOCKED — precision {precision:.4f} ({correct}/{total}) "
          f"< {PRECISION_THRESHOLD}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
