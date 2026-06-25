"""appraise_emotion — binding smoke + stub-LLM end-to-end round-trip.

Smoke: EmotionAppraisal POD fields present + appraise_emotion callable from
both _core and the thin Python wrapper.

Round-trip: "Xiao Ming wants a computer; on his birthday he receives a bicycle."
With attribute_first_order_mental_to_holder=True the belief pass re-attributes
the desire to holder_id=Xiao Ming. The episodic pass emits an OCCURRED event
(subject_id=Xiao Ming, object=bicycle). appraise_emotion finds the desire
(computer) incongruent with the outcome (bicycle); actor==subject (Xiao Ming
himself received the wrong gift) -> agency=circumstance -> emotion=disappointment.

Mixed canned JSON strategy: the stub returns one JSON array for every LLM call.
The belief extractor picks up items with subject/predicate/object; the episodic
extractor picks up items with actor/action/theme; each ignores items missing its
required fields. Two objects in the same array therefore drive both passes.
"""
import json

import pytest

import starling
from starling.extractor.config import ExtractionConfig
from starling.tom.primitives import appraise_emotion

# Mixed JSON: object[0] feeds the belief pass (desire), object[1] feeds the
# episodic pass (OCCURRED outcome). Each pass silently skips the other object.
_CANNED = json.dumps([
    # Belief pass: Xiao Ming desires computer.
    # holder="narrator" (LLM always names the narrator); with flag ON the
    # extractor re-attributes to subject_id="Xiao Ming" -> holder_id=Xiao Ming.
    {
        "holder": "narrator",
        "holder_perspective": "INFERRED",
        "subject": "Xiao Ming",
        "predicate": "desires",
        "object": "computer",
        "modality": "DESIRES",
        "polarity": "POS",
        "nesting_depth": 0,
    },
    # Episodic pass: Xiao Ming receives bicycle.
    # actor/action/theme consumed by EpisodicExtractor -> OCCURRED statement with
    # subject_id="Xiao Ming", object_value="bicycle", modality="occurred".
    # holder_id is set to agent_self ("narrator") by the episodic extractor;
    # appraise_emotion matches via subject_id==xs.
    {
        "actor": "Xiao Ming",
        "action": "receive",
        "theme": "bicycle",
        "participants": ["Xiao Ming"],
        "time": None,
    },
])


# ─── smoke ────────────────────────────────────────────────────────────────────

def test_appraise_bound():
    from starling import _core
    assert hasattr(_core, "appraise_emotion")
    c = _core.EmotionAppraisal
    for f in ("cognizer", "emotion", "goal_congruence", "agency", "desire", "outcome_value"):
        assert hasattr(c, f)
    from starling.tom.primitives import appraise_emotion  # noqa: F401


# ─── round-trip ───────────────────────────────────────────────────────────────

def test_roundtrip_disappointment(tmp_path):
    """Full pipeline: narrated desire (computer) + OCCURRED outcome (bicycle)
    -> appraisal-theory produces disappointment (incongruent, circumstance)."""
    cfg = ExtractionConfig(attribute_first_order_mental_to_holder=True)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_CANNED),
        extraction=cfg,
    )
    try:
        mem.remember(
            "Xiao Ming wants a computer; on his birthday he receives a bicycle."
        )
        mem.tick()

        aps = appraise_emotion(
            mem._rt.adapter,
            x="Xiao Ming",
            tenant_id=mem._core.tenant,
        )
        emotions = {a.emotion for a in aps}
        assert "disappointment" in emotions, (
            f"expected 'disappointment'; got "
            f"{[(a.emotion, a.goal_congruence, a.agency) for a in aps]}"
        )
    finally:
        mem.close()
