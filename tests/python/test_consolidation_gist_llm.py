"""#38-C Phase 3: the consolidation LLM judges NORM gists via the run_sleep
binding. Parity for the C++ GistWriter.Llm* tests — proves the optional `llm`
param threads Python→C++, the C++ core owns the NORM-gist prompt/orchestration,
and Python only injects the adapter. Deterministic FakeLLMAdapter; no API key.
"""
import sqlite3
from pathlib import Path

from starling import _core
from starling import runtime as rt
from starling.testing import relax_preflight_for_m0_3


def _seed_norm_cluster(db):
    """Build the schema via a throwaway runtime (released before the test opens
    its own), then seed 3 distinct holders asserting the same (predicate, object)
    — a NORM cluster — volatile / user_input / replay_count=2 so it qualifies."""
    relax_preflight_for_m0_3()
    runtime = rt._build_local_store_sqlite_runtime(Path(db))
    runtime.start()
    del runtime  # release the writer handle before raw seeding
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
                 0.9, "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
                 "user_input", 2, "volatile", "approved", 1,
                 "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        conn.commit()
    finally:
        conn.close()


def _read_gist(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT confidence, consolidation_summary, consolidation_state, review_status "
            "FROM statements WHERE provenance='consolidation_abstract'").fetchone()
    finally:
        conn.close()


def test_run_sleep_with_consolidation_llm(tmp_path):
    db = str(tmp_path / "gist.db")
    _seed_norm_cluster(db)
    runtime = rt._build_local_store_sqlite_runtime(Path(db))
    runtime.start()
    sched = _core.ReplayScheduler(runtime.adapter)
    llm = _core.FakeLLMAdapter()
    # Combined response: judge reads {confidence, summary}; verify reads {entailed}.
    llm.set_default_response(
        '{"confidence": 0.77, "summary": "People know coffee.", "entailed": true}', True, "")

    stats = sched.run_sleep("2026-06-27T12:00:00Z", llm)
    assert stats.abstracted >= 1
    del sched
    del runtime  # release the writer before the read connection

    row = _read_gist(db)
    assert row is not None
    assert abs(row[0] - 0.77) < 1e-6          # LLM-judged confidence
    assert row[1] == "People know coffee."    # LLM summary persisted
    assert row[2] == "consolidated"           # Phase 4: verified + promoted to live
    assert row[3] == "approved"


def test_run_sleep_without_llm_is_deterministic(tmp_path):
    db = str(tmp_path / "gist_det.db")
    _seed_norm_cluster(db)
    runtime = rt._build_local_store_sqlite_runtime(Path(db))
    runtime.start()
    sched = _core.ReplayScheduler(runtime.adapter)

    stats = sched.run_sleep("2026-06-27T12:00:00Z")  # no llm → deterministic Phase-2 path
    assert stats.abstracted >= 1
    del sched
    del runtime

    row = _read_gist(db)
    assert row is not None
    assert abs(row[0] - 0.5) < 1e-6   # provisional confidence
    assert row[1] is None             # no LLM summary
    assert row[2] == "volatile"       # no LLM ⇒ inert, never promoted
    assert row[3] != "approved"
