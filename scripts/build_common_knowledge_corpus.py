#!/usr/bin/env python3
"""Synthetic CommonKnowledge eval corpus generator.

Produces HiToM-style stories where a target object's FINAL establishment is
randomly PUBLIC (all queried-group members present and witnessing) or PRIVATE
(an agent privately tells one group member, OR one group member leaves before
the move), plus distractor events (other objects moving, agents
entering/leaving) for complexity.

The direct question is:
    "Is it common knowledge among {A}, {B} and {C} that the {object} is in {L}?"

Gold answer:
    "yes"  iff  public=True  (all of {A,B,C} co-witnessed the final placement)
    "no"   iff  public=False (subset-private or leave-then-move pattern)

Story line format mirrors HiToM (numbered events):
    "1 A, B, C entered the room1."
    "2 A moved the ball to the box."
    "5 D privately told A that the ball is in the jar."

Usage:
    python scripts/build_common_knowledge_corpus.py \\
        --n 100 --out tests/data/ck_corpus.jsonl

    python scripts/build_common_knowledge_corpus.py \\
        --n 20 --out /tmp/ck_smoke.jsonl --seed 42
"""
from __future__ import annotations

import argparse
import json
import random as _random_module
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
_AGENT_NAMES = [
    "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
    "Isla", "Jack", "Kate", "Liam", "Mia", "Noah", "Olivia", "Paul",
]

_OBJECTS = [
    "ball", "book", "cup", "key", "lamp", "mug", "pen", "plant",
    "purse", "scarf", "shoe", "vase", "watch", "bottle", "coin",
]

_LOCATIONS = [
    "box", "basket", "cupboard", "drawer", "shelf", "bag", "cabinet",
    "jar", "crate", "container", "bin", "chest", "tray", "bucket",
]

_ROOMS = [
    "kitchen", "living_room", "office", "bedroom", "hallway",
    "garage", "basement", "attic", "study", "playroom",
]

