"""Round-trip: a HiToM-style story whose scene-initial location is a bare stative (no
person named). The leaver (saw only the initial location) must keep the initial location
-- i.e. perception_state gets the initial location for ALL present agents, established
from a participant-less location event via the reconstructor's present-cast."""
import json

import starling
from starling.tom import what_does_X_think

# The episodic JSON the new prompt is designed to elicit for a BARE scene-initial
# stative "The watermelon is in the green_bucket" (NO person named): a `find` with
# participants=[] (no one is NAMED in the fact) and a present actor. The reconstructor's
# present-cast (present defaults to the whole cast) witnesses it, so every present agent
# perceives the initial location. Cast here = {Noah, Emma} (Noah's leave + Emma's move
# register them); both are present at the find (seq 1) -> both perceive green_bucket.
# This is the bare-stative sibling of test_completeness_e2e.py (which lists explicit
# finders); here NO one is named, so participants=[] and present-cast does the witnessing.
_CANNED = json.dumps([
    {"actor": "Noah", "action": "find", "theme": "watermelon", "location": "green_bucket",
     "participants": [], "time": None},
    {"actor": "Noah", "action": "leave", "theme": "hall", "location": None,
     "participants": ["Noah"], "time": None},
    {"actor": "Emma", "action": "move", "theme": "watermelon", "location": "blue_chest",
     "participants": ["Emma"], "time": None},
])


def test_bare_stative_perceived_by_all_present_then_leaver_keeps_it(tmp_path):
    # make_stub_llm wraps the C++ FakeLLMAdapter (Memory.open requires a real adapter, not
    # a Python object). default_response is returned for EVERY pass; only the episodic pass
    # turns it into events -> perception_state. Pattern: tests/python/test_completeness_e2e.py:34-56.
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember(
        "Noah and Emma entered the hall. The watermelon is in the green_bucket. "
        "Noah exited the hall. Emma moved the watermelon to the blue_chest.")
    frontier = starling._core.KnowledgeFrontier(mem._rt.adapter)
    tenant = mem._core.tenant
    # Leaver Noah: saw only the bare-stative initial location, absent for the move.
    noah = what_does_X_think(mem._rt.adapter, frontier, x="Noah", theme="watermelon", tenant_id=tenant)
    assert noah.has_belief, "the bare stative must give the leaver an initial-location belief"
    assert noah.state_value == "green_bucket"
    # Mover Emma: present through the move -> fresh blue_chest.
    emma = what_does_X_think(mem._rt.adapter, frontier, x="Emma", theme="watermelon", tenant_id=tenant)
    assert emma.has_belief
    assert emma.state_value == "blue_chest"


def test_chain_query_is_bound_and_callable():
    from starling import _core
    assert hasattr(_core, "what_does_X_think_chain")
    from starling.tom.primitives import what_does_X_think_chain  # wrapper exists


_CANNED_O3 = json.dumps([
    {"actor": "Aiden", "action": "enter", "theme": "hall", "location": None,
     "participants": ["Aiden", "Avery", "Carter"], "time": None},
    {"actor": "Aiden", "action": "find", "theme": "cabbage", "location": "blue_bathtub",
     "participants": [], "time": None},
    {"actor": "Carter", "action": "leave", "theme": "hall", "location": None,
     "participants": ["Carter"], "time": None},
    {"actor": "Avery", "action": "move", "theme": "cabbage", "location": "red_box",
     "participants": ["Avery"], "time": None},
])


def test_order3_chain_resolves_to_initial_for_early_leaver(tmp_path):
    from starling.tom.primitives import what_does_X_think_chain
    from datetime import datetime, timezone
    # The `enter` event seats the cast {Aiden, Avery, Carter}; all are present at the find ->
    # all perceive blue_bathtub. Carter leaves before Avery's move (so Carter still believes
    # blue_bathtub). Aiden is the outermost observer who never leaves/moves -- WITHOUT the
    # enter event he would be absent from the cast, get no perception, and the chain query
    # would return has_belief=false.
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_CANNED_O3))
    mem.remember("Aiden, Avery and Carter entered the hall. The cabbage is in the blue_bathtub. "
                 "Carter exited the hall. Avery moved the cabbage to the red_box.")
    frontier = starling._core.KnowledgeFrontier(mem._rt.adapter)
    # "Aiden think Avery think Carter think the cabbage is": Carter (deepest) left before the
    # move; all three co-saw the initial blue_bathtub -> blue_bathtub.
    sb = what_does_X_think_chain(
        mem._rt.adapter, frontier, chain=["Aiden", "Avery", "Carter"], theme="cabbage",
        tenant_id=mem._core.tenant, as_of=datetime(9999, 1, 1, tzinfo=timezone.utc))
    assert sb.has_belief
    assert sb.state_value == "blue_bathtub"
