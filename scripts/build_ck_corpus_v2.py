#!/usr/bin/env python3
"""Harder + cleaner CommonKnowledge eval (v2).

Fixes the v1 ambiguity (co-presence-at-a-move => CK was a contestable convention
deepseek defensibly rejected). v2 establishes CK ONLY via an EXPLICIT PUBLIC
ANNOUNCEMENT ("X publicly announced to everyone in the room that the OBJ is in
the LOC") — an unambiguous common-knowledge act even under a strict reading. The
hard part is purely TRACKING: which announcement was about the target, and who
was present for it, amid presence churn + distractor announcements.

Four variants (balanced), gold defensible:
  public_announce       (CK=yes)  all of G present at the public announcement.
  reentry_restore       (CK=yes)  a member leaves, target moves (they miss it),
                                  they RETURN, then a public re-announcement to
                                  all -> CK restored. (must integrate re-announce)
  absent_at_announce    (CK=no)   a member is OUT at the announcement, then RETURNS
                                  after (deceptive) but is never re-told -> not CK.
  separate_private_tells(CK=no)   target conveyed by SEPARATE private tells to each
                                  member, never one public announcement -> all know
                                  but NOT common knowledge.

The discriminator the model must compute: "was there a single public announcement
(or co-witnessed event) of the target fact that ALL THREE were present for?" This
is exactly what is_common_knowledge computes (latest theme-event co-witnessed by
all). Gold is announcement-based, NOT co-presence-based -> a model failure here is
a real tracking/CK gap, not a definitional disagreement.
"""
from __future__ import annotations

import argparse
import json
import random as _rnd
from pathlib import Path
from typing import Any

_AGENT_NAMES = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
                "Isla", "Jack", "Kate", "Liam", "Mia", "Noah", "Olivia", "Paul"]
_OBJECTS = ["ball", "book", "cup", "key", "lamp", "mug", "pen", "plant",
            "purse", "scarf", "shoe", "vase", "watch", "bottle", "coin"]
_LOCATIONS = ["box", "basket", "cupboard", "drawer", "shelf", "bag", "cabinet",
              "jar", "crate", "container", "bin", "chest", "tray", "bucket"]
_ROOMS = ["kitchen", "living_room", "office", "bedroom", "hallway",
          "garage", "basement", "attic", "study", "playroom"]

VARIANTS = ["public_announce", "reentry_restore", "absent_at_announce", "separate_private_tells"]
_YES = {"public_announce", "reentry_restore"}


