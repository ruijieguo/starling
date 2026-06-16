import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _engine_with_llm(db):
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_STUB_JSON, True, "")
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
    assert t.status_code == 200 and set(t.json()) == {
        "embedded", "fired", "broken", "auto_withdrawn",
        "replay_sampled", "consolidated", "ttl_archived",
        "projected", "dispatched"}


def test_recall_shape(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    r = client.post("/api/recall", json={"query": "auth", "k": 5})
    assert r.status_code == 200 and isinstance(r.json()["results"], list)


def test_recall_with_intent_goes_through_planner(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    client.post("/api/tick", json={})
    r = client.post("/api/recall", json={
        "query": "auth", "intent": "FACT_LOOKUP", "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert {"results", "context_pack", "abstained", "plan_steps"} <= set(body)
    assert [s["step"] for s in body["plan_steps"]][:3] == ["parse", "mask", "plan"]


def test_remember_409_when_llm_unconfigured(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "nollm.db"), token="")
    eng = DashboardEngine(cfg)            # llm unset
    c = TestClient(create_app(cfg, engine=eng))
    r = c.post("/api/remember", json={"text": "x"})
    assert r.status_code == 409 and r.json()["detail"] == "llm_not_configured"


def test_working_set_renders(client):
    r = client.get("/api/working_set", params={"interlocutor": "Alice"})
    assert r.status_code == 200 and "render" in r.json()


def test_forget_removes_from_recall(client):
    rid = client.post("/api/remember", json={"text": "Bob owns auth"}).json()
    sid = rid["statement_ids"][0]
    client.post("/api/tick", json={})
    assert client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    f = client.post("/api/forget", json={"ids": [sid]})
    assert f.status_code == 200 and f.json()["forgotten"] == 1
    hits = client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    assert all(h["id"] != sid for h in hits)   # forgotten id 不再出现在 recall


def test_forget_idempotent(client):
    f = client.post("/api/forget", json={"ids": ["nope"]})
    assert f.status_code == 200 and f.json()["forgotten"] == 0


def test_recall_includes_statement_id(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    client.post("/api/tick", json={})
    hits = client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    assert hits and all("id" in h and h["id"] for h in hits)


def test_recall_holder_override(client):
    # Statement written under a non-default holder ("agent"); dashboard agent="self".
    client.post("/api/remember", json={"text": "Bob owns auth", "holder": "agent"})
    client.post("/api/tick", json={})
    # Default recall holder (dashboard agent "self") must NOT see the agent-held row.
    miss = client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    assert not any(h["subject"] == "Bob" for h in miss)
    # Explicit holder="agent" round-trips and recalls it (P3.b2 plugin holder).
    hit = client.post(
        "/api/recall", json={"query": "auth", "k": 5, "holder": "agent"}).json()["results"]
    assert any(h["subject"] == "Bob" for h in hit)


def test_recall_perspective_case_insensitive(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    client.post("/api/tick", json={})
    # Uppercase perspective must still match the lowercase-stored value.
    hits = client.post(
        "/api/recall", json={"query": "auth", "k": 5, "perspective": "FIRST_PERSON"}
    ).json()["results"]
    assert any(h["subject"] == "Bob" for h in hits)
