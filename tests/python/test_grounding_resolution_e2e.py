"""Phase 2 Task 2.3: cognizer-name + theme grounding round-trip (write→query symmetry).

The stub LLM returns an episodic JSON array whose actor name DRIFTS across surface
forms ("Xiao Hong" / "XiaoHong") and whose theme is PLURAL ("the cabbages" /
"cabbages"). The write path resolves every cognizer surface to one canonical
first-seen name (CognizerHub) and normalizes the theme before canonicalize, so a
query issued with a DIFFERENT surface of the same name ("XiaoHong") + the SINGULAR
theme ("cabbage") still grounds — exercising both Phase-1 theme normalization and
Phase-2 cognizer resolution end to end.

Conventions mirror test_perception_e2e.py: `mem._rt.adapter`, `mem._core.tenant`,
and the C++ engine class `_core.KnowledgeFrontier` (not the schema dataclass).
"""
import json

import starling
from starling import _core
from starling.tom import what_does_X_think

# Drifted actor name across events + a plural theme. Xiao Hong puts the cabbages in
# the basket and LEAVES; Li Lei then moves them to the box. Xiao Hong's last-known
# (pre-departure) location for the cabbages is therefore a STALE "basket".
_CANNED = json.dumps([
    {"actor": "Xiao Hong", "action": "put", "theme": "the cabbages", "location": "basket",
     "participants": ["Xiao Hong", "Li Lei"], "time": None},
    {"actor": "Xiao Hong", "action": "leave", "theme": "room", "location": None,
     "participants": ["Xiao Hong"], "time": None},
    {"actor": "Li Lei", "action": "move", "theme": "cabbages", "location": "box",
     "participants": ["Li Lei"], "time": None},
])


def test_drifted_name_and_plural_theme_ground(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember("Xiao Hong puts the cabbages in the basket and leaves. "
                 "Li Lei moves them to the box.")

    adapter = mem._rt.adapter
    tenant = mem._core.tenant
    frontier = _core.KnowledgeFrontier(adapter)

    # Query with a DRIFTED surface ("XiaoHong" — written as "Xiao Hong") + the
    # SINGULAR theme ("cabbage" — written plural). Both must resolve to the stored
    # canonical surfaces and ground to the stale basket belief.
    b = what_does_X_think(adapter, frontier, x="XiaoHong", theme="cabbage",
                          tenant_id=tenant)
    assert b.has_belief, "drifted-name + plural-theme query should still ground"
    assert b.state_value == "basket", f"Xiao Hong left before the move → stale basket: {b.state_value!r}"
    assert b.is_stale, "the cabbages really moved to the box → basket belief is stale"

    mem.close()
