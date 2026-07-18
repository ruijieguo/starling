"""T0d-2 — Persona / CommonGround read-only inspection endpoints.

Two new read-only surfaces filling the neocortex sub-region gap:
queries.personae (containers WHERE kind='persona') and queries.common_ground
(the common_ground pool, five-state status, LEFT JOIN statements for text).
Both are pure derived reads (open_ro, tenant-scoped), no write path added —
the container/common-ground state machines live in the C++ core.

Mirrors tests/python/test_dashboard_engrams.py: each query covers empty /
single-row / cross-tenant isolation; the HTTP routes each get one 200.
"""
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from starling import runtime as rt
from starling.dashboard import DashboardConfig, create_app, queries

# ── seeding helpers ────────────────────────────────────────────────────────

_STMT_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, modality, "
    "polarity, confidence, observed_at, salience, affect_json, activation, "
    "last_accessed, provenance, created_at, updated_at, evidence_json"
)


def _fresh_db(db_path: str) -> sqlite3.Connection:
    """Build the schema via the runtime, release the writer, return a raw conn."""
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r
    return sqlite3.connect(db_path)


def _container(conn, cid, *, tenant="default", kind="persona", holder="self",
               scope='{"scope":"global"}', created="2026-04-10T10:00:00Z",
               updated="2026-04-10T10:00:00Z", version=1):
    conn.execute(
        "INSERT INTO containers (id, tenant_id, kind, holder_id, scope_descriptor, "
        "created_at, updated_at, version) VALUES (?,?,?,?,?,?,?,?)",
        (cid, tenant, kind, holder, scope, created, updated, version),
    )


def _cg(conn, cgid, *, tenant="default", statement_id="s1", status="grounded",
        parties='["A","B"]', grounded_at=None, last_confirmed_at=None,
        created="2026-04-10T10:00:00Z", updated="2026-04-10T10:00:00Z"):
    conn.execute(
        "INSERT INTO common_ground (id, tenant_id, statement_id, status, parties_json, "
        "grounded_at, last_confirmed_at, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (cgid, tenant, statement_id, status, parties, grounded_at, last_confirmed_at,
         created, updated),
    )


