"""Pybind binding round-trip for OpenAIAdapter.

These tests do NOT hit the network. They verify only that the binding
exposes Config/Adapter with the expected surface and that env-var
plumbing works. The api_key field is intentionally NOT exposed to Python.
"""

from __future__ import annotations

import pytest

from starling import _core
from starling.extractor.openai_client import make_openai_adapter


def test_config_default_when_base_url_unset(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    cfg = _core.OpenAIAdapterConfig.from_env()
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.model == "gpt-5.5"
    # api_key intentionally NOT readable from Python (spec §3.3)
    assert not hasattr(cfg, "api_key")


def test_config_from_env_reads_proxy(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")
    cfg = _core.OpenAIAdapterConfig.from_env()
    assert cfg.base_url == "https://proxy.example/v1"


def test_config_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        _core.OpenAIAdapterConfig.from_env()


def test_adapter_construction_does_not_hit_network(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")
    adapter = make_openai_adapter()
    assert adapter is not None  # No exception, no network call yet
