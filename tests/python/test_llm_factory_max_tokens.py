import inspect

import starling


def test_make_openai_llm_accepts_max_tokens(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid")
    llm = starling.make_openai_llm(model="m", max_tokens=32768)
    assert llm is not None


def test_max_tokens_in_signature():
    assert "max_tokens" in inspect.signature(starling.make_openai_llm).parameters
    assert "max_tokens" in inspect.signature(starling.make_anthropic_llm).parameters
