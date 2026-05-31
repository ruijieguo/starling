import sqlite3

import pytest

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_commits(rt, sid):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
            "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
            "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
            "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, "default", "alice", "first_person", "cognizer", "bob", "will_send", "str", "report",
             "a" * 64, "v1", "COMMITS", "pos", 0.9, "2026-05-30T09:00:00Z", 0.5, "{}", 0.0,
             "2026-05-30T09:00:00Z", "user_input", "consolidated", "approved",
             "2026-05-30T09:00:00Z", "2026-05-30T09:00:00Z"))
        c.commit()


def test_commitment_lifecycle(rt):
    _seed_commits(rt, "c1")
    eng = _core.CommitmentEngine(rt.adapter)
    eng.create_from_statement("c1", "default", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        assert c.execute("SELECT state FROM commitments WHERE stmt_id='c1'").fetchone()[0] == "ACTIVE"
        assert c.execute("SELECT COUNT(*) FROM commitment_protection WHERE protected_stmt_id='c1'").fetchone()[0] == 1
    eng.fulfill("c1", "default", "2026-05-30T11:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        assert c.execute("SELECT state FROM commitments WHERE stmt_id='c1'").fetchone()[0] == "FULFILLED"
