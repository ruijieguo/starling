"""Extraction-completeness machinery pin (sub-project: extraction completeness).

The leaver-find-gap fix is a PROMPT change (episodic_prompt.py learns to capture a
state-establishing INITIAL location: "they find the hat in the suitcase" ->
action=find, location=suitcase). This test pins the downstream MACHINERY: given the
episodic JSON the new prompt elicits for the leaver-find scene, the character who
LEAVES before the object is moved holds the stale initial-location belief, while the
mover holds the fresh one.

It is a regression pin (it passes against the current reconstructor — find-with-
location already routes to state_dim=location and the leaver is a default-present
witness via her own leave clause); whether the *real model* emits the find WITH a
location is what the prompt change steers and only the real-model grounding-recall
eval (scripts/eval_perception_starling.py, gated) measures.
"""
import json

import starling
from starling.tom import what_does_X_think

# The episodic JSON the new episodic_prompt is designed to elicit for the
# Xiao-Li / Youyou leaver-find scene: the `find` establishes the hat's INITIAL
# location (suitcase); Youyou leaves before Xiao Li moves it to the locker.
_CANNED = json.dumps([
    {"actor": "Xiao Li", "action": "find", "theme": "hat", "location": "suitcase",
     "participants": ["Xiao Li", "Youyou"], "time": None},
    {"actor": "Youyou", "action": "leave", "theme": "basement", "location": None,
     "participants": ["Youyou"], "time": None},
    {"actor": "Xiao Li", "action": "move", "theme": "hat", "location": "storage locker",
     "participants": ["Xiao Li"], "time": None},
])


def test_leaver_find_initial_location_grounds(tmp_path):
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember(
        "Xiao Li and Youyou find a hat in the suitcase. Youyou leaves. "
        "Xiao Li moves the hat to the storage locker.")
    frontier = starling._core.KnowledgeFrontier(mem._rt.adapter)
    tenant = mem._core.tenant

    # Leaver: perceived the find (initial location), absent for the move -> stale "suitcase".
    youyou = what_does_X_think(mem._rt.adapter, frontier, x="Youyou", theme="hat",
                               tenant_id=tenant)
    assert youyou.has_belief
    assert youyou.state_value == "suitcase"
    assert youyou.is_stale

    # Mover: present throughout -> fresh "storage locker".
    xiaoli = what_does_X_think(mem._rt.adapter, frontier, x="Xiao Li", theme="hat",
                               tenant_id=tenant)
    assert xiaoli.has_belief
    assert xiaoli.state_value == "storage locker"
    assert not xiaoli.is_stale
