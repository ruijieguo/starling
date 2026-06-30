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

_COMMITS_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"self","predicate":"owes","object":"send the report",'
    '"modality":"COMMITS","polarity":"POS","nesting_depth":0}]'
)


def test_commits_statement_auto_materializes_commitment(tmp_path):
    """REGRESSION: a remembered commits-modality statement (the pipeline stores the
    canonical lowercase 'commits') must auto-materialize an ACTIVE commitment when
    the PolicyEngine runs on tick. The engine compared modality == "COMMITS" (upper)
    while statements store 'commits' (lower), so auto-materialization silently never
    fired — and the existing C++ tests seeded uppercase 'COMMITS', masking it."""
    import sqlite3
    db = str(tmp_path / "commit.db")
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_COMMITS_JSON, True, "")
    eng.llm = fake
    client = TestClient(create_app(cfg, engine=eng))

    assert client.post("/api/remember", json={"text": "I owe sending the report"}).status_code == 200
    for _ in range(10):
        if client.post("/api/tick", json={}).json()["dispatched"] == 0:
            break
    conn = sqlite3.connect(db)
    active = conn.execute("SELECT COUNT(*) FROM commitments WHERE state='ACTIVE'").fetchone()[0]
    conn.close()
    assert active >= 1, "commits statement did not auto-materialize a commitment"


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
        "projected", "dispatched", "stage_timings_ms"}


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


def test_recall_intent_receipt_additive_regression(client):
    """REGRESSION (Phase 0): plan_query gained a `receipt` block. The original
    six keys the interact page depends on MUST stay; the new attribution fields
    are purely additive; runtime_health stays hidden (honesty: never populated)."""
    client.post("/api/remember", json={"text": "Bob owns auth"})
    client.post("/api/tick", json={})
    body = client.post("/api/recall", json={
        "query": "auth", "intent": "FACT_LOOKUP", "k": 5}).json()
    # 1) the six legacy keys remain (interact page contract)
    assert {"results", "context_pack", "abstained", "abstention_reason",
            "plan_steps", "scopes_searched"} <= set(body)
    # 2) the new receipt block is present with the previously-dropped fields
    rc = body["receipt"]
    assert {"filters_applied", "candidate_counts", "score_breakdown",
            "frontier_masked_count", "evidence_erased_count", "sufficiency_status",
            "degraded_paths", "trace_id", "query_id"} <= set(rc)
    assert isinstance(rc["filters_applied"], list)
    assert {"fetched", "returned", "dropped_by_review"} <= set(rc["candidate_counts"])
    # 3) runtime_health is deliberately NOT surfaced (live-vs-roadmap honesty)
    assert "runtime_health" not in rc and "runtime_health" not in body


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
