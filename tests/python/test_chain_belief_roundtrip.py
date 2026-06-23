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
