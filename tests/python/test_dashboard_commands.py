from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.memory import Memory, make_stub_llm

_STUB_XML = (
    "<statements><statement><holder>self</holder>"
    "<holder_perspective>FIRST_PERSON</holder_perspective>"
    "<subject>Bob</subject><predicate>responsible_for</predicate>"
    "<object>auth</object><modality>BELIEVES</modality>"
    "<polarity>POS</polarity><nesting_depth>0</nesting_depth></statement></statements>"
)


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "cmd.db")
    mem = Memory.open(db, llm=make_stub_llm(default_xml=_STUB_XML))
    cfg = DashboardConfig(db_path=db, token="")
    return TestClient(create_app(cfg, memory=mem))


def test_remember_then_tick(client):
    r = client.post("/api/remember", json={"text": "Bob owns auth"})
    assert r.status_code == 200
    assert r.json()["outcome"] in ("accepted", "idempotent")
    t = client.post("/api/tick", json={"now": "2026-06-01T10:00:00Z"})
    assert t.status_code == 200
    assert set(t.json()) == {"embedded", "fired", "broken", "auto_withdrawn"}


def test_working_set_renders(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    r = client.get("/api/working_set", params={"interlocutor": "Alice"})
    assert r.status_code == 200
    assert "render" in r.json() and "blocks" in r.json()
