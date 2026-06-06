import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine

_STUB_XML = (
    "<statements><statement><holder>self</holder>"
    "<holder_perspective>FIRST_PERSON</holder_perspective>"
    "<subject>Bob</subject><predicate>responsible_for</predicate>"
    "<object>auth</object><modality>BELIEVES</modality>"
    "<polarity>POS</polarity><nesting_depth>0</nesting_depth></statement></statements>"
)


def _engine_with_llm(db):
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_STUB_XML, True, "")
    eng.llm = fake
    return cfg, eng


@pytest.fixture
def client(tmp_path):
    cfg, eng = _engine_with_llm(str(tmp_path / "cmd.db"))
    return TestClient(create_app(cfg, engine=eng))


def test_remember_then_tick(client):
    r = client.post("/api/remember", json={"text": "Bob owns auth"})
    assert r.status_code == 200 and r.json()["outcome"] in ("accepted", "idempotent")
    t = client.post("/api/tick", json={})
    assert t.status_code == 200 and set(t.json()) == {"embedded", "fired", "broken", "auto_withdrawn"}


def test_recall_shape(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    r = client.post("/api/recall", json={"query": "auth", "k": 5})
    assert r.status_code == 200 and isinstance(r.json()["results"], list)


def test_remember_409_when_llm_unconfigured(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "nollm.db"), token="")
    eng = DashboardEngine(cfg)            # llm unset
    c = TestClient(create_app(cfg, engine=eng))
    r = c.post("/api/remember", json={"text": "x"})
    assert r.status_code == 409 and r.json()["detail"] == "llm_not_configured"


def test_working_set_renders(client):
    r = client.get("/api/working_set", params={"interlocutor": "Alice"})
    assert r.status_code == 200 and "render" in r.json()
