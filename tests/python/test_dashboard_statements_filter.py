"""T0b — /api/statements consolidation_state 过滤(支持逗号分隔多值 IN)。
T0d-1 — /api/statements modality 过滤(同款范式,新皮层 Semantic/Norms 子区)。

镜像 test_dashboard_inspect.py 的 seed-then-TestClient 范式。播种 4 条不同
consolidation_state 的语句(其中 1 条属另一租户),断言:
  - 空串 → 不过滤,返回全部(本租户)。
  - 单值 → 精确匹配该态。
  - 多值(逗号分隔)→ IN 并集,顺序/空白容错。
  - 跨租户语句永不出现,即便其 consolidation_state 匹配过滤值。
  - 端点层(TestClient 走 HTTP query string)与 queries 层行为一致。

modality 测试额外播种 4 条覆盖 believes/knows/norm_ought/norm_forbid(其中 1 条
属另一租户),断言同款单值/多值 IN/空不过滤/跨租户不泄漏/端点层行为。
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


# ── T0d-1: modality 过滤(Semantic/Norms 子区)────────────────────────────

def _stmt_modality(conn, sid, tenant, modality):
    conn.execute(
        f"INSERT INTO statements ({_STMT_COLS}) VALUES ({','.join('?' * 23)})",
        (sid, tenant, "self", "first_person", "cognizer", "Bob", "responsible_for",
         "str", "auth", f"h{sid}", "v1", modality, "POS", 0.9, "2026-04-10T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-10T10:00:00Z", "test", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", "consolidated"),
    )


def _seed_modality(db_path: str):
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r
    conn = sqlite3.connect(db_path)
    _stmt_modality(conn, "s_believes", "default", "believes")
    _stmt_modality(conn, "s_knows", "default", "knows")
    _stmt_modality(conn, "s_norm_ought", "default", "norm_ought")
    _stmt_modality(conn, "s_other_believes", "other", "believes")  # other tenant — must never surface
    conn.commit()
    conn.close()


@pytest.fixture
def db_modality(tmp_path):
    p = str(tmp_path / "dash_modality.db")
    _seed_modality(p)
    return p


@pytest.fixture
def client_modality(db_modality):
    cfg = DashboardConfig(db_path=db_modality, token="")
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


# ── T0d-1: modality 过滤 — queries 层 ────────────────────────────────────

def test_query_modality_empty_filter_returns_all_tenant_rows(db_modality):
    out = queries.statements(db_modality, "default", modality="")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_believes", "s_knows", "s_norm_ought"}


def test_query_modality_single_value_exact_match(db_modality):
    out = queries.statements(db_modality, "default", modality="believes")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_believes"}


def test_query_modality_multi_value_in_union(db_modality):
    # Semantic 子区深链场景:believes + knows 一次筛。
    out = queries.statements(db_modality, "default", modality="believes,knows")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_believes", "s_knows"}


def test_query_modality_multi_value_tolerates_whitespace_and_blanks(db_modality):
    out = queries.statements(
        db_modality, "default",
        modality=" believes , ,knows,",
    )
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_believes", "s_knows"}


def test_query_modality_cross_tenant_never_leaks(db_modality):
    # "other" tenant also has a believes row — filtering "default" for believes
    # must not surface it.
    out = queries.statements(db_modality, "default", modality="believes")
    ids = {r["id"] for r in out["rows"]}
    assert "s_other_believes" not in ids

    out_other = queries.statements(db_modality, "other", modality="believes")
    ids_other = {r["id"] for r in out_other["rows"]}
    assert ids_other == {"s_other_believes"}


# ── T0d-1: modality 过滤 — 端点层(HTTP query string)───────────────────────

def test_endpoint_modality_no_param_returns_all(client_modality):
    r = client_modality.get("/api/statements")
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_believes", "s_knows", "s_norm_ought"}


def test_endpoint_modality_single_value(client_modality):
    r = client_modality.get("/api/statements", params={"modality": "norm_ought"})
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_norm_ought"}


def test_endpoint_modality_multi_value_semantic_subregion(client_modality):
    # Semantic 子区深链:believes + knows。
    r = client_modality.get("/api/statements", params={"modality": "believes,knows"})
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_believes", "s_knows"}


def test_endpoint_modality_multi_value_norms_subregion(client_modality):
    # Norms 子区深链:norm_ought + norm_forbid(norm_forbid 未播种,验证并集不误报)。
    r = client_modality.get(
        "/api/statements", params={"modality": "norm_ought,norm_forbid"}
    )
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_norm_ought"}


# ── T0e ②: 信念阶层过滤(belief_order → nesting_depth 比较)+ ① subject_kind ──

def _stmt_belief(conn, sid, tenant, nesting_depth, subject_kind="cognizer"):
    cols = _STMT_COLS + ", nesting_depth"
    conn.execute(
        f"INSERT INTO statements ({cols}) VALUES ({','.join('?' * 24)})",
        (sid, tenant, "self", "first_person", subject_kind, "Bob", "responsible_for",
         "str", "auth", f"h{sid}", "v1", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-10T10:00:00Z", "test", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", "consolidated", nesting_depth),
    )


def _seed_belief(db_path: str):
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r
    conn = sqlite3.connect(db_path)
    _stmt_belief(conn, "s_first", "default", 0, subject_kind="cognizer")
    _stmt_belief(conn, "s_higher1", "default", 1, subject_kind="cognizer")
    _stmt_belief(conn, "s_higher2", "default", 2, subject_kind="entity")
    _stmt_belief(conn, "s_other_first", "other", 0, subject_kind="cognizer")  # other tenant
    conn.commit()
    conn.close()


@pytest.fixture
def db_belief(tmp_path):
    p = str(tmp_path / "dash_belief.db")
    _seed_belief(p)
    return p


@pytest.fixture
def client_belief(db_belief):
    cfg = DashboardConfig(db_path=db_belief, token="")
    return TestClient(create_app(cfg))


# ── queries 层 ────────────────────────────────────────────────────────────

def test_query_belief_order_empty_returns_all(db_belief):
    out = queries.statements(db_belief, "default", belief_order="")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_first", "s_higher1", "s_higher2"}


def test_query_belief_order_first_is_depth_zero(db_belief):
    out = queries.statements(db_belief, "default", belief_order="first")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_first"}


def test_query_belief_order_higher_is_depth_gte_one(db_belief):
    out = queries.statements(db_belief, "default", belief_order="higher")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_higher1", "s_higher2"}


def test_query_belief_order_cross_tenant_never_leaks(db_belief):
    out = queries.statements(db_belief, "default", belief_order="first")
    ids = {r["id"] for r in out["rows"]}
    assert "s_other_first" not in ids

    out_other = queries.statements(db_belief, "other", belief_order="first")
    ids_other = {r["id"] for r in out_other["rows"]}
    assert ids_other == {"s_other_first"}


def test_query_subject_kind_exact_match(db_belief):
    out = queries.statements(db_belief, "default", subject_kind="entity")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_higher2"}


def test_query_subject_kind_and_belief_order_combine(db_belief):
    out = queries.statements(db_belief, "default", belief_order="higher", subject_kind="cognizer")
    ids = {r["id"] for r in out["rows"]}
    assert ids == {"s_higher1"}


# ── 端点层(HTTP query string)──────────────────────────────────────────

def test_endpoint_belief_order_first(client_belief):
    r = client_belief.get("/api/statements", params={"belief_order": "first"})
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_first"}


def test_endpoint_belief_order_higher(client_belief):
    r = client_belief.get("/api/statements", params={"belief_order": "higher"})
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_higher1", "s_higher2"}


def test_endpoint_subject_kind(client_belief):
    r = client_belief.get("/api/statements", params={"subject_kind": "entity"})
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["rows"]}
    assert ids == {"s_higher2"}
