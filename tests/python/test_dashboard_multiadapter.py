"""P2.l: multi-provider config — provider factory dispatch, config v2, and the
/api/config/test connectivity probe (no real network; adapters monkeypatched or
constructed without HTTP)."""
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
    # Backward-compat: a legacy config without a provider key defaults to OpenAI.
    legacy = _build_chat_adapter({"api_key": "k"})
    assert isinstance(legacy, _core.OpenAIAdapter)


def test_real_adapters_expose_extract():
    # Regression: /api/config/test calls .extract() from Python, so the real
    # adapters (not only FakeLLMAdapter) must expose it. Constructing does no HTTP.
    o = _build_chat_adapter({"provider": "openai", "api_key": "k"})
    a = _build_chat_adapter({"provider": "anthropic", "api_key": "k"})
    assert callable(getattr(o, "extract", None))
    assert callable(getattr(a, "extract", None))


def test_config_v2_has_provider_and_roundtrips(tmp_path):
    cfgfile = tmp_path / "starling.json"
    cfg = DashboardConfig(db_path=str(tmp_path / "c.db"), token="t", config_path=str(cfgfile))
    assert cfg.llm["provider"] == "openai"
    assert cfg.embedder["provider"] == "openai"
    cfg.llm["provider"] = "anthropic"
    cfg.llm["api_key"] = "sk-x"  # set so the OPENAI_* env-overlay does not reseed llm
    cfg.save()
    loaded = DashboardConfig.load(str(cfgfile))
    assert loaded.llm["provider"] == "anthropic"
    assert loaded.llm["api_key"] == "sk-x"


@pytest.fixture
def ctx(tmp_path):
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
    # never persisted, never leaks the key
    assert not cfgfile.exists()
    assert "sk-secret-xyz" not in json.dumps(body)


def test_config_test_embedder_uses_real_embed_binding(ctx, monkeypatch):
    cfg, eng, client, _ = ctx
    # StubEmbeddingAdapter.embed (via the new EmbeddingAdapter.embed binding) → 8-dim vector.
    monkeypatch.setattr(engmod, "_build_embed_adapter", lambda c: _core.StubEmbeddingAdapter(8))
    r = client.post("/api/config/test", json={"kind": "embedder", "api_key": "sk-x"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["detail"] == "dim=8"


def test_config_test_no_key_is_failure(ctx):
    _, _, client, _ = ctx
    r = client.post("/api/config/test", json={"kind": "llm", "provider": "openai"})
    assert r.status_code == 200 and r.json()["ok"] is False
