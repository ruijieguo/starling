"""T0b — /api/statements consolidation_state 过滤(支持逗号分隔多值 IN)。

镜像 test_dashboard_inspect.py 的 seed-then-TestClient 范式。播种 4 条不同
consolidation_state 的语句(其中 1 条属另一租户),断言:
  - 空串 → 不过滤,返回全部(本租户)。
  - 单值 → 精确匹配该态。
  - 多值(逗号分隔)→ IN 并集,顺序/空白容错。
  - 跨租户语句永不出现,即便其 consolidation_state 匹配过滤值。
  - 端点层(TestClient 走 HTTP query string)与 queries 层行为一致。
"""
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.dashboard import queries

_STMT_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, "
    "canonical_object_hash_version, modality, polarity, confidence, observed_at, "
    "salience, affect_json, activation, last_accessed, provenance, created_at, "
    "updated_at, consolidation_state"
)


def _stmt(conn, sid, tenant, state):
    conn.execute(
        f"INSERT INTO statements ({_STMT_COLS}) VALUES ({','.join('?' * 23)})",
        (sid, tenant, "self", "first_person", "cognizer", "Bob", "responsible_for",
         "str", "auth", f"h{sid}", "v1", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-10T10:00:00Z", "test", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", state),
    )


def _seed(db_path: str):
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r  # release the writer handle before raw seeding
    conn = sqlite3.connect(db_path)
    _stmt(conn, "s_vol", "default", "volatile")
    _stmt(conn, "s_rc", "default", "replaying_consolidating")
    _stmt(conn, "s_con", "default", "consolidated")
    _stmt(conn, "s_other_vol", "other", "volatile")  # other tenant — must never surface
    conn.commit()
    conn.close()


@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "dash.db")
    _seed(p)
    return p


@pytest.fixture
def client(db):
    cfg = DashboardConfig(db_path=db, token="")
    return TestClient(create_app(cfg))


# ── queries 层 ────────────────────────────────────────────────────────────

def test_query_empty_filter_returns_all_tenant_rows(db):
    out = queries.statements(db, "default", consolidation_state="")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_vol", "s_rc", "s_con"}


def test_query_single_value_exact_match(db):
    out = queries.statements(db, "default", consolidation_state="volatile")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_vol"}


def test_query_multi_value_in_union(db):
    out = queries.statements(
        db, "default",
        consolidation_state="volatile,replaying_consolidating",
    )
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_vol", "s_rc"}


def test_query_multi_value_tolerates_whitespace_and_blanks(db):
    out = queries.statements(
        db, "default",
        consolidation_state=" volatile , ,replaying_consolidating,",
    )
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_vol", "s_rc"}


def test_query_cross_tenant_never_leaks(db):
    # "other" tenant has a volatile row too — filtering "default" for volatile
    # must not surface it.
    out = queries.statements(db, "default", consolidation_state="volatile")
    ids = {r["id"] for r in out["rows"]}
    assert "s_other_vol" not in ids

    out_other = queries.statements(db, "other", consolidation_state="volatile")
    ids_other = {r["id"] for r in out_other["rows"]}
    assert ids_other == {"s_other_vol"}


# ── 端点层(HTTP query string)──────────────────────────────────────────

def test_endpoint_no_param_returns_all(client):
    r = client.get("/api/statements")
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_vol", "s_rc", "s_con"}


def test_endpoint_single_value(client):
    r = client.get("/api/statements", params={"consolidation_state": "consolidated"})
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_con"}


def test_endpoint_multi_value_parses_correctly(client):
    r = client.get(
        "/api/statements",
        params={"consolidation_state": "volatile,consolidated"},
    )
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_vol", "s_con"}


def test_endpoint_multi_value_all_three_hippocampal_states(client):
    # 海马三态一次筛(nav 深链场景):VOLATILE + 两个 REPLAYING_* 态。
    r = client.get(
        "/api/statements",
        params={
            "consolidation_state": (
                "volatile,replaying_consolidating,replaying_reconsolidating"
            )
        },
    )
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    # replaying_reconsolidating not seeded, so union is just vol+rc.
    assert ids == {"s_vol", "s_rc"}
