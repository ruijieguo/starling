"""End-to-end proof that a declarative passage becomes a recallable general fact.

Drives the REAL `mem.remember(...)` pipeline (no spies/mocks) with a stub LLM that
emits a single declarative-fact claim (the SAME EXTRACTION_PROMPT JSON-array schema
the belief Extractor parses). The third "general fact" pass in
`MemoryCore.remember` reuses the belief Extractor with a `{self}`-filled general
prompt; `reports_to` is a core predicate
(include/starling/extractor/predicate_registry.hpp) so the validator keeps the
stored row approved (NOT downgraded to review_requested).

The embedded facade uses a deterministic STUB embedder, so *semantic* recall is not
reliable for asserting retrieval. Instead — exactly like the configurability
milestone's e2e (tests/python/test_extraction_config_e2e.py) — assert the stored
row directly via sqlite3: the fact MUST exist, MUST NOT be review_requested (so it
sits in the default recall scope), and MUST be held by the self agent (so it is
eligible under the default recall(holder=self)).

Belief-JSON shape (holder/holder_perspective/subject/predicate/object/modality/
polarity/nesting_depth/confidence) matches the EXTRACTION_PROMPT output schema.
confidence=0.9 clears both validator floors (0.30 drop, 0.50 weak-inference) so the
only thing that could change the review status is the predicate gate — and
reports_to is in-set, so it stays approved. holder="self" in the JSON is advisory;
the extractor overrides holder_id with the run agent (json_parser.cpp), which is
"self" here.
"""
import json
import sqlite3

import starling

_CANNED = json.dumps([
    {"holder": "self", "holder_perspective": "FIRST_PERSON", "subject": "Alice",
     "predicate": "reports_to", "object": "Bob", "modality": "BELIEVES",
     "polarity": "POS", "nesting_depth": 0, "confidence": 0.9},
])


def test_general_fact_stored_approved_self_held(tmp_path):
    db = str(tmp_path / "m.db")
    mem = starling.Memory.open(
        db, agent="self", llm=starling.make_stub_llm(default_response=_CANNED))
    try:
        mem.remember("Alice reports to Bob.")
    finally:
        mem.close()

    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT holder_id, review_status FROM statements "
            "WHERE predicate='reports_to'").fetchall()
    finally:
        con.close()

    assert rows, "general fact (reports_to) not stored"
    holder_id, review_status = rows[0]
    # general predicate is core -> approved, NOT review_requested -> in default
    # recall scope.
    assert review_status != "review_requested", review_status
    # holder is the self agent -> default recall(holder=self) eligibility.
    assert holder_id == "self", holder_id
