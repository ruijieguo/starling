"""P2.l/2a: multi-provider config — provider factory dispatch, the named-provider
registry, and the /api/config/test connectivity probe (no real network; adapters
monkeypatched or constructed without HTTP)."""
import json

import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine, _build_chat_adapter
import starling.dashboard.engine as engmod


def test_build_chat_adapter_dispatches_by_provider():
    # Constructing an adapter does no HTTP (key read from env-swap at build).
    a = _build_chat_adapter({"provider": "anthropic", "api_key": "k", "model": "claude-x"})
    assert isinstance(a, _core.AnthropicAdapter)
    o = _build_chat_adapter({"provider": "openai", "api_key": "k", "model": "gpt-x"})
    assert isinstance(o, _core.OpenAIAdapter)
    # A provider dict without a provider key defaults to OpenAI-compatible.
    legacy = _build_chat_adapter({"api_key": "k"})
    assert isinstance(legacy, _core.OpenAIAdapter)


def test_real_adapters_expose_extract():
    # Regression: /api/config/test calls .extract() from Python, so the real
    # adapters (not only FakeLLMAdapter) must expose it. Constructing does no HTTP.
    o = _build_chat_adapter({"provider": "openai", "api_key": "k"})
    a = _build_chat_adapter({"provider": "anthropic", "api_key": "k"})
    assert callable(getattr(o, "extract", None))
    assert callable(getattr(a, "extract", None))


def test_registry_roundtrips(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfgfile = tmp_path / "starling.json"
    cfg = DashboardConfig(db_path=str(tmp_path / "c.db"), token="t", config_path=str(cfgfile))
    cfg.providers["claude"] = {"provider": "anthropic", "model": "claude-x",
                               "base_url": "", "api_key": "sk-x"}
    cfg.roles["extraction"] = "claude"
    cfg.save()
    loaded = DashboardConfig.load(str(cfgfile))
    ex = loaded.extraction()
    assert ex["provider"] == "anthropic" and ex["api_key"] == "sk-x"
    assert loaded.roles["extraction"] == "claude"


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfgfile = tmp_path / "starling.json"
    cfg = DashboardConfig(db_path=str(tmp_path / "c.db"), token="", config_path=str(cfgfile))
    eng = DashboardEngine(cfg)
    client = TestClient(create_app(cfg, engine=eng))
    return cfg, eng, client, cfgfile


def test_config_test_llm_probes_without_persisting(ctx, monkeypatch):
    cfg, eng, client, cfgfile = ctx
    fake = _core.FakeLLMAdapter()
    fake.set_default_response("[]", True, "")  # raw_xml, ok, error
    monkeypatch.setattr(engmod, "_build_chat_adapter", lambda c: fake)
    r = client.post("/api/config/test",
                    json={"kind": "llm", "provider": "openai", "api_key": "sk-secret-xyz", "model": "m"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and "latency_ms" in body
    assert not cfgfile.exists()                       # never persisted
    assert "sk-secret-xyz" not in json.dumps(body)    # never leaks the key


def test_config_test_embedder_uses_real_embed_binding(ctx, monkeypatch):
    cfg, eng, client, _ = ctx
    monkeypatch.setattr(engmod, "_build_embed_adapter", lambda c: _core.StubEmbeddingAdapter(8))
    r = client.post("/api/config/test", json={"kind": "embedder", "api_key": "sk-x"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["detail"] == "dim=8"


def test_config_test_no_key_is_failure(ctx):
    _, _, client, _ = ctx
    r = client.post("/api/config/test", json={"kind": "llm", "provider": "openai"})
    assert r.status_code == 200 and r.json()["ok"] is False


def test_config_test_never_sends_stored_key_to_overridden_base_url(ctx, monkeypatch):
    # SECURITY: a stored provider's api_key may only probe its own stored base_url.
    # Overriding base_url without a fresh key is refused; a fresh caller key may
    # probe a caller URL (the caller's own key, not the stored secret).
    cfg, eng, client, _ = ctx
    cfg.providers["stored"] = {"provider": "openai", "model": "m",
                               "base_url": "https://api.openai.com/v1", "api_key": "sk-stored-secret"}
    built = {}

    def fake_build(c):
        built["base_url"] = c.get("base_url")
        built["api_key"] = c.get("api_key")
        f = _core.FakeLLMAdapter()
        f.set_default_response("[]", True, "")
        return f

    monkeypatch.setattr(engmod, "_build_chat_adapter", fake_build)

    # 1. override base_url, no fresh key → refused; builder never invoked → secret never left.
    r = client.post("/api/config/test",
                    json={"kind": "llm", "name": "stored", "base_url": "https://evil.example"})
    assert r.json()["ok"] is False
    assert built == {}

    # 2. probe the STORED endpoint with the stored key → allowed.
    r2 = client.post("/api/config/test",
                     json={"kind": "llm", "name": "stored", "base_url": "https://api.openai.com/v1"})
    assert r2.json()["ok"] is True
    assert built["api_key"] == "sk-stored-secret" and built["base_url"] == "https://api.openai.com/v1"

    # 3. a fresh caller key may go to a caller URL — it's the caller's own key.
    built.clear()
    r3 = client.post("/api/config/test",
                     json={"kind": "llm", "base_url": "https://my.proxy", "api_key": "sk-mine"})
    assert r3.json()["ok"] is True
    assert built["api_key"] == "sk-mine"
