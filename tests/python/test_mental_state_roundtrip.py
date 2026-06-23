def test_mental_state_bound_and_callable():
    from starling import _core
    assert hasattr(_core, "mental_state_of")
    ms_cls = _core.MentalState
    for f in ("beliefs", "knowledge", "desires", "intentions", "commitments", "preferences"):
        assert hasattr(ms_cls, f)
    from starling.tom.primitives import mental_state_of  # wrapper exists


import json
import starling
from starling.tom.primitives import mental_state_of

# Canned extraction output: four statements covering all the non-belief
# attitudes under test.  The stub LLM returns this JSON for any prompt.
# holder="Alice" in the JSON is the extraction-level holder; the writer
# stores these as holder_id=<agent> ("narrator") — so we query
# mental_state_of with x="narrator".
# modality is stored lowercase by the writer (DESIRES->desires, etc.).
# predicate=knows routes to knowledge bucket regardless of modality;
# predicate=prefers routes to preferences bucket regardless of modality;
# modality=intends routes to intentions; modality=believes->beliefs.
_CANNED = json.dumps([
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "ball",
     "predicate": "located_at", "object": "box", "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0},
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "keys",
     "predicate": "knows", "object": "drawer", "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0},
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "weekend",
     "predicate": "prefers", "object": "outdoors", "modality": "DESIRES", "polarity": "POS", "nesting_depth": 0},
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "report",
     "predicate": "responsible_for", "object": "report", "modality": "INTENDS", "polarity": "POS", "nesting_depth": 0},
])


def test_roundtrip_buckets_nonbelief_attitudes(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember("Alice: the ball is in the box; I know the keys are in the drawer; "
                 "I want to spend the weekend outdoors; I'm going to finish the report.")
    # tick() consolidates volatile rows so mental_state_of (which filters
    # consolidation_state IN ('consolidated','archived')) can find them.
    mem.tick()
    ms = mental_state_of(mem._rt.adapter, x="narrator", tenant_id=mem._core.tenant)
    assert len(ms.knowledge) >= 1, f"knowledge empty; buckets: {_dump(ms)}"      # predicate=knows
    assert len(ms.preferences) >= 1, f"preferences empty; buckets: {_dump(ms)}"  # predicate=prefers
    assert len(ms.intentions) >= 1, f"intentions empty; buckets: {_dump(ms)}"    # modality=INTENDS
    assert any(r.object_value == "box" for r in ms.beliefs), f"belief missing; {_dump(ms)}"


def _dump(ms):
    return {k: [(r.subject_id, r.predicate, r.object_value, r.modality) for r in getattr(ms, k)]
            for k in ("beliefs", "knowledge", "desires", "intentions", "commitments", "preferences")}
