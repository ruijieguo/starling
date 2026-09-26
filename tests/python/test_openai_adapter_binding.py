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


def test_json_object_output_config_is_explicit_and_off_by_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")
    cfg = _core.OpenAIAdapterConfig.from_env()
    assert hasattr(cfg, "json_object_output"), "native JSON mode config is missing"
    assert cfg.json_object_output is False
    cfg.json_object_output = True
    assert cfg.json_object_output is True


def test_enable_thinking_config_round_trip():
    cfg = _core.OpenAIAdapterConfig()
    assert hasattr(cfg, "enable_thinking"), "native thinking config is missing"
    assert cfg.enable_thinking is None
    cfg.enable_thinking = False
    assert cfg.enable_thinking is False
    cfg.enable_thinking = True
    assert cfg.enable_thinking is True
    cfg.enable_thinking = None
    assert cfg.enable_thinking is None


def test_native_structured_request_and_capability_surface():
    assert hasattr(_core, "StructuredOutputRequest"), "native typed request missing"
    request = _core.StructuredOutputRequest()
    assert request.mode == _core.OutputMode.Legacy
    request.mode = _core.OutputMode.JsonSchemaStrict
    request.contract = _core.OutputContractKind.ClaimAdmissionV1
    fake = _core.FakeLLMAdapter()
    fake.set_default_response('{"schema_version":1,"decisions":[]}', True, "")
    response = fake.extract_with_contract("JSON", "opaque", request)
    assert response.ok
    assert response.output_mode == request.mode
    assert response.output_contract == request.contract
    assert response.raw_completion == response.raw_xml
    assert len(response.schema_sha256) == 64
    assert fake.structured_requests[0].contract == request.contract
    assert hasattr(_core.OpenAIAdapter, "probe_structured_output")
    assert hasattr(_core.OpenAIAdapter, "clear_structured_output_capabilities")


def test_capability_archive_validator_is_native():
    assert hasattr(_core, "validate_capability_evidence_json"), "native evidence verifier missing"
    assert _core.validate_capability_evidence_json("{}")
