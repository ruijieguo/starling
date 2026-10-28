import starling
from starling import _core


def test_open_without_embedder_keeps_stub_8(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice")
    assert mem._core.emb.model() == "stub" and mem._core.emb.dim() == 8
    mem.close()


def test_open_with_injected_embedder(tmp_path):
    emb = _core.StubEmbeddingAdapter(16)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", embedder=emb)
    assert mem._core.emb is emb
    assert mem._core.semantic is not None and mem._core.worker is not None
    mem.close()


def test_make_openai_embedder_sets_fields_without_network(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    emb = starling.make_openai_embedder(model="text-embedding-3-small",
                                        base_url="http://127.0.0.1:9/v1",
                                        dim=1536, timeout_ms=50)
    assert isinstance(emb, _core.OpenAIEmbeddingAdapter)
    assert emb.model() == "text-embedding-3-small" and emb.dim() == 1536
    assert (emb.request_count, emb.embed_calls, emb.batch_calls) == (0, 0, 0)


def _spy_on_adapter_config(monkeypatch, name):
    """Wrap the native adapter class so the config handed to it is observable.

    The bound adapters expose no config getters, so the only offline way to see
    what the factory actually set is to capture the config at construction.
    """
    real = getattr(_core, name)
    seen = []

    def spy(cfg):
        seen.append(cfg)
        return real(cfg)

    monkeypatch.setattr(_core, name, spy)
    return seen


def test_max_retries_zero_is_honoured_by_both_factories(monkeypatch):
    # The C++ defaults are max_retries = 3 for both configs; a "set only if
    # non-zero" override would turn a configured 0 into 3 silent retries.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert _core.OpenAIAdapterConfig.from_env().max_retries == 3
    assert _core.OpenAIEmbeddingConfig.from_env().max_retries == 3

    llm_cfgs = _spy_on_adapter_config(monkeypatch, "OpenAIAdapter")
    emb_cfgs = _spy_on_adapter_config(monkeypatch, "OpenAIEmbeddingAdapter")

    starling.make_openai_llm(model="m", base_url="http://127.0.0.1:9/v1",
                             timeout_ms=50, max_retries=0)
    starling.make_openai_embedder(model="m", base_url="http://127.0.0.1:9/v1",
                                  dim=8, timeout_ms=50, max_retries=0)
    assert [c.max_retries for c in llm_cfgs] == [0]
    assert [c.max_retries for c in emb_cfgs] == [0]

    # A non-zero value still passes through.
    starling.make_openai_llm(model="m", max_retries=2)
    starling.make_openai_embedder(model="m", base_url="http://127.0.0.1:9/v1",
                                  dim=8, timeout_ms=50, max_retries=2)
    assert llm_cfgs[-1].max_retries == 2 and emb_cfgs[-1].max_retries == 2


def test_omitting_max_retries_keeps_the_cpp_default_in_both_factories(monkeypatch):
    # Existing callers that never pass max_retries (smoke script, e2e tests)
    # must keep the C++ default of 3; only an explicit value may change it.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    cpp_llm = _core.OpenAIAdapterConfig.from_env().max_retries
    cpp_emb = _core.OpenAIEmbeddingConfig.from_env().max_retries
    assert (cpp_llm, cpp_emb) == (3, 3)

    llm_cfgs = _spy_on_adapter_config(monkeypatch, "OpenAIAdapter")
    emb_cfgs = _spy_on_adapter_config(monkeypatch, "OpenAIEmbeddingAdapter")

    starling.make_openai_llm(model="m")
    starling.make_openai_llm(model="m", max_retries=None)
    starling.make_openai_embedder(model="m", base_url="http://127.0.0.1:9/v1",
                                  dim=8, timeout_ms=50)
    starling.make_openai_embedder(model="m", base_url="http://127.0.0.1:9/v1",
                                  dim=8, timeout_ms=50, max_retries=None)
    assert [c.max_retries for c in llm_cfgs] == [cpp_llm, cpp_llm]
    assert [c.max_retries for c in emb_cfgs] == [cpp_emb, cpp_emb]

