"""Memory.recall(holder=, strict=) 与 RecallDegradedError。

离线:stub LLM、`unsupported-starling-test://invalid` 嵌入器、OPENAI_API_KEY=test-key,
不发任何真实网络请求。
"""
import pytest

import starling

# 与 tests/python/test_memory_facade.py 的 CANNED_JSON 相同:单元素 JSON 数组。
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _mem(tmp_path, **kw):
    return starling.Memory.open(str(tmp_path / "m.db"), agent="alice",
                                llm=starling.make_stub_llm(default_response=CANNED_JSON), **kw)


def _bad_embedder(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return starling.make_openai_embedder(model="offline", dim=8, timeout_ms=10,
                                         base_url="unsupported-starling-test://invalid")


def test_recall_forwards_holder(tmp_path):
    mem = _mem(tmp_path)
    mem.remember("Bob owns the auth module", holder="carol", now="2026-01-01T00:00:00Z")
    mem.tick("2026-01-01T00:00:01Z")          # 本任务时 recall 只见 consolidated 行,见 Task 4
    assert mem.recall("Bob owns the auth module") == []
    hits = mem.recall("Bob owns the auth module", holder="carol")
    assert len(hits) == 1 and hits[0]["row"].holder_id == "carol"


def test_strict_recall_raises_when_query_embedding_fails(tmp_path, monkeypatch):
    mem = _mem(tmp_path, embedder=_bad_embedder(monkeypatch))
    with pytest.raises(starling.RecallDegradedError):
        mem.recall("anything", strict=True)


def test_non_strict_recall_keeps_old_empty_result(tmp_path, monkeypatch):
    mem = _mem(tmp_path, embedder=_bad_embedder(monkeypatch))
    assert mem.recall("anything") == []
    assert mem.recall("anything", strict=False) == []


def test_strict_rejects_completion_mode(tmp_path):
    with pytest.raises(ValueError):
        _mem(tmp_path).recall("x", mode="completion", strict=True)


def test_strict_recall_returns_hits_when_embedding_is_healthy(tmp_path):
    # 默认 stub 嵌入器是健康的:strict=True 不能因为"开了 strict"就抛,
    # 只有 SemanticResult.degraded 为真时才抛。钉住 `strict and res.degraded` 这道门。
    mem = _mem(tmp_path)
    mem.remember("Bob owns the auth module", now="2026-01-01T00:00:00Z")
    mem.tick("2026-01-01T00:00:01Z")
    hits = mem.recall("Bob owns the auth module", strict=True)
    assert len(hits) == 1 and hits[0]["row"].holder_id == "alice"
