"""sub-project A phase 5 Task 5.2 — dual-pass remember() end-to-end (offline).

A narrative ("Sally puts her ball in the basket and leaves the room. Anne moves
the ball to the box.") that the belief/conversation extractor extracts NOTHING
from must now produce OCCURRED event statements + episodic_events rows via the
SECOND (episodic) extraction pass that remember() runs alongside the claim pass.

Dual-pass stub-LLM routing: make_stub_llm returns ONE canned response for ANY
prompt. The two passes call the SAME adapter with DIFFERENT prompts. We seed the
EPISODIC JSON as the default response and let the claim pass parse-fail to empty:
the episodic objects carry actor/action/theme but NO subject/predicate/object,
so the belief parser skips every element (lenient) → 0 belief statements, while
the episodic parser reads them as 3 events. This proves BOTH passes run and the
episodic rows land, with zero network and no fragile prompt-hash reproduction.

sub-project A phase 6 Task 6.2 — adds a GATED real-LLM end-to-end (the A→B
handoff proof). It is skipped unless STARLING_RUN_LLM_E2E is set (plus an
OPENAI_API_KEY/DEEPSEEK_API_KEY), so the offline suite stays green regardless of
inherited keys. When opt-in IS present with a key it
drives a real LLM through the SAME dual-pass remember() and asserts the full
handoff payload: OCCURRED events (put/leave/move) + episodic_events seq in
narrative order + participants + ground-truth current location via
latest_event_location("ball") == "box". The controller runs this variant
separately (see the run command in the test docstring).
"""
import os
import sqlite3

import pytest

import starling

# Episodic JSON for the Sally/Anne narrative, in narrative order (incl. the
# Sally "leave" presence-change event). Has NO subject/predicate/object keys,
# so the belief/conversation parser yields nothing from it.
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


def _query(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_dual_pass_remember_writes_episodic_events(tmp_path):
    db_path = str(tmp_path / "episodic.db")
    llm = starling.make_stub_llm(default_response=EPISODIC_JSON)
    mem = starling.Memory.open(db_path, agent="self", llm=llm)
    try:
        res = mem.remember(NARRATIVE, now="2026-06-16T10:00:00Z")
        assert res.outcome in ("accepted", "idempotent")
        # The 3 episodic event statements surface in the merged result.
        assert len(res.statement_ids) >= 3
    finally:
        mem.close()

    # OCCURRED event statements exist (holder=self, perspective=first_person).
    occ = _query(
        db_path,
        "SELECT subject_id, predicate, object_value, polarity, provenance, "
        "review_status FROM statements WHERE modality='occurred' "
        "AND holder_id='self' AND holder_perspective='first_person' "
        "ORDER BY subject_id, predicate")
    triples = {(r[0], r[1], r[2]) for r in occ}
    assert ("Sally", "put", "ball") in triples
    assert ("Sally", "leave", "room") in triples   # presence-change is its own event
    assert ("Anne", "move", "ball") in triples
    assert len(occ) == 3
    # OCCURRED action verbs are kept verbatim and approved (not downgraded).
    for _subj, _pred, _obj, polarity, provenance, review in occ:
        assert polarity == "pos"
        assert provenance == "user_input"
        assert review == "approved"

    # episodic_events extension rows: one per OCCURRED statement, seq 1/2/3,
    # location basket/NULL/box, participants ["Sally"]/["Sally"]/["Anne"].
    rows = _query(
        db_path,
        "SELECT e.seq, e.location, e.participants_json, e.action_raw, "
        "s.subject_id, s.object_value "
        "FROM episodic_events e "
        "JOIN statements s ON s.id = e.statement_id AND s.tenant_id = e.tenant_id "
        "WHERE s.modality='occurred' ORDER BY e.seq")
    assert len(rows) == 3
    by_seq = {r[0]: r for r in rows}
    assert by_seq[1][1] == "basket"          # put -> basket
    assert by_seq[1][2] == '["Sally"]'
    assert by_seq[1][3] == "put"
    assert by_seq[2][1] is None              # leave -> location NULL
    assert by_seq[2][2] == '["Sally"]'
    assert by_seq[2][3] == "leave"
    assert by_seq[3][1] == "box"             # move -> box
    assert by_seq[3][2] == '["Anne"]'
    assert by_seq[3][3] == "move"


def test_dual_pass_belief_pass_independent_empty_episodic(tmp_path):
    """When the LLM returns a belief-shaped array, the episodic pass parses it to
    zero events (no actor/action/theme), and the belief pass writes its claim —
    proving the two passes are independent and an empty episodic result is fine."""
    belief_json = (
        '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
        '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
        '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
    )
    db_path = str(tmp_path / "belief_only.db")
    llm = starling.make_stub_llm(default_response=belief_json)
    mem = starling.Memory.open(db_path, agent="self", llm=llm)
    try:
        res = mem.remember("Bob owns the auth module", now="2026-06-16T10:00:00Z")
        assert res.outcome in ("accepted", "idempotent")
        assert len(res.statement_ids) >= 1
    finally:
        mem.close()

    # One belief statement, zero OCCURRED rows, zero episodic_events.
    n_belief = _query(db_path,
                      "SELECT COUNT(*) FROM statements WHERE predicate='responsible_for'")[0][0]
    n_occurred = _query(db_path,
                        "SELECT COUNT(*) FROM statements WHERE modality='occurred'")[0][0]
    n_episodic = _query(db_path, "SELECT COUNT(*) FROM episodic_events")[0][0]
    assert n_belief == 1
    assert n_occurred == 0
    assert n_episodic == 0


# ----- Task 6.2: gated real-LLM end-to-end (the A→B handoff proof) -----
#
# Run it explicitly (opt-in + key required; not in CI). DeepSeek-compatible
# endpoint:
#
#   STARLING_RUN_LLM_E2E=1 OPENAI_API_KEY=$DEEPSEEK_API_KEY \
#   OPENAI_BASE_URL=https://api.deepseek.com/v1 \
#   .venv/bin/python -m pytest \
#       tests/python/test_episodic_e2e.py::test_real_llm_dual_pass_handoff -v
#
# (make_openai_llm reads the key from OPENAI_API_KEY only; if you have it under
# DEEPSEEK_API_KEY this test copies it into OPENAI_API_KEY for the adapter.)

_HAS_LLM_KEY = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))
# Require an EXPLICIT opt-in (STARLING_RUN_LLM_E2E) in addition to a key. The
# real-LLM test hits a hardcoded DeepSeek endpoint, so an inherited but unrelated
# OPENAI_API_KEY (e.g. a real OpenAI key) would otherwise run it with the wrong
# key, get 0 events, and FAIL. Gating on opt-in keeps the default suite green.
_RUN_LLM_E2E = bool(os.environ.get("STARLING_RUN_LLM_E2E")) and _HAS_LLM_KEY


