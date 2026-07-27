"""PR2 Task 10 — /cognizers 归档过滤:archived_at 非空的认知体不出现在图谱。

镜像 test_dashboard_statements_filter.py 的 seed-then-query 范式。播种 4 个认知体:
  - 2 个 active(archived_at NULL)
  - 1 个 archived(archived_at 有时戳)—— 存量重分类判为 entity 而归档
  - 1 个属另一租户(archived_at NULL)—— 跨租户永不泄漏

断言 queries.cognizers() 的 nodes:
  - 只返回本租户 active 行(归档行不出现)。
  - 跨租户行不出现。
  - 端点层(TestClient 走 HTTP)与 queries 层一致。
"""
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.dashboard import queries

_COG_COLS = (
    "id, tenant_id, kind, canonical_name, canonical_name_normalized, "
    "aliases_json, aliases_normalized_json, external_id, trust_priors_json, "
    "permissions_json, created_at, last_seen_at, archived_at"
)


def _cog(conn, cid, tenant, name, archived_at):
    conn.execute(
        f"INSERT INTO cognizers ({_COG_COLS}) VALUES ({','.join('?' * 13)})",
        (cid, tenant, "human", name, name.lower(), "[]", "[]", cid, "{}", "{}",
         "2026-04-10T10:00:00Z", "2026-04-10T10:00:00Z", archived_at),
    )


_REL_COLS = (
    "id, tenant_id, a_id, b_id, fiske_weights_json, affinity, trust_json, "
    "power_asymmetry, created_at, updated_at"
)


def _rel(conn, rid, tenant, a_id, b_id, fiske_json):
    conn.execute(
        f"INSERT INTO cognizer_relations ({_REL_COLS}) VALUES ({','.join('?' * 10)})",
        (rid, tenant, a_id, b_id, fiske_json, 0.7, "{}", 0.2,
         "2026-04-10T10:00:00Z", "2026-04-10T10:00:00Z"),
    )


def _seed(db_path: str):
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r  # release the writer handle before raw seeding
    conn = sqlite3.connect(db_path)
    _cog(conn, "cog_active1", "default", "Alice", None)
    _cog(conn, "cog_active2", "default", "Bob", None)
    _cog(conn, "cog_archived", "default", "H800 memory", "2026-07-23T00:00:00Z")
    _cog(conn, "cog_other", "other", "Carol", None)  # other tenant — must never surface
    # 一条 Alice→Bob 的 authority 边(reports_to 折叠成 fiske)——测有向渲染要的字段。
    _rel(conn, "rel_1", "default", "cog_active1", "cog_active2",
         '{"authority":0.7,"communal":0.1,"equality":0.1,"market":0.1}')
    conn.commit()
    conn.close()


@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "dash.db")
    _seed(p)
    return p


def test_queries_cognizers_excludes_archived(db):
    result = queries.cognizers(db, "default")
    names = {n["canonical_name"] for n in result["nodes"]}
    assert names == {"Alice", "Bob"}  # archived + cross-tenant excluded
    ids = {n["id"] for n in result["nodes"]}
    assert "cog_archived" not in ids
    assert "cog_other" not in ids


def test_queries_cognizers_archived_row_hidden_even_though_present(db):
    # The archived row IS in the table (reversible), just filtered from the graph.
    conn = sqlite3.connect(db)
    total = conn.execute(
        "SELECT COUNT(*) FROM cognizers WHERE tenant_id='default'").fetchone()[0]
    archived = conn.execute(
        "SELECT COUNT(*) FROM cognizers WHERE tenant_id='default' "
        "AND archived_at IS NOT NULL").fetchone()[0]
    conn.close()
    assert total == 3   # 2 active + 1 archived still on disk
    assert archived == 1


def test_endpoint_cognizers_excludes_archived(db):
    app = create_app(DashboardConfig(db_path=db, tenant="default"))
    client = TestClient(app)
    resp = client.get("/api/cognizers")
    assert resp.status_code == 200
    names = {n["canonical_name"] for n in resp.json()["nodes"]}
    assert names == {"Alice", "Bob"}


def test_queries_cognizers_relations_carry_direction_and_fiske(db):
    # 有向渲染需要:relations 带方向(a_id→b_id 有序)+ fiske_weights_json(边类型)。
    result = queries.cognizers(db, "default")
    rels = result["relations"]
    assert len(rels) == 1
    r = rels[0]
    assert r["a_id"] == "cog_active1"        # 方向:Alice→Bob(有序,不可交换)
    assert r["b_id"] == "cog_active2"
    assert "fiske_weights_json" in r          # 边类型信息(前端 argmax 主导模式)
    assert '"authority":0.7' in r["fiske_weights_json"]
