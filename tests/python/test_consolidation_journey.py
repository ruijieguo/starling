"""#38-C full-journey integration — the REAL remember() flow → run_replay(sleep)
→ NORM gist, end-to-end.

remember() consolidates each statement synchronously (the post-write online-replay
pump), so a fresh memory is 'consolidated', never lingering 'volatile'. The NORM
clustering therefore must seed from SETTLED (consolidated) beliefs — which is the
fix this test guards. The PRIOR version of this file seeded `volatile` rows
directly (a state the real flow never produces) and so "passed" while gists never
formed in production. This version drives the actual remember path; pre-fix it
forms 0 gists (sample_volatile is empty → no seeds), post-fix it forms the gist.

Deterministic FakeLLMAdapter for both extraction and consolidation; no API key.
"""
import json

from starling import _core
from starling.dashboard import queries
from starling.memory import Memory

NOW = "2026-06-27T12:00:00Z"


def _extraction(holder, subj, pred, obj):
    return [{"holder": holder, "holder_perspective": "FIRST_PERSON",
             "subject": subj, "predicate": pred, "object": obj,
             "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0}]


def test_real_remember_flow_forms_gist(tmp_path):
    db = str(tmp_path / "journey.db")
    extractor = _core.FakeLLMAdapter()
    mem = Memory.open(db, llm=extractor)
    cons = _core.FakeLLMAdapter()
    # Combined response: judge reads {confidence, summary}; verify reads {entailed}.
    cons.set_default_response(
        '{"confidence":0.8,"summary":"People value code review.","entailed":true}', True, "")
    mem._core.consolidation_llm = cons

    # 3 distinct holders, each subject = themselves (so no dedup), SAME
    # (predicate, object). Real remember() → each lands 'consolidated' (synchronous
    # online pump), NOT 'volatile'.
    for holder in ("alice", "bob", "carol"):
        extractor.set_default_response(
            json.dumps(_extraction(holder, holder, "values", "code review")), True, "")
        mem.remember(f"{holder} values code review", holder=holder, now=NOW)

    # The settled beliefs seed the NORM scan (the fix). Pre-fix: sample_volatile is
    # empty → 0 candidates → 0 gists (the production bug this test guards).
    stats = mem._core.run_replay("sleep", now=NOW)
    assert stats["gist_candidates"] >= 1, (
        f"no NORM candidate formed from consolidated seeds via the real flow: {stats}")

    del mem  # release the writer before the read connection
    out = queries.gists(db, "default")
    assert len(out["gists"]) >= 1, (
        f"no gist formed via the real remember journey; by_state={out['by_state']}")
    gist = out["gists"][0]
    assert gist["consolidation_state"] == "consolidated"   # verified + promoted to live
    assert gist["review_status"] == "approved"
    assert gist["consolidation_summary"] == "People value code review."
    assert len(gist["derived_from"]) >= 3                  # >= K distinct-holder members
