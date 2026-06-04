from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app


def _client(token: str) -> TestClient:
    cfg = DashboardConfig(db_path=":memory:", token=token)
    return TestClient(create_app(cfg))


def test_health_open_without_token():
    c = _client("secret")
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_protected_requires_token():
    c = _client("secret")
    assert c.get("/api/ping").status_code == 401
    assert c.get("/api/ping", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = c.get("/api/ping", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200 and ok.json()["pong"] is True


def test_empty_token_opens_gate():
    c = _client("")
    assert c.get("/api/ping").status_code == 200
