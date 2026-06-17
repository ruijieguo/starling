"""sub-project A phase 6 Task 6.1 — recall surfaces OCCURRED events +
`latest_event_location` facade (offline, stub LLM, zero network).

Two guarantees, both proven without a real model:

1. OCCURRED events are ordinary `statements` rows, so the normal write→tick→
   recall path returns them — no recall/query surface filters by modality.
   We seed events via the dual-pass `remember()` (the episodic JSON the belief
   parser drops to empty), tick to embed, then assert a semantic recall over
   the narrative surfaces the OCCURRED rows.

2. `mem.latest_event_location("ball")` returns the highest-seq event's location
   — "box" after put(basket, seq1) then move(box, seq2) — the ground-truth
   current state for the A→B handoff.
"""
import starling

# Episodic JSON for the Sally/Anne narrative, in narrative order. Has NO
# subject/predicate/object keys, so the belief/conversation parser yields
# nothing — only the episodic pass reads it (→ 3 OCCURRED events).
EPISODIC_JSON = (
    '[\n'
    '  {"actor":"Sally","action":"put","theme":"ball","location":"basket","participants":["Sally"],"time":null},\n'
    '  {"actor":"Sally","action":"leave","theme":"room","location":null,"participants":["Sally"],"time":null},\n'
    '  {"actor":"Anne","action":"move","theme":"ball","location":"box","participants":["Anne"],"time":null}\n'
    ']'
)

NARRATIVE = (
    "Sally puts her ball in the basket and leaves the room. "
    "Anne moves the ball to the box."
)


def test_recall_returns_occurred_events(tmp_path):
    """OCCURRED events surface through the ordinary recall path (no modality
    filter drops them)."""
    llm = starling.make_stub_llm(default_response=EPISODIC_JSON)
    mem = starling.Memory.open(str(tmp_path / "recall.db"), agent="self", llm=llm)
    try:
        res = mem.remember(NARRATIVE, now="2026-06-16T10:00:00Z")
        assert len(res.statement_ids) >= 3  # 3 OCCURRED events written
        mem.tick(now="2026-06-16T10:01:00Z")  # embed pending statements

        hits = mem.recall("ball moved into the box", mode="semantic", k=10)
        assert isinstance(hits, list)
        assert len(hits) >= 1, "recall returned nothing for OCCURRED events"
        # The OCCURRED event rows are present among the hits (subject/predicate/
        # object identify them — recall does not exclude modality='occurred').
        triples = {(h["row"].subject_id, h["row"].predicate, h["row"].object_value)
                   for h in hits}
        assert ("Anne", "move", "ball") in triples or \
               ("Sally", "put", "ball") in triples, \
            f"no OCCURRED event among recall hits: {triples}"
        # Every hit that is an event carries modality OCCURRED (sanity: events
        # are not silently rewritten to a belief modality on the recall path).
        for h in hits:
            row = h["row"]
            if (row.subject_id, row.predicate, row.object_value) in {
                ("Sally", "put", "ball"), ("Sally", "leave", "room"),
                ("Anne", "move", "ball"),
            }:
                assert row.modality.lower() == "occurred"
    finally:
        mem.close()


def test_latest_event_location_tracks_highest_seq(tmp_path):
    """latest_event_location("ball") == "box" after put(basket,seq1) +
    move(box,seq2) — the highest-seq event's location wins."""
    llm = starling.make_stub_llm(default_response=EPISODIC_JSON)
    mem = starling.Memory.open(str(tmp_path / "latest.db"), agent="self", llm=llm)
    try:
        mem.remember(NARRATIVE, now="2026-06-16T10:00:00Z")
        # ball: put->basket(seq1), move->box(seq3) → highest seq location = box.
        assert mem.latest_event_location("ball") == "box"
        # A theme with no OCCURRED event → "".
        assert mem.latest_event_location("spaceship") == ""
    finally:
        mem.close()