def _participants(participants_json):
    import json
    return set(json.loads(participants_json or "[]"))


@pytest.mark.skipif(
    not _RUN_LLM_E2E,
    reason="real-LLM e2e: set STARLING_RUN_LLM_E2E=1 (+ OPENAI_API_KEY/"
           "DEEPSEEK_API_KEY for the DeepSeek endpoint) to run")
def test_real_llm_dual_pass_handoff(tmp_path):
    """A→B handoff proof on a REAL model: the Sally/Anne narrative must yield
    OCCURRED events (put / leave / move) with episodic_events rows in narrative
    seq order, locations basket / (null) / box, participants Sally / Sally /
    Anne, and latest_event_location("ball") == "box"."""
    # make_openai_llm sources the key from OPENAI_API_KEY only; mirror the eval
    # harness (OPENAI_API_KEY=$DASHSCOPE_API_KEY) when only DEEPSEEK_API_KEY is set.
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("DEEPSEEK_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

    db_path = str(tmp_path / "episodic_real.db")
    llm = starling.make_openai_llm(
        model="deepseek-v4-pro", base_url="https://api.deepseek.com/v1")
    mem = starling.Memory.open(db_path, agent="self", llm=llm)
    try:
        mem.remember(NARRATIVE, now="2026-06-16T10:00:00Z")
        # Ground-truth current location is computed from the highest-seq event.
        assert mem.latest_event_location("ball") == "box"
    finally:
        mem.close()

    # OCCURRED event statements exist for put(Sally,ball) / leave(Sally) /
    # move(Anne,ball). The real model picks its own action verbs and may phrase
    # the exit as "leave"/"leaves"/"exit"; assert on actor+theme+presence.
    occ = _query(
        db_path,
        "SELECT subject_id, predicate, object_value FROM statements "
        "WHERE modality='occurred' AND holder_id='self' "
        "AND holder_perspective='first_person'")
    triples = {(r[0], r[1], r[2]) for r in occ}

    def _has(actor, theme):
        return any(s == actor and o == theme for (s, _p, o) in triples)

    assert _has("Sally", "ball"), f"missing Sally put-ball event: {triples}"
    assert _has("Anne", "ball"), f"missing Anne move-ball event: {triples}"
    # A leave/exit presence-change event by Sally (its own event, theme≈room).
    assert any(s == "Sally" and p in ("leave", "leaves", "exit", "exits", "left")
               for (s, p, _o) in triples), f"missing Sally leave event: {triples}"

    # episodic_events rows: seq in narrative order put < leave < move, with
    # locations basket / (null) / box and participants Sally / Sally / Anne.
    rows = _query(
        db_path,
        "SELECT e.seq, e.location, e.participants_json, e.action_raw, "
        "s.subject_id, s.object_value "
        "FROM episodic_events e "
        "JOIN statements s ON s.id = e.statement_id AND s.tenant_id = e.tenant_id "
        "WHERE s.modality='occurred' ORDER BY e.seq")
    assert len(rows) >= 3, f"expected >=3 episodic rows, got {rows}"

    # Locate the three landmark events by their (actor, theme/presence) identity.
    put_row = next((r for r in rows if r[4] == "Sally" and r[5] == "ball"), None)
    move_row = next((r for r in rows if r[4] == "Anne" and r[5] == "ball"), None)
    leave_row = next(
        (r for r in rows if r[4] == "Sally"
         and r[3] in ("leave", "leaves", "exit", "exits", "left")),
        None)
    assert put_row is not None, f"no Sally/ball row: {rows}"
    assert move_row is not None, f"no Anne/ball row: {rows}"
    assert leave_row is not None, f"no Sally leave row: {rows}"

    # seq is in narrative order: put < leave < move.
    assert put_row[0] < leave_row[0] < move_row[0], (
        f"seq not in narrative order put<leave<move: "
        f"put={put_row[0]} leave={leave_row[0]} move={move_row[0]}")

    # Locations: put -> basket, leave -> NULL (no place), move -> box.
    assert put_row[1] == "basket", f"put location != basket: {put_row}"
    assert leave_row[1] is None, f"leave location should be NULL: {leave_row}"
    assert move_row[1] == "box", f"move location != box: {move_row}"

    # Participants name Sally / Sally / Anne respectively.
    assert "Sally" in _participants(put_row[2]), f"put participants: {put_row[2]}"
    assert "Sally" in _participants(leave_row[2]), f"leave participants: {leave_row[2]}"
    assert "Anne" in _participants(move_row[2]), f"move participants: {move_row[2]}"
