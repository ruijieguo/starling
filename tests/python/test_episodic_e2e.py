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
"""
import sqlite3

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
