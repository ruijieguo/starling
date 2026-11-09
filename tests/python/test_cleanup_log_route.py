"""GET /api/worlds/cleanup_log（记忆服务第 6 期 Task 6.2，spec §9、§14）：看板「最近清理」表的数据。

记录由 C++ 写、由 C++ 读（world_cleanup_log，limit 1–500，越界 invalid_world_query），路由只转发并套统一错误体。
"""
import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app

NOW = "2026-11-20T00:00:00Z"
STALE = "2026-11-01T00:00:00Z"


def _client(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "dashboard.db"), token="", tick_interval_s=0,
                          source_lane_enabled=False, ingest_spool_path=str(tmp_path / "spool"))
    app = create_app(cfg)
    return TestClient(app), app


def _rollout(pool, name: str, created_at: str) -> None:
    try:
        pool.record("deploy")
    except Exception:  # noqa: BLE001 — 部署世界第一次用时建
        pool.create_world("deploy", "")
    saved = pool._clock
    pool._clock = lambda: created_at
    try:
        pool.fork_world("deploy", name, reclaimable=True, retention_group="run1")
    finally:
        pool._clock = saved


def test_cleanup_log_shape_and_order(tmp_path):
    client, app = _client(tmp_path)
    pool = app.state.pool
    try:
        _rollout(pool, "old-1", STALE)
        _rollout(pool, "old-2", STALE)
        with pool.lease("old-2"):
            pass
        pool.cleanup_round(now=NOW)
        resp = client.get("/api/worlds/cleanup_log")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == {"entries"}
        entries = body["entries"]
        assert [(e["world"], e["action"], e["reason"]) for e in entries] == [
            ("old-2", "skipped", "open"), ("old-1", "removed", "over_age")]
        for entry in entries:
            assert set(entry) == {"id", "at", "world", "group", "action", "reason", "detail"}
            assert entry["at"] == NOW and entry["group"] == "run1"
        assert entries[0]["id"] > entries[1]["id"]                    # 最新在前
        one = client.get("/api/worlds/cleanup_log?limit=1").json()["entries"]
        assert [e["world"] for e in one] == ["old-2"]
    finally:
        pool.close_all()


def test_cleanup_log_defaults_to_50(tmp_path, monkeypatch):
    client, app = _client(tmp_path)
    seen = []
    real = _core.world_cleanup_log

    def spy(reg, limit):
        seen.append(limit)
        return real(reg, limit)
    monkeypatch.setattr(_core, "world_cleanup_log", spy)
    try:
        assert client.get("/api/worlds/cleanup_log").json() == {"entries": []}
        assert seen == [50]
    finally:
        app.state.pool.close_all()


@pytest.mark.parametrize("limit", [0, 501, -3])
def test_cleanup_log_limit_out_of_range_uses_the_catalog_error_body(tmp_path, limit):
    client, app = _client(tmp_path)
    try:
        resp = client.get(f"/api/worlds/cleanup_log?limit={limit}")
        assert resp.status_code == 400
        assert resp.json() == {"code": "invalid_world_query", "transient": False,
                               "detail": "invalid_world_query"}
    finally:
        app.state.pool.close_all()


def test_cleanup_log_without_a_registry_is_empty():
    app = create_app(DashboardConfig(db_path=":memory:", token="", tick_interval_s=0))
    try:
        assert app.state.pool.registry is None
        resp = TestClient(app).get("/api/worlds/cleanup_log")
        assert resp.status_code == 200
        assert resp.json() == {"entries": []}
    finally:
        app.state.pool.close_all()


def test_cleanup_log_route_is_not_shadowed_by_world_detail(tmp_path):
    """/worlds/cleanup_log 注册在 /worlds/{name} 之前：不会被当成一个叫 cleanup_log 的世界去查（world_not_found）。"""
    client, app = _client(tmp_path)
    try:
        resp = client.get("/api/worlds/cleanup_log")
        assert resp.status_code == 200 and "entries" in resp.json()
    finally:
        app.state.pool.close_all()


def test_cleanup_log_needs_the_token(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "dashboard.db"), token="secret", tick_interval_s=0,
                          source_lane_enabled=False, ingest_spool_path=str(tmp_path / "spool"))
    app = create_app(cfg)
    try:
        client = TestClient(app)
        assert client.get("/api/worlds/cleanup_log").status_code == 401
        ok = client.get("/api/worlds/cleanup_log", headers={"Authorization": "Bearer secret"})
        assert ok.status_code == 200
    finally:
        app.state.pool.close_all()
