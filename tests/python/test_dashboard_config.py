import json
import os
import stat

from starling.dashboard.config import DashboardConfig


def test_load_defaults_and_token_autogen(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_DASH_TOKEN", raising=False)
    cfg_path = tmp_path / "starling.json"
    cfg = DashboardConfig.load(str(cfg_path))
    assert cfg.token and len(cfg.token) >= 20          # auto-generated
    assert cfg_path.exists()                            # persisted
    assert stat.S_IMODE(os.stat(cfg_path).st_mode) == 0o600
    # token stable across reloads
    cfg2 = DashboardConfig.load(str(cfg_path))
    assert cfg2.token == cfg.token


def test_file_then_env_precedence(tmp_path, monkeypatch):
    cfg_path = tmp_path / "starling.json"
    cfg_path.write_text(json.dumps({
        "token": "filetok", "host": "127.0.0.1", "port": 9000,
        "llm": {"model": "m-file", "base_url": "", "api_key": "k-file"},
    }))
    monkeypatch.setenv("STARLING_DASH_PORT", "9999")    # env overrides file
    cfg = DashboardConfig.load(str(cfg_path))
    assert cfg.port == 9999 and cfg.token == "filetok"
    assert cfg.llm["api_key"] == "k-file"


def test_save_roundtrip_excludes_config_path(tmp_path):
    cfg = DashboardConfig(db_path="x.db", token="t", config_path=str(tmp_path / "c.json"))
    cfg.llm = {"model": "gpt", "base_url": "", "api_key": "sk-xyz"}
    cfg.save()
    data = json.loads((tmp_path / "c.json").read_text())
    assert "config_path" not in data and data["llm"]["api_key"] == "sk-xyz"
    assert "embedder" in data
    import os as _os, stat as _stat
    assert _stat.S_IMODE(_os.stat(tmp_path / "c.json").st_mode) == 0o600
