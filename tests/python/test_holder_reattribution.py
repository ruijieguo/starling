"""Flag-gated first-order desire holder re-attribution (additive).

A validation showed the LLM's `holder` field is always the narrator
(fragmented narrator/叙述者/Narrator), while `subject` reliably names the
desirer for the desire family. With
ExtractionConfig.attribute_first_order_mental_to_holder=True, a FIRST-ORDER
DESIRE statement is instead attributed to its cognizer-resolved subject, so a
narrated 3rd-person desire ("Xiao Hong wants the amusement park") lands under
holder_id="Xiao Hong" and mental_state_of("Xiao Hong") finds it.
BELIEVES/KNOWS remain agent-attributed (subject is the topic, not the bearer).

Mirrors tests/python/test_mental_state_roundtrip.py's stub-LLM + Memory.open
style. The stub's canned JSON carries `subject` = the character. The stub
returns this for ANY prompt, so all three remember() passes (belief / episodic /
general-fact) see it; the belief pass is the one under test.
"""
import json

import starling
from starling.extractor.config import ExtractionConfig
from starling.tom.primitives import mental_state_of

# A narrated first-order desire: subject names the CHARACTER (Xiao Hong),
# holder is "narrator" (as the LLM always emits in practice), modality=DESIRES,
# nesting_depth=0. predicate=desires is non-core (no review downgrade).
_DESIRE_JSON = json.dumps([
    {"holder": "narrator", "holder_perspective": "INFERRED", "subject": "Xiao Hong",
     "predicate": "desires", "object": "amusement park", "modality": "DESIRES",
     "polarity": "POS", "nesting_depth": 0},
])

_STORY = "Xiao Hong wants to go to the amusement park."


def _desire_objs(ms):
    return [r.object_value for r in ms.desires]


def test_flag_on_attributes_narrated_desire_to_character(tmp_path):
    mem = starling.Memory.open(
        str(tmp_path / "on.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_DESIRE_JSON),
        extraction=ExtractionConfig(attribute_first_order_mental_to_holder=True))
    mem.remember(_STORY)
    # tick() consolidates volatile rows so mental_state_of (which filters
    # consolidation_state IN ('consolidated','archived')) can find them.
    mem.tick()

    ms_char = mental_state_of(mem._rt.adapter, x="Xiao Hong", tenant_id=mem._core.tenant)
    assert "amusement park" in _desire_objs(ms_char), (
        f"desire not attributed to character (subject); got {_desire_objs(ms_char)}")

    ms_narr = mental_state_of(mem._rt.adapter, x="narrator", tenant_id=mem._core.tenant)
    assert "amusement park" not in _desire_objs(ms_narr), (
        f"desire leaked onto the agent holder; got {_desire_objs(ms_narr)}")


def test_flag_off_keeps_agent_holder(tmp_path):
    # Default-OFF: identical story, no extraction override -> the attitude stays
    # with the agent ("narrator"), exactly as before (additive guarantee).
    mem = starling.Memory.open(
        str(tmp_path / "off.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_DESIRE_JSON))
    mem.remember(_STORY)
    mem.tick()

    ms_narr = mental_state_of(mem._rt.adapter, x="narrator", tenant_id=mem._core.tenant)
    assert "amusement park" in _desire_objs(ms_narr), (
        f"flag-OFF must keep agent holder; got {_desire_objs(ms_narr)}")

    ms_char = mental_state_of(mem._rt.adapter, x="Xiao Hong", tenant_id=mem._core.tenant)
    assert "amusement park" not in _desire_objs(ms_char), (
        f"flag-OFF must NOT re-attribute; got {_desire_objs(ms_char)}")


def test_flag_default_is_off():
    assert ExtractionConfig().attribute_first_order_mental_to_holder is False
