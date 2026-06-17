"""Self-tests for the Starling-in-the-loop second-order memory eval (track 2).

Unlike the track-1 harness tests (fixture mode, no Starling), these drive the
real second-order path via the harness helpers: question-template parsing
(derive_deterministic) and the seed -> belief_tracker_tick -> tick -> recall
round-trip (run_case). No network: deterministic mode only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eval_tom2_starling import (  # noqa: E402
    Case,
    _KNOWN_DRIFT_QIDS,
    derive_deterministic,
    run_case,
)


def _loc_record() -> dict:
    return {
        "question_id": "t-loc",
        "context": "A and B see a handbag and a backpack; they find a cabbage in "
        "the handbag; B leaves; A moves the cabbage to the backpack.",
        "question": "After B returns, where does A think B looks for the cabbage?",
        "options": ["handbag", "backpack", "box", "drawer"],
        "answer": 0,
        "ability": "second-order",
    }


def _content_record() -> dict:
    return {
        "question_id": "t-con",
        "context": "A and B see a box; B sees an apple in the box; B leaves; A "
        "swaps the apple for a pear.",
        "question": "After B opens the box, what does A think B expects to find "
        "in the box?",
        "options": ["apple", "pear", "grape", "plum"],
        "answer": 0,
        "ability": "second-order",
    }


def test_derive_location_template():
    case = derive_deterministic(_loc_record())
    assert case is not None
    assert case.predicate == "located_in"
    assert case.l1 == "handbag"  # gold option
    assert case.l2 != case.l1


def test_derive_content_template():
    case = derive_deterministic(_content_record())
    assert case is not None
    assert case.predicate == "contains"
    assert case.l1 == "apple"


def test_derive_returns_none_on_unparseable():
    rec = _loc_record()
    rec["question"] = "Who moved the cabbage and why did they do it?"
    assert derive_deterministic(rec) is None


def test_run_case_recalls_peer_stale_belief():
    """Integration: Starling produces + recalls B's stale belief (L1), not L2.

    Exercises belief_tracker_tick (programmatic depth-1 meta-belief) ->
    mem.tick() (consolidation) -> what_does_X_think_Y_believes recall.
    """
    case = Case(predicate="located_in", l1="handbag", l2="backpack",
                gold="handbag")
    correct, recalled = run_case(case)
    assert correct, f"recalled={recalled!r}"
    assert recalled.lower() == "handbag"


def test_run_case_wrong_when_recall_would_be_l2():
    """A case whose gold is NOT what the peer believes must score False.

    Seeds peer-belief L1='handbag' but marks gold='backpack' (the distractor);
    the recall returns the peer's 'handbag', which does not match gold, so the
    case is scored incorrect — guards against a scorer that always passes.
    """
    case = Case(predicate="located_in", l1="handbag", l2="backpack",
                gold="backpack")
    correct, recalled = run_case(case)
    assert not correct
    assert recalled.lower() == "handbag"


def test_known_drift_qids():
    assert _KNOWN_DRIFT_QIDS == {
        "tb-so-002", "tb-so-035", "tb-so-047", "tb-so-053"
    }
