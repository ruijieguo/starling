import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app


def _seed(db_path: str):
    """Build the schema via the runtime, then raw-seed a few rows, commit+close."""
    from pathlib import Path
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    # ensure WAL is flushed and the writer handle is released before raw seeding
    del r
    conn = sqlite3.connect(db_path)
    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO statements (id, tenant_id, holder_id, holder_perspective, "
        "subject_kind, subject_id, predicate, object_kind, object_value, "
        "canonical_object_hash, canonical_object_hash_version, modality, polarity, "
        "confidence, observed_at, salience, affect_json, activation, last_accessed, "
        "provenance, created_at, updated_at) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, "default", "self", "first_person", "cognizer", "Bob", "responsible_for",
         "str", "auth", "h", "v1", "BELIEVES", "POS", 0.9, "2026-04-15T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-15T10:00:00Z", "test",
         "2026-04-15T10:00:00Z", "2026-04-15T10:00:00Z"),
    )
    conn.execute(
        "INSERT INTO commitments (stmt_id, tenant_id, state, broken_count, deadline, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (sid, "default", "ACTIVE", 0, "2026-04-20T10:00:00Z",
         "2026-04-15T10:00:00Z", "2026-04-15T10:00:00Z"),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "dash.db")
    _seed(db)
    cfg = DashboardConfig(db_path=db, token="")
    return TestClient(create_app(cfg))


def test_overview(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["statements"] >= 1
    assert body["commitments_by_state"].get("ACTIVE") == 1


def test_statements_filter(client):
    r = client.get("/api/statements", params={"predicate": "responsible_for"})
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows and rows[0]["predicate"] == "responsible_for"


def test_commitments_joins_statement(client):
    r = client.get("/api/commitments")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows and rows[0]["state"] == "ACTIVE" and rows[0]["object_value"] == "auth"


def test_replay_conflicts_queues_shape(client):
    assert client.get("/api/replay").status_code == 200
    assert "by_kind" in client.get("/api/conflicts").json()
    assert "embedding_backlog" in client.get("/api/queues").json()


def test_eval_reports(client):
    r = client.get("/api/eval")
    assert r.status_code == 200 and isinstance(r.json()["reports"], list)
