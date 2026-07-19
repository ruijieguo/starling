"""T0a — engram (verbatim evidence) browse/search endpoints.

Two new read-only surfaces filling the previously-missing "raw evidence" data
class: queries.engrams_list / engram_detail, wired at GET /api/engrams and
GET /api/engram/{id}. engram is immutable; these are pure derived reads, no
write path added.

Privacy: engram_detail's payload preview MUST reuse the exact suppression
rule already proven in queries._engrams_for (used by provenance) — inline +
unerased + privacy_class not in {regulated, sensitive, personal} + first 280
chars. This file pins that same invariant for the new single-engram lookup so
a future rewrite can't quietly diverge and leak a suppressed payload.
"""
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from starling import runtime as rt
from starling.dashboard import DashboardConfig, create_app, queries

# ── seeding helpers (mirrors tests/python/test_dashboard_provenance.py) ────

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


def _eng(conn, eid, *, tenant="default", source_kind="user_input", privacy="internal",
          retention="audit_retain", erased=None, payload=b"the verbatim source text",
          content_hash="ch1", source_item_id=None, chunk_index=0, adapter_name="",
          payload_uri=None):
    conn.execute(
        "INSERT INTO engrams (id, tenant_id, content_hash, source_kind, ingest_policy, "
        "ingest_mode, privacy_class, retention_mode, payload_uri, payload_inline, "
        "created_at, erased_at, source_item_id, chunk_index, adapter_name) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, tenant, content_hash, source_kind, "store",
         "uri" if payload is None else "inline", privacy, retention, payload_uri,
         payload, "2026-04-10T10:00:00Z", erased, source_item_id or eid, chunk_index,
         adapter_name),
    )


