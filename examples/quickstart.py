"""Starling Memory quickstart — offline, no API key.

Run:  python examples/quickstart.py

Demonstrates the public `starling.Memory` facade end-to-end, fully offline
(no network, no OPENAI_API_KEY) via a deterministic stub LLM:

  1. write a memory          — remember(text) → stub Extractor extracts a statement
  2. materialize a persona   — PersonaContainer.rebuild (explicit; not auto in P2.e)
  3. record a due commitment — seed a COMMITS statement + create it via CommitmentEngine,
                               then mark its trigger `fired` (PolicyEngine would do this live)
  4. tick                    — advance embed + commitment background workers
  5. render a working set    — a prompt-ready ContextBlock; the fired commitment
                               surfaces as a ⚠ DUE reminder under "## Pending commitments"

Single-adapter discipline: all C++ engine calls go through ONE Memory's
`mem._rt.adapter` (the WAL writer). Raw sqlite3 seeds set busy_timeout, commit,
and close BEFORE any C++ write — strictly sequential, never concurrent, and we
never open a second SqliteAdapter on the same file.
"""
import pathlib
import sqlite3
import tempfile

import starling
from starling import _core

# Canned JSON-array response the Extractor accepts (mirrors
# tests/python/test_memory_facade.py). The orchestrator stamps holder_id with
# the agent ("alice"); the JSON "holder" is advisory.
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _seed_commit_stmt(conn, sid, holder, subject, obj):
    """Seed a COMMITS statement (24 columns) the CommitmentEngine can promote."""
    conn.execute(
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES(?,?,?,?,'cognizer',?,'owes','str',?,?,'v1','commits',"
        "'pos',0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,'2026-06-01T09:00:00Z','user_input',"
        "'consolidated','approved','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')",
        (sid, "default", holder, "first_person", subject, obj, "a" * 64))


def main() -> str:
    tmp = pathlib.Path(tempfile.mkdtemp()) / "quickstart.db"
    db = str(tmp)
    mem = starling.Memory.open(
        db, agent="alice",
        llm=starling.make_stub_llm(default_response=CANNED_JSON))
    adapter = mem._rt.adapter  # the single WAL adapter for all C++ engine calls

    # 1) write a memory via the extractor (stub, offline)
    mem.remember("Bob owns the auth module.")

    # 2) materialize a persona (explicit — not auto-built in P2.e)
    _core.PersonaContainer(adapter).rebuild(
        "default", "alice",
        [_core.AnchorStatement(
            stmt_id="a1", anchor_type="self_model_anchor",
            dimension="traits", value="concise", confidence=0.9)],
        "2026-06-01T09:00:00Z")

    # 3a) seed a COMMITS statement (raw sqlite3; commit+close BEFORE any C++ write)
    c = sqlite3.connect(db)
    c.execute("PRAGMA busy_timeout=30000")
    _seed_commit_stmt(c, "c1", "alice", "bob", "design doc")
    c.commit()
    c.close()

    # 3b) create the commitment (ACTIVE) via the engine on the SAME adapter.
    #     Deadline is in the FUTURE relative to the tick below (12:00 > 10:00),
    #     so PolicyEngine.tick leaves it ACTIVE (an expired deadline would move
    #     it to BROKEN and it would drop out of `pending`, which is ACTIVE-only).
    _core.CommitmentEngine(adapter).create_from_statement(
        "c1", "default", "2026-06-01T12:00:00Z", "2026-06-01T06:00:00Z")

    # 3c) mark its trigger `fired` (a reminder is due now). PolicyEngine.tick
    #     would set this in production; here we seed it directly. Seeded AFTER
    #     create_from_statement so the engine's own trigger bookkeeping doesn't
    #     clobber the fired status.
    c = sqlite3.connect(db)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute(
        "INSERT INTO commitment_triggers(id,commitment_stmt_id,tenant_id,kind,spec_json,"
        "status,created_at) VALUES('t1','c1','default','time','{}','fired',"
        "'2026-06-01T09:00:00Z')")
    c.commit()
    c.close()

    # 4) advance async machinery (embed pending statements + commitment tick)
    mem.tick()

    # 5) render the prompt-ready working set (fired commitment → ⚠ DUE reminder)
    cb = mem.render_working_set(interlocutor="bob", goal="auth")
    out = cb.render()
    mem.close()
    return out


if __name__ == "__main__":
    print(main())
