"""/ws/converse — #37 streaming converse (per-turn WS token stream).

Mirrors test_dashboard_converse's FakeLLMAdapter setup. The fake does NOT override
generate_stream, so the base default emits the whole reply as ONE delta — a happy
turn therefore yields exactly one {type:token} frame then {type:done}. Real SSE
adapters (follow-up) emit many token frames; the wire protocol is identical, so
these tests pin the spine end to end (binding GIL sink + converse threading +
sync→async bridge) regardless of how many deltas a real adapter produces.
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


def _client_with_fake(db, *, ok=True, body=_STUB_JSON, error=""):
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(body, ok, error)
    eng.llm = fake                 # extraction adapter; chat falls back to it
    return TestClient(create_app(cfg, engine=eng))


def _drain(ws):
    """Collect token deltas until the terminal frame; return (deltas, terminal)."""
    deltas = []
    while True:
        msg = ws.receive_json()
        if msg["type"] == "token":
            deltas.append(msg["delta"])
        else:
            return deltas, msg


def test_stream_happy_emits_tokens_then_done(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = _client_with_fake(str(tmp_path / "s.db"))
    with client.websocket_connect("/ws/converse") as ws:
        ws.send_json({"message": "who owns auth?"})
        deltas, done = _drain(ws)
    assert done["type"] == "done"
    assert done["ok"] is True
    assert done["reply"]                          # full reply present
    assert len(deltas) >= 1                        # base default: 1 delta for the fake
    assert "".join(deltas) == done["reply"]        # streamed deltas reconstruct the reply
    assert done["remember_ok"] is True             # the exchange consolidated
    assert len(done["statement_ids"]) >= 1
    assert {"gen_total_tokens", "gen_prompt_tokens"} <= done.keys()  # cost carried through


def test_stream_empty_message_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = _client_with_fake(str(tmp_path / "e.db"))
    with client.websocket_connect("/ws/converse") as ws:
        ws.send_json({"message": ""})
        msg = ws.receive_json()
    assert msg == {"type": "error", "error": "empty_message"}


def test_stream_error_when_llm_unconfigured(tmp_path, monkeypatch):
    # No extraction adapter → converse_stream raises LLMNotConfigured in the
    # worker; the endpoint surfaces it as an error frame (not a crash).
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = DashboardConfig(db_path=str(tmp_path / "n.db"), token="")
    eng = DashboardEngine(cfg)
    client = TestClient(create_app(cfg, engine=eng))
    with client.websocket_connect("/ws/converse") as ws:
        ws.send_json({"message": "hi"})
        deltas, term = _drain(ws)
    assert deltas == []
    assert term == {"type": "error", "error": "llm_not_configured"}


def test_stream_generate_failure_is_done_with_no_reply(tmp_path, monkeypatch):
    # generate fails → converse returns ok=False (a clean no-reply turn, NOT an
    # exception). So no token frame (base default emits only when ok) then a
    # done frame with ok=False — failure of the model ≠ a transport error.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = _client_with_fake(str(tmp_path / "gf.db"), ok=False, body="", error="boom")
    with client.websocket_connect("/ws/converse") as ws:
        ws.send_json({"message": "hi"})
        deltas, done = _drain(ws)
    assert deltas == []
    assert done["type"] == "done"
    assert done["ok"] is False and done["error"] == "boom"
    assert done["statement_ids"] == []
