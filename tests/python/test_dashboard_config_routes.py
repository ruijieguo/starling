import json
import os
import stat

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine


@pytest.fixture
def ctx(tmp_path):
    cfgfile = tmp_path / "starling.json"
    cfg = DashboardConfig(db_path=str(tmp_path / "c.db"), token="", config_path=str(cfgfile))
    eng = DashboardEngine(cfg)
    client = TestClient(create_app(cfg, engine=eng))
    return cfg, eng, client, cfgfile


def test_get_config_masks_keys(ctx):
    cfg, eng, client, _ = ctx
    cfg.llm["api_key"] = "sk-secret-1234"
    body = client.get("/api/config").json()
    assert body["llm"]["key_set"] is True
    assert "api_key" not in body["llm"] and "secret" not in json.dumps(body)


def test_post_config_persists_0600_and_hot_swaps(ctx, monkeypatch):
    cfg, eng, client, cfgfile = ctx
    # avoid real network: stub the chat-adapter builder so set_llm yields a non-None obj
    from starling import _core
    import starling.dashboard.engine as engmod
    monkeypatch.setattr(engmod, "_build_chat_adapter", lambda c: _core.FakeLLMAdapter())
    r = client.post("/api/config", json={"llm": {"model": "m", "base_url": "", "api_key": "sk-x"}})
    assert r.status_code == 200 and r.json()["llm"]["key_set"] is True
    assert cfgfile.exists() and stat.S_IMODE(os.stat(cfgfile).st_mode) == 0o600
    assert json.loads(cfgfile.read_text())["llm"]["api_key"] == "sk-x"
    assert eng.llm is not None                       # hot-swapped


def test_get_config_never_returns_token(ctx):
    cfg, eng, client, _ = ctx
    assert "token" not in client.get("/api/config").json()