_DISTRACTOR_VERBS = [
    "{actor} picked up the {obj}.",
    "{actor} looked at the {obj}.",
    "{actor} sat near the {obj}.",
    "{actor} admired the {obj}.",
]


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_item(seed: int, public: bool) -> dict[str, Any]:
    """Generate one synthetic CK eval item.

    Args:
        seed:   Seed for the seeded Random instance — deterministic output.
        public: If True, all group members co-witness the final placement
                → gold "yes".  If False, the final placement is private to
                a subset → gold "no".

    Returns a dict with:
        question_id  – str
        story        – numbered-event narrative (str)
        question     – the direct yes/no CK question (str)
        answer       – "yes" or "no" (str)
        meta         – {"public": bool, "group": [A,B,C], "object": ...,
                        "location": ..., "ability": "common_knowledge",
                        "lang": "en"}
    """
    rng = _random_module.Random(seed)

    # --- pick agents, room, objects ------------------------------------------
    agents_pool = list(_AGENT_NAMES)
    rng.shuffle(agents_pool)

    # Group size is always 3 (A, B, C); optionally 1-2 extra bystanders.
    n_extra = rng.randint(0, 2)
    total_agents = 3 + n_extra
    agents = agents_pool[:total_agents]
    group = agents[:3]            # the three queried agents
    extra = agents[3:]            # bystanders (may exist or not)

    room = rng.choice(_ROOMS)
    obj_pool = list(_OBJECTS)
    rng.shuffle(obj_pool)
    target_obj = obj_pool[0]
    distractor_objs = obj_pool[1:1 + rng.randint(1, 2)]

    loc_pool = list(_LOCATIONS)
    rng.shuffle(loc_pool)
    initial_loc = loc_pool[0]
    target_loc = loc_pool[1]
    distractor_locs = loc_pool[2:2 + len(distractor_objs)]

    # --- build story lines ---------------------------------------------------
    lines: list[str] = []

    def _line(text: str) -> None:
        lines.append(f"{len(lines) + 1} {text}")

    # Scene 1: everyone enters room together.
    all_in = ", ".join(agents)
    _line(f"{all_in} entered the {room}.")

    # Establish the initial location of the target object.
    _line(f"The {target_obj} is in the {initial_loc}.")

    # Distractor moves: some other object shuffled around while everyone watches.
    for dist_obj, dist_loc in zip(distractor_objs, distractor_locs):
        mover = rng.choice(group)
        _line(f"{mover} moved the {dist_obj} to the {dist_loc}.")
        # Add a flavour distractor line (likes/dislikes/saw) for noise.
        flavour_agent = rng.choice(agents)
        flavour_obj = rng.choice(distractor_objs)
        _line(f"{flavour_agent} dislikes the {flavour_obj}.")

    # --- final TARGET establishment (the load-bearing CK event) --------------

    if public:
        # PUBLIC: all of {A, B, C} (and extras) are present when the object moves.
        # One group member moves it; all others witness it.
        mover = rng.choice(group)
        _line(f"{mover} moved the {target_obj} to the {target_loc}.")
        # Optional: one extra bystander also present → still public to the group.
        if extra:
            _line(f"{rng.choice(extra)} made no movements and stayed in the {room}.")
        answer = "yes"

    else:
        # PRIVATE: two sub-variants, chosen randomly.
        variant = rng.choice(["leave_then_move", "private_tell"])

        if variant == "leave_then_move":
            # One group member leaves; the remaining two + extras witness the move.
            # The absentee does NOT learn the new location → not common knowledge.
            leaver = rng.choice(group)
            _line(f"{leaver} exited the {room}.")
            present = [a for a in agents if a != leaver]
            mover = rng.choice([a for a in present if a in group])
            _line(f"{mover} moved the {target_obj} to the {target_loc}.")
            # Leaver must NOT re-enter (that would let them witness it retroactively).

        else:  # private_tell
            # The object stays in initial_loc (or is moved before all witness it);
            # then ONE group member privately tells ANOTHER group member the location
            # while the third is absent.
            # To keep it simple: we first have one group member exit the room, then
            # agent_a privately tells agent_b, so agent_c (the exited one) never heard.
            # The "real" final placement here is target_loc established ONLY via the
            # private communication, not via a public physical move.

            # Step 1: one group member leaves.
            outsider = rng.choice(group)
            _line(f"{outsider} exited the {room}.")

            # Step 2: an agent moves the object (witnessed only by those still present;
            # outsider did NOT witness it).
            present_group = [a for a in group if a != outsider]
            mover = rng.choice(present_group)
            _line(f"{mover} moved the {target_obj} to the {target_loc}.")

            # Step 3: all re-enter a waiting room so private communication can happen.
            all_agents_str = ", ".join(agents)
            waiting = rng.choice([r for r in _ROOMS if r != room])
            _line(f"{outsider} entered the {waiting}.")
            _line(f"{', '.join([a for a in agents if a != outsider])} entered the {waiting}.")

            # Step 4: one insider privately tells the outsider (but NOT the third group member).
            teller = rng.choice(present_group)
            _line(
                f"{teller} privately told {outsider} that the {target_obj} is in the {target_loc}."
            )
            # At this point: teller + outsider know target_loc,
            # but the second present_group member (the non-teller) was NOT told.
            # → NOT common knowledge among the full group of three.

        answer = "no"

    # --- optional extra distractor lines after main event --------------------
    # A flavour line to pad the story and add noise.
    if rng.random() > 0.4:
        noise_agent = rng.choice(agents)
        noise_obj = rng.choice(distractor_objs) if distractor_objs else target_obj
        _line(f"{noise_agent} looked at the {noise_obj}.")

    # --- question ------------------------------------------------------------
    a_name, b_name, c_name = group
    question = (
        f"Is it common knowledge among {a_name}, {b_name} and {c_name} "
        f"that the {target_obj} is in the {target_loc}?"
    )

    story = "\n".join(lines)
    question_id = f"ck-{seed:06d}-{'pub' if public else 'priv'}"

    return {
        "question_id": question_id,
        "story": story,
        "question": question,
        "answer": answer,
        "meta": {
            "public": public,
            "group": group,
            "object": target_obj,
            "location": target_loc,
            "ability": "common_knowledge",
            "lang": "en",
        },
    }


def _to_tomeval_record(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a generate_item() output to the ToMEval normalized JSONL format.

    ToMEval's normalize_sample() expects:
        story       – str
        question    – str
        answer      – {"correct_answers": [str], "wrong_answers": [str]}
        meta        – dict (any extra fields forwarded as-is)
    """
    answer_str: str = item["answer"]
    wrong_str = "no" if answer_str == "yes" else "yes"
    meta = dict(item["meta"])
    meta["id"] = item["question_id"]

    return {
        "sample_id": item["question_id"],
        "story": item["story"],
        "question": item["question"],
        "answer": {
            "correct_answers": [answer_str],
            "wrong_answers": [wrong_str],
        },
        "meta": meta,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=100,
                   help="Total items to generate (half public, half private)")
    p.add_argument("--out", type=Path, required=True,
                   help="Output JSONL path")
    p.add_argument("--seed", type=int, default=0,
                   help="Base seed offset for item seeds (default 0)")
    args = p.parse_args(argv)

    n = args.n
    n_pub = n // 2
    n_priv = n - n_pub

    items: list[dict[str, Any]] = []
    for i in range(n_pub):
        items.append(generate_item(seed=args.seed + i, public=True))
    for i in range(n_priv):
        items.append(generate_item(seed=args.seed + i, public=False))

    # shuffle so public and private items are interleaved
    master_rng = _random_module.Random(args.seed)
    master_rng.shuffle(items)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(_to_tomeval_record(item), ensure_ascii=False) + "\n")

    n_yes = sum(1 for it in items if it["answer"] == "yes")
    n_no = sum(1 for it in items if it["answer"] == "no")
    print(f"wrote {len(items)} records (yes={n_yes}, no={n_no}) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
