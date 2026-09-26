"""OpenAIEmbeddingAdapter must be constructible (production embedder for gated evals)."""
import os
import pytest
from starling import _core

def test_openai_embedding_adapter_constructs():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")   # construction only, no network
    cfg = _core.OpenAIEmbeddingConfig.from_env()
    cfg.model = "text-embedding-3-small"
    emb = _core.OpenAIEmbeddingAdapter(cfg)
    assert emb is not None


def test_embedding_native_counters_include_failed_attempts_and_are_readonly():
    cfg = _core.OpenAIEmbeddingConfig()
    cfg.base_url = "unsupported-starling-test://invalid"
    cfg.max_retries = 3  # Unsupported protocol is permanent, so only one attempt.
    cfg.timeout_ms = 10
    emb = _core.OpenAIEmbeddingAdapter(cfg)
    assert hasattr(emb, "request_count"), "native embedding request counters missing"
    assert (emb.request_count, emb.embed_calls, emb.batch_calls) == (0, 0, 0)
    with pytest.raises(RuntimeError, match="transport_error"):
        emb.embed("offline fixture")
    assert (emb.request_count, emb.embed_calls, emb.batch_calls) == (1, 1, 0)
    with pytest.raises(AttributeError):
        emb.request_count = 100


def test_real_embedding_metadata_uses_same_native_interface_as_stub():
    cfg = _core.OpenAIEmbeddingConfig()
    cfg.model, cfg.dim = "configured-offline-model", 1024
    real = _core.OpenAIEmbeddingAdapter(cfg)
    stub = _core.StubEmbeddingAdapter(8)
    assert isinstance(real, _core.EmbeddingAdapter)
    assert real.model() == "configured-offline-model"
    assert real.dim() == 1024
    assert isinstance(stub.model(), str) and stub.dim() == 8
    assert (real.request_count, real.embed_calls, real.batch_calls) == (0, 0, 0)