def _stmt(conn, sid, *, tenant="default", subj="X", predicate="rel", obj="v"):
    conn.execute(
        f"INSERT INTO statements ({_STMT_COLS}) VALUES ({','.join('?' * 22)})",
        (sid, tenant, "self", "first_person", "cognizer", subj, predicate, "str", obj,
         f"h{sid}", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z", 0.5, "{}", 0.0,
         "2026-04-10T10:00:00Z", "user_input", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", "[]"),
    )


# ── queries.personae ────────────────────────────────────────────────────────

def test_personae_empty(tmp_path):
    db = str(tmp_path / "empty.db")
    conn = _fresh_db(db)
    conn.commit()
    conn.close()
    assert queries.personae(db, "default") == {"rows": []}


def test_personae_single_row(tmp_path):
    db = str(tmp_path / "one.db")
    conn = _fresh_db(db)
    _container(conn, "p1", kind="persona", holder="alice", version=3)
    conn.commit()
    conn.close()

    out = queries.personae(db, "default")
    assert len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["id"] == "p1"
    assert row["holder_id"] == "alice"
    assert row["version"] == 3
    assert row["scope_descriptor"] == '{"scope":"global"}'


def test_personae_only_persona_kind(tmp_path):
    # kind filter: common_ground / knowledge_frontier containers never surface here.
    db = str(tmp_path / "kinds.db")
    conn = _fresh_db(db)
    _container(conn, "p1", kind="persona")
    _container(conn, "cg1", kind="common_ground")
    _container(conn, "kf1", kind="knowledge_frontier")
    conn.commit()
    conn.close()

    out = queries.personae(db, "default")
    assert {r["id"] for r in out["rows"]} == {"p1"}


def test_personae_tenant_scoped(tmp_path):
    db = str(tmp_path / "tenant.db")
    conn = _fresh_db(db)
    _container(conn, "mine", tenant="default", kind="persona")
    _container(conn, "alien", tenant="other", kind="persona")
    conn.commit()
    conn.close()

    out = queries.personae(db, "default")
    assert {r["id"] for r in out["rows"]} == {"mine"}


# ── queries.common_ground ─────────────────────────────────────────────────────

def test_common_ground_empty(tmp_path):
    db = str(tmp_path / "cg_empty.db")
    conn = _fresh_db(db)
    conn.commit()
    conn.close()
    out = queries.common_ground(db, "default")
    assert out == {"rows": [], "by_status": {}}


def test_common_ground_joins_statement_text(tmp_path):
    db = str(tmp_path / "cg_join.db")
    conn = _fresh_db(db)
    _stmt(conn, "s1", subj="Bob", predicate="responsible_for", obj="auth")
    _cg(conn, "cg1", statement_id="s1", status="grounded")
    conn.commit()
    conn.close()

    out = queries.common_ground(db, "default")
    assert len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["id"] == "cg1"
    assert row["status"] == "grounded"
    assert row["subject_id"] == "Bob"
    assert row["predicate"] == "responsible_for"
    assert row["object_value"] == "auth"
    assert out["by_status"] == {"grounded": 1}


def test_common_ground_by_status_counts(tmp_path):
    db = str(tmp_path / "cg_status.db")
    conn = _fresh_db(db)
    _cg(conn, "a", statement_id="s1", status="grounded")
    _cg(conn, "b", statement_id="s2", status="grounded")
    _cg(conn, "c", statement_id="s3", status="suspected_diverge")
    _cg(conn, "d", statement_id="s4", status="recanted")
    conn.commit()
    conn.close()

    out = queries.common_ground(db, "default")
    assert out["by_status"] == {"grounded": 2, "suspected_diverge": 1, "recanted": 1}


def test_common_ground_missing_statement_null_text(tmp_path):
    # LEFT JOIN: a common_ground row whose statement is absent/forgotten still
    # surfaces, with NULL subject/predicate/object rather than being dropped.
    db = str(tmp_path / "cg_orphan.db")
    conn = _fresh_db(db)
    _cg(conn, "cg1", statement_id="gone")
    conn.commit()
    conn.close()

    out = queries.common_ground(db, "default")
    assert len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["subject_id"] is None
    assert row["predicate"] is None
    assert row["object_value"] is None


def test_common_ground_tenant_scoped(tmp_path):
    db = str(tmp_path / "cg_tenant.db")
    conn = _fresh_db(db)
    _cg(conn, "mine", tenant="default", statement_id="s1")
    _cg(conn, "alien", tenant="other", statement_id="s2")
    conn.commit()
    conn.close()

    out = queries.common_ground(db, "default")
    assert {r["id"] for r in out["rows"]} == {"mine"}
    assert out["by_status"] == {"grounded": 1}


def test_common_ground_join_does_not_leak_cross_tenant_statement(tmp_path):
    # The JOIN is tenant-scoped too: a same-id statement in another tenant must
    # not supply text to this tenant's common_ground row.
    db = str(tmp_path / "cg_join_tenant.db")
    conn = _fresh_db(db)
    _stmt(conn, "s1", tenant="other", subj="Alien", predicate="secret", obj="x")
    _cg(conn, "cg1", tenant="default", statement_id="s1")
    conn.commit()
    conn.close()

    out = queries.common_ground(db, "default")
    assert len(out["rows"]) == 1
    assert out["rows"][0]["subject_id"] is None


# ── HTTP routes ──────────────────────────────────────────────────────────

def _client(db_path: str) -> TestClient:
    cfg = DashboardConfig(db_path=db_path, token="")
    return TestClient(create_app(cfg))


def test_route_personae(tmp_path):
    db = str(tmp_path / "route_personae.db")
    conn = _fresh_db(db)
    _container(conn, "p1", kind="persona", holder="alice")
    conn.commit()
    conn.close()

    r = _client(db).get("/api/personae")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["id"] == "p1"


def test_route_common_ground(tmp_path):
    db = str(tmp_path / "route_cg.db")
    conn = _fresh_db(db)
    _stmt(conn, "s1", subj="Bob", predicate="rel", obj="v")
    _cg(conn, "cg1", statement_id="s1", status="grounded")
    conn.commit()
    conn.close()

    r = _client(db).get("/api/common_ground")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["id"] == "cg1"
    assert body["by_status"] == {"grounded": 1}