def _stmt(conn, sid, *, tenant="default", evidence="[]", subj="X", predicate="rel", obj="v"):
    conn.execute(
        f"INSERT INTO statements ({_STMT_COLS}) VALUES ({','.join('?' * 22)})",
        (sid, tenant, "self", "first_person", "cognizer", subj, predicate, "str", obj,
         f"h{sid}", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z", 0.5, "{}", 0.0,
         "2026-04-10T10:00:00Z", "user_input", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", evidence),
    )


def _ev_ref(eid, content_hash="ch1"):
    return f'[{{"engram_ref":"{eid}","content_hash":"{content_hash}","status":"active"}}]'


# ── queries.engrams_list ────────────────────────────────────────────────────

def test_engrams_list_tenant_scoped_and_total(tmp_path):
    db = str(tmp_path / "l.db")
    conn = _fresh_db(db)
    _eng(conn, "e1", tenant="default")
    _eng(conn, "e2", tenant="default")
    _eng(conn, "alien", tenant="other")
    conn.commit()
    conn.close()

    out = queries.engrams_list(db, "default")
    assert out["total"] == 2
    assert {r["id"] for r in out["rows"]} == {"e1", "e2"}


def test_engrams_list_filters_source_kind_and_privacy(tmp_path):
    db = str(tmp_path / "f.db")
    conn = _fresh_db(db)
    _eng(conn, "e_user", source_kind="user_input", privacy="internal")
    _eng(conn, "e_tool", source_kind="tool_observation", privacy="regulated")
    conn.commit()
    conn.close()

    by_kind = queries.engrams_list(db, "default", source_kind="tool_observation")
    assert {r["id"] for r in by_kind["rows"]} == {"e_tool"}
    assert by_kind["total"] == 1

    by_privacy = queries.engrams_list(db, "default", privacy_class="internal")
    assert {r["id"] for r in by_privacy["rows"]} == {"e_user"}


def test_engrams_list_filters_erased_tristate(tmp_path):
    db = str(tmp_path / "e.db")
    conn = _fresh_db(db)
    _eng(conn, "live", erased=None)
    _eng(conn, "gone", erased="2026-05-01T00:00:00Z")
    conn.commit()
    conn.close()

    assert {r["id"] for r in queries.engrams_list(db, "default", erased="yes")["rows"]} == {"gone"}
    assert {r["id"] for r in queries.engrams_list(db, "default", erased="no")["rows"]} == {"live"}
    assert {r["id"] for r in queries.engrams_list(db, "default")["rows"]} == {"live", "gone"}


def test_engrams_list_filters_q_over_hash_and_source_item(tmp_path):
    db = str(tmp_path / "q.db")
    conn = _fresh_db(db)
    _eng(conn, "e1", content_hash="abc123", source_item_id="msg-1")
    _eng(conn, "e2", content_hash="zzz999", source_item_id="msg-2")
    conn.commit()
    conn.close()

    by_hash = queries.engrams_list(db, "default", q="abc")
    assert {r["id"] for r in by_hash["rows"]} == {"e1"}
    by_source_item = queries.engrams_list(db, "default", q="msg-2")
    assert {r["id"] for r in by_source_item["rows"]} == {"e2"}
    assert queries.engrams_list(db, "default", q="nope-nothing")["rows"] == []


# ── queries.engram_detail ───────────────────────────────────────────────────

def test_engram_detail_none_when_absent_or_cross_tenant(tmp_path):
    db = str(tmp_path / "d.db")
    conn = _fresh_db(db)
    _eng(conn, "owned", tenant="default")
    _eng(conn, "alien", tenant="other")
    conn.commit()
    conn.close()

    assert queries.engram_detail(db, "default", "nope") is None
    assert queries.engram_detail(db, "default", "alien") is None
    assert queries.engram_detail(db, "default", "owned") is not None


def test_engram_detail_preview_shown_for_inline_unerased_unrestricted(tmp_path):
    db = str(tmp_path / "p.db")
    conn = _fresh_db(db)
    _eng(conn, "ok", privacy="internal", payload=b"the verbatim source text")
    conn.commit()
    conn.close()

    out = queries.engram_detail(db, "default", "ok")
    assert out["preview"] == "the verbatim source text"
    assert out["preview_suppressed_reason"] is None
    assert out["engram"]["id"] == "ok"
    assert "payload_inline" not in out["engram"]   # raw bytes never re-exposed alongside preview


def test_engram_detail_preview_suppressed_for_restricted_privacy(tmp_path):
    # Same 3-class suppression list as queries._engrams_for/provenance:
    # regulated / sensitive / personal.
    db = str(tmp_path / "priv.db")
    conn = _fresh_db(db)
    for pc in ("regulated", "sensitive", "personal"):
        _eng(conn, f"e_{pc}", privacy=pc)
    conn.commit()
    conn.close()

    for pc in ("regulated", "sensitive", "personal"):
        out = queries.engram_detail(db, "default", f"e_{pc}")
        assert out["preview"] is None
        assert out["preview_suppressed_reason"]


def test_engram_detail_preview_suppressed_when_erased(tmp_path):
    db = str(tmp_path / "erased.db")
    conn = _fresh_db(db)
    _eng(conn, "gone", privacy="internal", erased="2026-05-01T00:00:00Z")
    conn.commit()
    conn.close()

    out = queries.engram_detail(db, "default", "gone")
    assert out["preview"] is None
    assert out["preview_suppressed_reason"]


def test_engram_detail_preview_suppressed_when_uri_only(tmp_path):
    db = str(tmp_path / "uri.db")
    conn = _fresh_db(db)
    _eng(conn, "uri_only", privacy="internal", payload=None, payload_uri="s3://blob/x")
    conn.commit()
    conn.close()

    out = queries.engram_detail(db, "default", "uri_only")
    assert out["preview"] is None
    assert out["preview_suppressed_reason"]


def test_engram_detail_referencing_statements(tmp_path):
    db = str(tmp_path / "ref.db")
    conn = _fresh_db(db)
    _eng(conn, "ev1")
    _stmt(conn, "s1", evidence=_ev_ref("ev1"), subj="Bob", predicate="responsible_for", obj="auth")
    _stmt(conn, "s2", evidence="[]", subj="Carol", predicate="likes", obj="tea")  # no reference
    conn.commit()
    conn.close()

    out = queries.engram_detail(db, "default", "ev1")
    refs = out["referencing_statements"]
    assert {r["id"] for r in refs} == {"s1"}
    assert refs[0]["subject_id"] == "Bob" and refs[0]["predicate"] == "responsible_for"


# ── HTTP routes ──────────────────────────────────────────────────────────

def _client(db_path: str) -> TestClient:
    cfg = DashboardConfig(db_path=db_path, token="")
    return TestClient(create_app(cfg))


def test_route_engrams_list(tmp_path):
    db = str(tmp_path / "route_list.db")
    conn = _fresh_db(db)
    _eng(conn, "e1", source_kind="user_input")
    conn.commit()
    conn.close()

    r = _client(db).get("/api/engrams")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["rows"][0]["id"] == "e1"

    r2 = _client(db).get("/api/engrams", params={"source_kind": "tool_observation"})
    assert r2.status_code == 200 and r2.json()["rows"] == []


def test_route_engram_detail_and_404(tmp_path):
    db = str(tmp_path / "route_detail.db")
    conn = _fresh_db(db)
    _eng(conn, "e1", privacy="internal")
    conn.commit()
    conn.close()

    ok = _client(db).get("/api/engram/e1")
    assert ok.status_code == 200
    assert ok.json()["engram"]["id"] == "e1"

    missing = _client(db).get("/api/engram/does-not-exist")
    assert missing.status_code == 404
