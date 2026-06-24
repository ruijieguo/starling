"""detect_faux_pas / FauxPasCandidate (SP-B) — binding smoke + end-to-end
round-trip (viability gate).

The ctest tests/cpp/test_faux_pas.cpp proves the OPERATOR LOGIC with hand-seeded
perception_state rows. These tests prove the operator fires through a REAL
remember() → A (EpisodicExtractor: OCCURRED events + episodic_events) → B
(PerceptionReconstructor: per-cognizer perception_state) path — i.e. that a
narrated story populates perception_state so what_does_X_think() yields the
per-character stale-view asymmetry the operator keys on.

The operator is per-EVENT now (it reads what_does_X_think.is_stale over
perception_state), so a SINGLE natural remember() of the whole story is enough:
within one passage the reconstructor already excludes the absent party from the
post-departure state row. (This is the bug the re-base fixed — the previous
does_X_know/frontier mechanism collapsed the visibility signal to per-passage
engram granularity and emitted zero candidates on a single remember.)

Story: Alice, Bob and Carol are together; Alice puts the ball on the table; Bob
leaves; Alice moves the ball to the box (only Alice and Carol present). Readout:
  what_does_X_think(Alice/Carol, ball) = box, NOT stale  (they saw the move)
  what_does_X_think(Bob,        ball) = table, STALE     (Bob left before it)
→ detect_faux_pas flags Bob ignorant, who_knows = {Alice, Carol}.
"""
import json

import starling
from starling import _core
from starling.tom.primitives import detect_faux_pas

# Episodic-event JSON the stub LLM returns (schema mirrors
# tests/python/test_perception_e2e.py — actor/action/theme/location/participants).
# The belief/general-fact extraction passes get the same JSON and graceful-empty;
# only the episodic pass consumes it (→ OCCURRED events that drive perception).
# One passage carries the whole arc: put (all present) → leave → move (Bob absent).
_STORY = json.dumps([
    {"actor": "Alice", "action": "put", "theme": "ball", "location": "table",
     "participants": ["Alice", "Bob", "Carol"], "time": None},
    {"actor": "Bob", "action": "leave", "theme": "room", "location": None,
     "participants": ["Bob"], "time": None},
    {"actor": "Alice", "action": "move", "theme": "ball", "location": "box",
     "participants": ["Alice", "Carol"], "time": None},
])


def test_faux_pas_bound():
    from starling import _core
    assert hasattr(_core, "detect_faux_pas")
    c = _core.FauxPasCandidate
    for f in ("ignorant", "theme", "state_dim", "stale_value", "actual_value", "who_knows"):
        assert hasattr(c, f)
    from starling.tom.primitives import detect_faux_pas  # noqa: F401


def test_roundtrip_flags_absent_party(tmp_path):
    """End-to-end: a single real remember() populates per-character perception_state
    so the operator fires — Bob (who left before the move) is flagged ignorant of
    the ball's current location, which co-present Alice and Carol perceived. Proves
    SP-B ships as a working production operator on a natural single-remember story."""
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_STORY))
    try:
        # ONE natural passage: the three are together, Bob leaves, then the ball
        # moves with only Alice and Carol present. Per-event perception_state
        # excludes Bob from the post-departure "box" row, so he stays on "table".
        mem.remember("Alice, Bob and Carol are together; Alice puts the ball on the "
                     "table; Bob leaves the room; Alice then moves the ball to the box.")
        mem.tick()  # consolidate volatile rows for the stable-state queries

        adapter = mem._rt.adapter
        tenant = mem._core.tenant
        frontier = _core.KnowledgeFrontier(adapter)

        cands = detect_faux_pas(adapter, frontier, tenant_id=tenant)
        igns = {c.ignorant for c in cands}
        assert "Bob" in igns, (
            "candidates="
            f"{[(c.ignorant, c.theme, c.stale_value, c.actual_value) for c in cands]}")

        # The flagged candidate is about the theme Bob holds a stale view of, and the
        # co-present witnesses (Alice, Carol) are credited as knowers of the new state.
        bob_cands = [c for c in cands if c.ignorant == "Bob"]
        assert any(c.theme == "ball" and c.stale_value == "table"
                   and c.actual_value == "box" for c in bob_cands), (
            f"bob_cands={[(c.theme, c.stale_value, c.actual_value) for c in bob_cands]}")
        assert any(set(c.who_knows) & {"Alice", "Carol"} for c in bob_cands), (
            f"who_knows={[list(c.who_knows) for c in bob_cands]}")
        assert "Alice" not in igns and "Carol" not in igns, (
            "co-present witnesses must NOT be flagged ignorant of what they saw; "
            f"ignorant={sorted(igns)}")
    finally:
        mem.close()


def test_single_passage_discriminates(tmp_path):
    """The whole story in one remember() is now sufficient: per-event perception
    (what_does_X_think.is_stale) discriminates the absent party WITHIN a single
    passage. (Before the re-base this was an xfail — the does_X_know/frontier
    mechanism collapsed the visibility signal to per-passage engram granularity
    and emitted no candidate. The operator now reads perception_state directly.)"""
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_STORY))
    try:
        mem.remember("Alice, Bob and Carol are together. Alice puts the ball on "
                     "the table. Bob leaves the room. Alice then moves the ball "
                     "to the box.")
        mem.tick()
        adapter = mem._rt.adapter
        tenant = mem._core.tenant
        frontier = _core.KnowledgeFrontier(adapter)
        cands = detect_faux_pas(adapter, frontier, tenant_id=tenant)
        assert "Bob" in {c.ignorant for c in cands}, (
            "single-passage per-event perception must flag the absent party; "
            f"candidates={[(c.ignorant, c.theme, c.stale_value) for c in cands]}")
    finally:
        mem.close()
