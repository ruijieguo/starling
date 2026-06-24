"""/api/converse — chat-with-memory turn (Phase 2c, three-phase C++ orchestration).

Uses FakeLLMAdapter as both chat + extraction adapter (chat role falls back to
extraction). The fake's default response is a statements JSON array, so generate
returns it as the reply AND the remember leg's extractor parses it into a
statement — exercising recall→inject→generate→remember end to end without HTTP.
"""
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


def _engine_with_fake(db, *, ok=True, body=_STUB_JSON, error=""):
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(body, ok, error)
    eng.llm = fake                 # extraction adapter; chat falls back to it
    return cfg, eng


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg, eng = _engine_with_fake(str(tmp_path / "conv.db"))
    return TestClient(create_app(cfg, engine=eng))


def test_converse_three_phase_happy(client):
    r = client.post("/api/converse", json={"message": "who owns auth?"})
    assert r.status_code == 200
    b = r.json()
    assert b["ok"] is True
    assert b["reply"]                              # generate produced a reply
    assert b["remember_ok"] is True                # exchange consolidated
    assert len(b["statement_ids"]) >= 1            # remember extracted a statement
    assert "context_pack" in b and "abstained" in b


def test_converse_consolidates_then_recallable(client):
    # The turn's exchange is remembered → after tick it is recallable.
    sid = client.post("/api/converse", json={"message": "who owns auth?"}).json()["statement_ids"]
    assert sid
    client.post("/api/tick", json={})
    hits = client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    assert any(h["predicate"] == "responsible_for" for h in hits)


def test_converse_generate_failure_preserves_no_reply_and_skips_remember(tmp_path, monkeypatch):
    # generate fails → ok=False, no reply, nothing consolidated (clean no-reply turn).
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg, eng = _engine_with_fake(str(tmp_path / "f.db"), ok=False, body="", error="boom")
    c = TestClient(create_app(cfg, engine=eng))
    b = c.post("/api/converse", json={"message": "hi"}).json()
    assert b["ok"] is False
    assert b["reply"] == ""
    assert b["error"] == "boom"
    assert b["statement_ids"] == []


def test_converse_remember_failure_preserves_reply(tmp_path, monkeypatch):
    # decision-A: generate succeeds (reply shown) but the extraction LLM fails.
    # The Extractor swallows the failure (FAILED, no throw), so remember_ok must be
    # derived honestly — reply preserved, remember_ok=False, observable reason.
    # Distinct chat (ok) vs extraction (fail) adapters isolate the remember leg.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = DashboardConfig(db_path=str(tmp_path / "rf.db"), token="")
    eng = DashboardEngine(cfg)
    chat = _core.FakeLLMAdapter()
    chat.set_default_response("Bob owns auth.", True, "")
    extract = _core.FakeLLMAdapter()
    extract.set_default_response("", False, "extract-boom")
    eng.llm = extract              # extraction adapter (fails)
    eng._core.chat_llm = chat      # distinct chat adapter (succeeds)
    c = TestClient(create_app(cfg, engine=eng))
    b = c.post("/api/converse", json={"message": "who owns auth?"}).json()
    assert b["ok"] is True                       # generate succeeded
    assert b["reply"] == "Bob owns auth."         # reply preserved, not dropped
    assert b["remember_ok"] is False             # extraction failed → honest signal
    assert b["remember_error"] == "extraction_failed"
    assert b["statement_ids"] == []


def test_converse_409_when_llm_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = DashboardConfig(db_path=str(tmp_path / "nollm.db"), token="")
    eng = DashboardEngine(cfg)            # no extraction adapter
    c = TestClient(create_app(cfg, engine=eng))
    r = c.post("/api/converse", json={"message": "hi"})
    assert r.status_code == 409 and r.json()["detail"] == "llm_not_configured"
