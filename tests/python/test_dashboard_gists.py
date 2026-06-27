"""#38-C v2 observability: dashboard queries.gists() — lists consolidation_abstract
gists (summary/confidence/derived_from/state), tenant-scoped, with by_state counts.
Schema built via a throwaway runtime, then gist rows seeded directly (same handle-
release discipline as the other dashboard query tests)."""
import sqlite3
from pathlib import Path

from starling import runtime as rt
from starling.dashboard import queries
from starling.testing import relax_preflight_for_m0_3


def _prep(db):
    relax_preflight_for_m0_3()
    runtime = rt._build_local_store_sqlite_runtime(Path(db))
    runtime.start()
    del runtime  # release the writer handle before raw seeding
    return db


def _seed(db, *, stmt_id, provenance="consolidation_abstract", state="consolidated",
          summary="People like coffee.", confidence=0.8, derived='["m1","m2","m3"]',
          tenant="default", predicate="likes", obj="coffee", holder="__common_ground__"):
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
            "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
            "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
            "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
            "access_count,derived_from_json,consolidation_summary,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, tenant, holder, "inferred", "entity", "__people__", predicate,
             "str", obj, "a" * 64, "v1", "believes", "pos", confidence, "2026-06-27T00:00:00Z",
             0.5, "{}", 0.0, "2026-06-27T00:00:00Z", provenance, state, "approved", 1,
             derived, summary, "2026-06-27T00:00:00Z", "2026-06-27T00:00:00Z"))
        conn.commit()
    finally:
        conn.close()


def test_gists_lists_only_consolidation_abstract(tmp_path):
    db = _prep(str(tmp_path / "g.db"))
    _seed(db, stmt_id="g1", state="consolidated", summary="People like coffee.", confidence=0.8)
    _seed(db, stmt_id="g2", state="volatile", summary=None, confidence=0.5)
    _seed(db, stmt_id="other", provenance="user_input", state="consolidated")  # not a gist

    out = queries.gists(db, "default")
    assert {g["id"] for g in out["gists"]} == {"g1", "g2"}     # user_input excluded
    assert out["by_state"] == {"consolidated": 1, "volatile": 1}
    g1 = next(g for g in out["gists"] if g["id"] == "g1")
    assert g1["consolidation_summary"] == "People like coffee."
    assert abs(g1["confidence"] - 0.8) < 1e-6
    assert g1["derived_from"] == ["m1", "m2", "m3"]            # derived_from_json parsed to list


def test_gists_tenant_scoped(tmp_path):
    db = _prep(str(tmp_path / "g2.db"))
    _seed(db, stmt_id="a1", tenant="A")
    _seed(db, stmt_id="b1", tenant="B")
    assert {g["id"] for g in queries.gists(db, "A")["gists"]} == {"a1"}


def test_gists_empty(tmp_path):
    db = _prep(str(tmp_path / "g3.db"))
    assert queries.gists(db, "default") == {"by_state": {}, "gists": []}


def test_gist_members_returns_derived_from(tmp_path):
    db = _prep(str(tmp_path / "gm.db"))
    for mid, holder in (("m1", "alice"), ("m2", "bob"), ("m3", "carol")):
        _seed(db, stmt_id=mid, holder=holder, provenance="user_input", state="consolidated",
              summary=None, derived="[]")
    _seed(db, stmt_id="g1", derived='["m1","m2","m3"]')

    out = queries.gist_members(db, "default", "g1")
    assert out["gist_id"] == "g1"
    assert {m["id"] for m in out["members"]} == {"m1", "m2", "m3"}
    assert {m["holder_id"] for m in out["members"]} == {"alice", "bob", "carol"}


def test_gist_members_missing_gist(tmp_path):
    db = _prep(str(tmp_path / "gm2.db"))
    assert queries.gist_members(db, "default", "nope") == {"gist_id": "nope", "members": []}


def test_gist_members_tenant_scoped(tmp_path):
    db = _prep(str(tmp_path / "gm3.db"))
    _seed(db, stmt_id="m1", tenant="A", provenance="user_input", summary=None, derived="[]")
    _seed(db, stmt_id="g1", tenant="A", derived='["m1"]')
    # querying tenant B for tenant A's gist → not found → no members
    assert queries.gist_members(db, "B", "g1")["members"] == []
