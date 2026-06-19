"""End-to-end proof that ExtractionConfig(extra_core_predicates=...) reaches the
REAL belief write path and changes a STORED statement's review status.

This drives the actual `mem.remember(...)` pipeline (no spies/mocks) with a stub
LLM that emits a belief statement whose predicate is a custom domain verb
("annotates" — NOT in the controlled core set of
include/starling/extractor/predicate_registry.hpp). The validator
(src/extractor/statement_validator.cpp) downgrades out-of-set non-OCCURRED
predicates to review_requested UNLESS the predicate is named in the policy's
extra_core_predicates. So:

  - with ExtractionConfig(extra_core_predicates=("annotates",)) the stored row
    keeps review_status='approved';
  - with the default ExtractionConfig the SAME row is 'review_requested'.

Belief-JSON shape copied from tests/python/test_tom2_e2e.py's CANNED constant
(holder/holder_perspective/subject/predicate/object/modality/polarity/
nesting_depth, the EXTRACTION_PROMPT output schema). holder="self" is advisory —
the extractor overrides holder_id with the run agent (json_parser.cpp). The
review-status read (sqlite3.connect + SELECT review_status FROM statements) also
mirrors test_tom2_e2e.py.

confidence=0.9 keeps the row above both floors: the 0.30 drop floor (so it
isn't dropped) and the 0.50 weak-inference floor (so FIRST_PERSON/user_input
doesn't get tagged inferred_unreviewed instead of approved). modality=BELIEVES
(not OCCURRED) so the predicate gate applies.
"""
import sqlite3

import starling

# Belief shape the stub LLM returns (EXTRACTION_PROMPT JSON array). predicate is a
# custom domain verb outside the core set; confidence=0.9 clears both validator
# floors so the only review-status lever left is the predicate policy.
CUSTOM_PREDICATE_BELIEF = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"annotates","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","confidence":0.9,'
    '"nesting_depth":0}]'
)

REMEMBER_TEXT = "Bob annotates the auth module."


def _read_annotates_review_status(db_path: str):
    """Return the review_status of the stored 'annotates' belief, or None if the
    custom-predicate statement was never persisted."""
    ro = sqlite3.connect(db_path)
    try:
        row = ro.execute(
            "SELECT review_status FROM statements WHERE predicate='annotates'"
        ).fetchone()
    finally:
        ro.close()
    return row[0] if row else None


def test_extra_core_predicate_approved_under_policy(tmp_path):
    """With extra_core_predicates=("annotates",) the custom-predicate belief
    lands approved (the policy suppresses the review_requested downgrade)."""
    db = str(tmp_path / "approved.db")
    llm = starling.make_stub_llm(default_response=CUSTOM_PREDICATE_BELIEF)
    mem = starling.Memory.open(
        db, llm=llm,
        extraction=starling.ExtractionConfig(extra_core_predicates=("annotates",)))
    try:
        result = mem.remember(REMEMBER_TEXT)
        assert result.outcome in ("accepted", "idempotent"), result.outcome
        status = _read_annotates_review_status(db)
        # The custom-predicate statement MUST have been persisted...
        assert status is not None, "custom-predicate belief was not stored"
        # ...and NOT flagged for review, because the policy approves "annotates".
        assert status != "review_requested", status
        assert status == "approved", status
    finally:
        mem.close()


def test_custom_predicate_flagged_without_policy(tmp_path):
    """Same stub + text but DEFAULT extraction config: the out-of-set predicate
    is downgraded to review_requested (the baseline the policy overrides)."""
    db = str(tmp_path / "flagged.db")
    llm = starling.make_stub_llm(default_response=CUSTOM_PREDICATE_BELIEF)
    mem = starling.Memory.open(db, llm=llm)
    try:
        result = mem.remember(REMEMBER_TEXT)
        assert result.outcome in ("accepted", "idempotent"), result.outcome
        status = _read_annotates_review_status(db)
        assert status is not None, "custom-predicate belief was not stored"
        assert status == "review_requested", status
    finally:
        mem.close()