def generate_item_v2(seed: int, variant: str) -> dict[str, Any]:
    rng = _rnd.Random(seed)
    names = list(_AGENT_NAMES); rng.shuffle(names)
    n_extra = rng.randint(1, 2)
    agents = names[:3 + n_extra]
    group = agents[:3]
    extras = agents[3:]
    room = rng.choice(_ROOMS)

    objs = list(_OBJECTS); rng.shuffle(objs)
    target = objs[0]
    dist_objs = objs[1:1 + rng.randint(1, 2)]
    locs = list(_LOCATIONS); rng.shuffle(locs)
    init_loc, target_loc = locs[0], locs[1]
    dist_locs = locs[2:2 + len(dist_objs)]

    lines: list[str] = []
    present = set()

    def line(t: str) -> None:
        lines.append(f"{len(lines) + 1} {t}")

    def enter(who: list[str]) -> None:
        present.update(who)
        line(f"{', '.join(who)} entered the {room}.")

    def leave(a: str) -> None:
        present.discard(a)
        line(f"{a} exited the {room}.")

    def reenter(a: str) -> None:
        present.add(a)
        line(f"{a} entered the {room}.")

    def move(a: str, obj: str, loc: str) -> None:
        line(f"{a} moved the {obj} to the {loc}.")

    def announce(a: str, obj: str, loc: str) -> None:
        line(f"{a} publicly announced to everyone in the {room} that the {obj} is in the {loc}.")

    def tell(a: str, b: str, obj: str, loc: str) -> None:
        line(f"{a} privately told {b} that the {obj} is in the {loc}.")

    def distractor() -> None:
        """A noise event: a distractor object move, a distractor PUBLIC announcement
        (about another object), or a flavour line. Forces target-tracking."""
        kind = rng.choice(["move", "announce", "flavour"])
        actor = rng.choice([a for a in agents if a in present] or group)
        do = rng.choice(dist_objs)
        dl = rng.choice(dist_locs)
        if kind == "move":
            move(actor, do, dl)
        elif kind == "announce":
            announce(actor, do, dl)  # decoy public announcement about ANOTHER object
        else:
            line(f"{actor} looked at the {do}.")

    # --- setup: everyone enters; target's initial location is stated -----------
    enter(agents)
    line(f"The {target} is in the {init_loc}.")
    for _ in range(rng.randint(1, 2)):
        distractor()

    g0, g1, g2 = group  # g0 acts as mover/announcer/teller; g1 the typical leaver

    if variant == "public_announce":
        # All of G present. The MOVER announces (announcer == mover) so the
        # announcement is always epistemically grounded — the speaker did the move
        # and demonstrably knows the location. (A random non-mover announcer would
        # be announcing a fact they may not have witnessed, which a rigorous reader
        # correctly flags as unfounded -> not CK; that was a generator bug, not a
        # model failure.)
        mover = rng.choice(group)
        move(mover, target, target_loc)
        if rng.random() < 0.5:
            distractor()
        announce(mover, target, target_loc)

    elif variant == "reentry_restore":
        leaver = g1
        leave(leaver)
        if rng.random() < 0.5:
            distractor()
        move(g0, target, target_loc)            # leaver misses the move
        reenter(leaver)                          # leaver comes back
        if rng.random() < 0.5:
            distractor()
        announce(g0, target, target_loc)         # public re-announcement -> CK restored

    elif variant == "absent_at_announce":
        leaver = g1
        leave(leaver)
        move(g0, target, target_loc)
        if rng.random() < 0.5:
            distractor()
        announce(g0, target, target_loc)         # leaver is OUT -> missed it
        reenter(leaver)                          # deceptive: returns AFTER, never re-told

    else:  # separate_private_tells
        # Target moves with two members absent; then each is told privately, separately.
        leave(g1)
        leave(g2)
        move(g0, target, target_loc)             # only g0 witnesses
        reenter(g1)
        tell(g0, g1, target, target_loc)         # g1 told privately
        leave(g1)
        reenter(g2)
        tell(g0, g2, target, target_loc)         # g2 told privately, separately
        # all three now individually know; never one public announcement -> NOT CK

    if rng.random() < 0.5:
        distractor()

    a, b, c = group
    question = (f"Is it common knowledge among {a}, {b} and {c} "
                f"that the {target} is in the {target_loc}?")
    answer = "yes" if variant in _YES else "no"
    qid = f"ckv2-{seed:06d}-{variant}"
    return {
        "sample_id": qid,
        "story": "\n".join(lines),
        "question": question,
        "answer": {"correct_answers": [answer], "wrong_answers": ["no" if answer == "yes" else "yes"]},
        "meta": {"public": answer == "yes", "variant": variant, "group": group,
                 "object": target, "location": target_loc, "ability": "common_knowledge",
                 "lang": "en", "id": qid},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=240, help="Total items (split evenly across 4 variants)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    per = args.n // len(VARIANTS)
    items = []
    for vi, variant in enumerate(VARIANTS):
        for i in range(per):
            items.append(generate_item_v2(seed=args.seed + vi * 10000 + i, variant=variant))
    _rnd.Random(args.seed).shuffle(items)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    n_yes = sum(1 for it in items if it["answer"]["correct_answers"][0] == "yes")
    print(f"wrote {len(items)} records (yes={n_yes}, no={len(items)-n_yes}) to {args.out}")
    by = {}
    for it in items:
        by[it["meta"]["variant"]] = by.get(it["meta"]["variant"], 0) + 1
    print("by variant:", by)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
