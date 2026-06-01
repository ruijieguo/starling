"""OpenAIEmbeddingAdapter must be constructible (production embedder for gated evals)."""
import os
from starling import _core

def test_openai_embedding_adapter_constructs():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")   # construction only, no network
    cfg = _core.OpenAIEmbeddingConfig.from_env()
    cfg.model = "text-embedding-3-small"
    emb = _core.OpenAIEmbeddingAdapter(cfg)
    assert emb is not None
