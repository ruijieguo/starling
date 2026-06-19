"""sub-project B Task 5.2 — deterministic self-test for the perception ToMBench harness.

Proves the ToMBench-subset harness (scripts/eval_perception_starling.py) is wired
correctly WITHOUT calling any real LLM: it feeds hand-built fixture items through
the FULL pipeline — parse the question -> remember(narrative) with a STUB LLM ->
A (EpisodicExtractor writes OCCURRED events) -> B (PerceptionReconstructor rebuilds
perception_state, via the wired remember) -> what_does_X_think(asked, theme) ->
map the perceived location to a multiple-choice option -> score vs the gold option
— and asserts the harness scores them correctly.

Covers both readouts B must get right:
  * a FALSE-BELIEF fixture (the asked cognizer LEFT before the move -> stale
    original location is the gold), and
  * a PERCEPTION/knowledge fixture (the asked cognizer STAYED and witnessed the
    move -> fresh new location is the gold).

The harness lives in scripts/, so it is imported by path here.
"""
import importlib.util
from pathlib import Path

_HARNESS_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "eval_perception_starling.py"
)


def _load_harness():
    spec = importlib.util.spec_from_file_location(
        "eval_perception_starling", _HARNESS_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_fixture_self_test_scores_all_correct():
    """The full harness pipeline scores every hand-built fixture correctly with a
    stub LLM — proving the parse/remember/A/B/what_does_X_think/score wiring works
    with zero network.

    Phase 3 (M5): run_fixture_self_test now returns (correct, total, grounded,
    details).  Both well-formed fixtures must ground (grounding-rate == 1.0).
    """
    harness = _load_harness()
    correct, total, grounded, details = harness.run_fixture_self_test()
    assert total >= 2, f"expected >=2 fixtures, got {total}: {details}"
    assert correct == total, (
        f"harness must score every fixture correctly: {correct}/{total}\n"
        + "\n".join(details))
    assert grounded == total, (
        f"all fixtures must ground (grounding-rate 1.0): {grounded}/{total}\n"
        + "\n".join(details))


def test_parse_probe_extracts_asked_and_theme_from_corpus_shape():
    """parse_probe pulls (asked cognizer, theme) out of a real ToMBench-shaped
    'where does X look for Y after ... returns' question, stripping the trailing
    temporal clause from the theme."""
    harness = _load_harness()
    record = {
        "question_id": "tb-x",
        "context": ("Xiaogang and Xiaoming are wandering in the bedroom, they find "
                    "cabbage in the handbag, Xiaoming leaves the bedroom, Xiaogang "
                    "moves the cabbage to the backpack."),
        "question": ("Where does Li Lei look for the sweatshirt after Han Meimei "
                     "returns to the living room?"),
        "options": ["Cabinet", "Box", "Handbag", "Tote bag"],
        "answer": 2,
        "ability": harness.LOCATION_FALSE_BELIEF_ABILITY,
    }
    probe = harness.parse_probe(record)
    assert probe is not None
    assert probe.asked == "Li Lei"
    assert probe.theme == "sweatshirt"          # trailing "after ..." clause stripped
    assert probe.gold == "Handbag"


def test_parse_probe_rejects_non_location_abilities():
    """A non-location-false-belief ability (e.g. a numeric Knowledge probe) is not
    a scorable perception probe — parse_probe returns None."""
    harness = _load_harness()
    record = {
        "question_id": "tb-k",
        "context": "Laura receives 5 letters...",
        "question": "Before Laura calls you, how many of these 5 letters contain checks?",
        "options": ["0", "1", "2", "4"],
        "answer": 3,
        "ability": "Knowledge: Information-knowledge links",
    }
    assert harness.parse_probe(record) is None


def test_map_to_option_normalized_and_containment():
    """Perceived location maps to the right option by normalized exact match and
    by containment (case / spacing differences)."""
    harness = _load_harness()
    opts = ["Backpack", "Handbag", "Storage locker", "Briefcase"]
    assert harness.map_to_option("backpack", opts) == "Backpack"
    assert harness.map_to_option("storage locker", opts) == "Storage locker"
    assert harness.map_to_option("nonexistent place", opts) is None
