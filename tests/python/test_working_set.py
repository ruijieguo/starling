"""P2.e working_set — render_working_set assembles sections; fired commitment → ⚠ reminder."""
import sqlite3
import starling
from starling import _core

def _seed_commit_stmt(conn, sid, holder, subject, obj):
    conn.execute(
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES(?,?,?,?,'cognizer',?,'owes','str',?,?,'v1','commits',"
        "'pos',0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,'2026-06-01T09:00:00Z','user_input',"
        "'consolidated','approved','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')",
        (sid, "default", holder, "first_person", subject, obj, "a"*64))

def test_working_set_has_reminder_after_tick(tmp_path):
    db = str(tmp_path / "ws.db")
    mem = starling.Memory.open(db, agent="alice")          # no llm needed; we seed directly
    adapter = mem._rt.adapter

    # 1) seed a COMMITS statement (raw sqlite3; commit+close BEFORE any C++ write)
    c = sqlite3.connect(db); c.execute("PRAGMA busy_timeout=30000")
    _seed_commit_stmt(c, "c1", "alice", "bob", "design doc")
    c.commit(); c.close()

    # 2) create the commitment (ACTIVE) via the engine on the SAME adapter
    _core.CommitmentEngine(adapter).create_from_statement(
        "c1", "default", "2026-06-01T07:00:00Z", "2026-06-01T06:00:00Z")

    # 3) seed a fired trigger (simulate PolicyEngine already fired the due commitment)
    c = sqlite3.connect(db); c.execute("PRAGMA busy_timeout=30000")
    c.execute("INSERT INTO commitment_triggers(id,commitment_stmt_id,tenant_id,kind,spec_json,"
              "status,created_at) VALUES('t1','c1','default','time','{}','fired','2026-06-01T07:00:00Z')")
    c.commit(); c.close()

    cb = mem.render_working_set(interlocutor="bob", goal="auth", token_budget=2000)
    rendered = cb.render()
    assert "design doc" in rendered
    assert "⚠" in rendered                              # ⚠ fired reminder
    assert "pending_commitments" in {b.label for b in cb.blocks}
    mem.close()

def test_token_budget_truncates(tmp_path):
    from starling.working_set import assemble
    big = "x" * 4000     # ~1000 tokens
    cb = assemble({"relevant_memories": big}, token_budget=10)   # 10 tokens → 40 chars kept
    assert "relevant_memories" in cb.truncated
    assert len(cb.blocks[0].content) <= 40
