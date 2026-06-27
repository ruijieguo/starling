"""#38-C v2: full-journey integration — volatile statements (as remember leaves
them: replay_count=0) → run_sleep consolidation → gist visible via queries.gists.
This exercises the real replay→cluster→write path end-to-end (not piece-wise),
which is where the replay_count/threshold interaction actually bites."""
import sqlite3
from pathlib import Path

from starling import _core
from starling import runtime as rt
from starling.dashboard import queries
from starling.testing import relax_preflight_for_m0_3


def _prep_with_cluster(db, *, replay_count=0):
    """Schema via throwaway runtime, then 3 distinct holders each asserting the
    same (predicate, object) — volatile, user_input (so sample_volatile picks
    them up), as fresh remember()'d statements would be."""
    relax_preflight_for_m0_3()
    runtime = rt._build_local_store_sqlite_runtime(Path(db))
    runtime.start()
    del runtime
    conn = sqlite3.connect(db)
    try:
        for idx, holder in enumerate(("alice", "bob", "carol")):
            conn.execute(
                "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
                "subject_kind,subject_id,predicate,object_kind,object_value,"
                "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
                "confidence,observed_at,salience,affect_json,activation,last_accessed,"
                "provenance,replay_count,consolidation_state,review_status,access_count,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"m{idx}", "default", holder, "first_person", "cognizer", "subj",
                 "knows", "str", "coffee", "a" * 64, "v1", "believes", "pos",
                 0.9, "2026-06-27T09:00:00Z", 0.5, "{}", 0.0, "2026-06-27T09:00:00Z",
                 "user_input", replay_count, "volatile", "approved", 1,
                 "2026-06-27T09:00:00Z", "2026-06-27T09:00:00Z"))
        conn.commit()
    finally:
        conn.close()


def _run_sleep(db):
    runtime = rt._build_local_store_sqlite_runtime(Path(db))
    runtime.start()
    sched = _core.ReplayScheduler(runtime.adapter)
    sched.run_sleep("2026-06-27T12:00:00Z")   # no LLM → deterministic gist if a cluster forms
    del sched
    del runtime


def test_journey_volatile_to_gist(tmp_path):
    """The real journey from fresh (replay_count=0) volatile statements must
    eventually produce a consolidation gist visible in /gists."""
    db = str(tmp_path / "journey.db")
    _prep_with_cluster(db, replay_count=0)
    _run_sleep(db)
    out = queries.gists(db, "default")
    assert len(out["gists"]) >= 1, (
        f"no gist formed from a 3-holder norm via the live journey; "
        f"by_state={out['by_state']}"
    )
