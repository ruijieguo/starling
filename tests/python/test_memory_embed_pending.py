"""Memory.embed_pending(now) -> EmbedStats:只跑嵌入阶段,返回成功与失败计数。

离线:stub LLM、`unsupported-starling-test://invalid` 嵌入器、OPENAI_API_KEY=test-key,
不发任何真实网络请求。
"""
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


def test_embed_pending_embeds_new_statements(tmp_path):
    mem = _mem(tmp_path)
    mem.remember("Bob owns the auth module", now="2026-01-01T00:00:00Z")
    st = mem.embed_pending("2026-01-01T00:00:01Z")
    assert isinstance(st, starling.EmbedStats)
    assert st.embedded >= 1 and st.failed == 0
    assert mem.embed_pending("2026-01-01T00:00:02Z") == starling.EmbedStats(0, 0)


def test_embed_pending_counts_failures_without_raising(tmp_path, monkeypatch):
    mem = _mem(tmp_path, embedder=_bad_embedder(monkeypatch))
    mem.remember("Bob owns the auth module", now="2026-01-01T00:00:00Z")
    st = mem.embed_pending("2026-01-01T00:00:01Z")
    assert st.embedded == 0 and st.failed > 0


def test_embed_pending_runs_no_maintenance(tmp_path):
    import sqlite3
    mem = _mem(tmp_path)
    mem.remember("Bob owns the auth module", now="2026-01-01T00:00:00Z")
    mem.embed_pending("2026-01-01T00:00:01Z")
    with sqlite3.connect(str(tmp_path / "m.db")) as c:
        assert c.execute("SELECT DISTINCT consolidation_state, replay_count FROM statements").fetchall() == [("volatile", 0)]
