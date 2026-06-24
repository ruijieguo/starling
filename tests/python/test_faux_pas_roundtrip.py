"""detect_faux_pas / FauxPasCandidate (SP-B) — binding smoke + end-to-end
round-trip (viability gate).

The ctest tests/cpp/test_faux_pas.cpp proves the OPERATOR LOGIC with a
hand-seeded KnowledgeFrontier. These tests prove the operator fires through a
REAL remember() → A (EpisodicExtractor: OCCURRED events + episodic_events) → B
(PerceptionReconstructor: per-cognizer perception_state + KnowledgeFrontier
presence_log, anchored on each OCCURRED statement's evidence engram_ref) path —
i.e. that a narrated story populates the frontier so does_X_know() yields the
per-character ignorance asymmetry the operator keys on.

Story: Alice, Bob and Carol are together; Bob leaves; then Alice moves the ball
to the box (only Alice and Carol present). Expected readout for that move-fact:
  does_X_know(Alice/Carol) = NotKnown   (their presence_log holds the move's engram)
  does_X_know(Bob)         = Unknowable (Bob, absent, never saw the move's engram)
→ detect_faux_pas flags Bob ignorant, who_knows = {Alice, Carol}.

CRUX learned while writing this (the round-trip is real but has two narration
preconditions, both honoured below — neither is an operator bug):

  1. ENGRAM GRANULARITY. PerceptionReconstructor anchors a witness's frontier
     presence on the OCCURRED statement's engram_ref, and ALL events extracted
     from ONE remember() passage share ONE engram_ref (the passage's engram).
     So if the fact-establishing event and an event the absent party DID witness
     live in the same passage, the absent party's presence_log holds that shared
     engram and does_X_know returns NotKnown for everyone (→ zero candidates).
     The post-departure fact must therefore be narrated in a SEPARATE remember()
     call so it gets its own engram. (Single-passage variant: see the xfail
     test below, which documents the limitation in-suite.)

  2. TIMELINE ORDERING. The reconstructor walks events on a global
     (observed_at, seq) order, and seq is per-passage. Two remember() calls with
     the default `now` collide on observed_at, and the second passage's seq=1
     then sorts BEFORE the first passage's seq=2 (Bob's leave) — so the move is
     processed while Bob is still "present" and Bob wrongly witnesses it. Passing
     distinct `now=` timestamps puts leave-before-move on the timeline, which is
     also the natural narration order.
"""
import json

import pytest

import starling
from starling import _core
from starling.tom.primitives import detect_faux_pas

# Episodic-event JSON the stub LLM returns (schema mirrors
# tests/python/test_perception_e2e.py — actor/action/theme/location/participants).
# The belief/general-fact extraction passes get the same JSON and graceful-empty;
# only the episodic pass consumes it (→ OCCURRED events that drive perception).
_TOGETHER = json.dumps([
    {"actor": "Alice", "action": "put", "theme": "ball", "location": "table",
     "participants": ["Alice", "Bob", "Carol"], "time": None},
    {"actor": "Bob", "action": "leave", "theme": "room", "location": None,
     "participants": ["Bob"], "time": None},
])
_AFTER = json.dumps([
    {"actor": "Alice", "action": "move", "theme": "ball", "location": "box",
     "participants": ["Alice", "Carol"], "time": None},
])


def test_faux_pas_bound():
    from starling import _core
    assert hasattr(_core, "detect_faux_pas")
    c = _core.FauxPasCandidate
    for f in ("ignorant", "unknown_fact", "who_knows"):
        assert hasattr(c, f)
    from starling.tom.primitives import detect_faux_pas  # noqa: F401


def test_roundtrip_flags_absent_party(tmp_path):
    """End-to-end: a real remember() populates the per-character frontier so the
    operator fires — Bob (who left) is flagged ignorant of the move only Alice
    and Carol witnessed. Proves SP-B ships as a working production operator."""
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_TOGETHER))
    try:
        # Passage 1 (its own engram): the three are together; Bob then leaves.
        mem.remember("Alice, Bob and Carol are together; Alice puts the ball on "
                     "the table; Bob leaves the room.",
                     now="2026-06-20T10:00:00Z")
        # Passage 2 (a SEPARATE engram, later timestamp): Alice moves the ball
        # with only Carol present. Distinct engram + leave-before-move ordering
        # are what make the frontier discriminate Bob from Alice/Carol.
        mem._core.llm = starling.make_stub_llm(default_response=_AFTER)
        mem.remember("Alice then moves the ball to the box.",
                     now="2026-06-20T11:00:00Z")
        mem.tick()  # consolidate volatile rows for the stable-state queries

        adapter = mem._rt.adapter
        tenant = mem._core.tenant
        frontier = _core.KnowledgeFrontier(adapter)

        cands = detect_faux_pas(adapter, frontier, tenant_id=tenant)
        igns = {c.ignorant for c in cands}
        assert "Bob" in igns, (
            "candidates="
            f"{[(c.ignorant, c.unknown_fact.predicate, c.unknown_fact.object_value) for c in cands]}")

        # The flagged candidate is about a fact Bob missed, and the co-present
        # witnesses (Alice, Carol) are credited as knowers.
        bob_cands = [c for c in cands if c.ignorant == "Bob"]
        assert any(set(c.who_knows) & {"Alice", "Carol"} for c in bob_cands), (
            f"who_knows={[list(c.who_knows) for c in bob_cands]}")
        assert "Alice" not in igns and "Carol" not in igns, (
            "co-present witnesses must NOT be flagged ignorant of what they saw; "
            f"ignorant={sorted(igns)}")
    finally:
        mem.close()


_ONE_PASSAGE = json.dumps([
    {"actor": "Alice", "action": "put", "theme": "ball", "location": "table",
     "participants": ["Alice", "Bob", "Carol"], "time": None},
    {"actor": "Bob", "action": "leave", "theme": "room", "location": None,
     "participants": ["Bob"], "time": None},
    {"actor": "Alice", "action": "move", "theme": "ball", "location": "box",
     "participants": ["Alice", "Carol"], "time": None},
])


@pytest.mark.xfail(
    reason="Single-passage narration limitation (not an operator bug): all events "
           "of one remember() share ONE engram_ref, so the absent party's frontier "
           "presence_log holds the same engram as the fact event and does_X_know "
           "returns NotKnown for everyone → no candidates. perception_state DOES "
           "exclude Bob from the move row, but the frontier evidence-visibility "
           "signal is per-passage, not per-event. Documented so the boundary is "
           "visible in-suite; the supported recipe is the two-remember test above.",
    strict=True)
def test_single_passage_does_not_discriminate(tmp_path):
    """One remember() with the whole story: the per-event perception asymmetry is
    captured in perception_state, but the per-passage engram collapses the
    frontier visibility signal, so no faux-pas candidate fires. (xfail: the
    operator needs per-event engram granularity, which remember() does not yet
    provide within a single passage.)"""
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_ONE_PASSAGE))
    try:
        mem.remember("Alice, Bob and Carol are together. Alice puts the ball on "
                     "the table. Bob leaves the room. Alice then moves the ball "
                     "to the box.")
        mem.tick()
        adapter = mem._rt.adapter
        tenant = mem._core.tenant
        frontier = _core.KnowledgeFrontier(adapter)
        cands = detect_faux_pas(adapter, frontier, tenant_id=tenant)
        assert "Bob" in {c.ignorant for c in cands}
    finally:
        mem.close()
