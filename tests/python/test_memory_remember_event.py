"""Memory.remember_event 的三段写入与 EventConflict(迁移 0038 的 events 表写侧)。

rise 每轮对话写一条记忆事件,带调用方给的稳定 key。重放要幂等:同 key 同文本不会
再抽取一次、不会写重复语句;第三段之前崩溃后重调要按 engram 补齐成 committed。

离线:stub LLM、默认 stub 嵌入器,不发任何真实网络请求。
"""
import sqlite3

import pytest

import starling

# 与 tests/python/test_memory_facade.py 的 CANNED_JSON 相同:单元素 JSON 数组。
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)

KEY = "r1/deploy-m-s-0#3"          # 含 "/":Starling 不校验 key 字符集,原样存取


def _mem(tmp_path, **kw):
    return starling.Memory.open(str(tmp_path / "m.db"), agent="alice",
                                llm=starling.make_stub_llm(default_response=CANNED_JSON), **kw)


def _failing_llm():
    llm = starling.make_stub_llm(default_response="")
    llm.set_default_response("", False, "stub extraction failure")
    return llm


def _count(tmp_path, sql):
    with sqlite3.connect(str(tmp_path / "m.db")) as c:
        return c.execute(sql).fetchone()[0]


def test_new_key_commits_and_assigns_seq(tmp_path):
    mem = _mem(tmp_path)
    res = mem.remember_event(KEY, "bob:我负责鉴权模块", interlocutor="bob")
    assert res.outcome == "accepted" and not res.extraction_failed and res.statement_ids
    assert mem.next_seq() == 1 and mem.pending_events() == []
    with sqlite3.connect(str(tmp_path / "m.db")) as c:
        row = c.execute("SELECT state, seq, key FROM events").fetchone()
        payload = c.execute("SELECT payload_inline FROM engrams").fetchone()[0]
    assert row == ("committed", 0, KEY)
    assert payload.decode() == f"[{KEY}] bob:我负责鉴权模块"


def test_same_key_same_text_returns_stored_ids_without_extraction(tmp_path):
    mem = _mem(tmp_path)
    first = mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    n = _count(tmp_path, "SELECT COUNT(*) FROM statements")
    mem._core.llm = _failing_llm()                 # 若再抽取就会 extraction_failed
    again = mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    assert again.outcome == "idempotent" and not again.extraction_failed
    assert again.statement_ids == first.statement_ids
    assert _count(tmp_path, "SELECT COUNT(*) FROM statements") == n
    assert mem.next_seq() == 1


def test_same_key_different_text_conflicts(tmp_path):
    mem = _mem(tmp_path)
    mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    with pytest.raises(starling.EventConflict):
        mem.remember_event(KEY, "bob:bye", interlocutor="bob")


def test_extraction_failure_leaves_pending_with_category_then_retry_commits(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=_failing_llm())
    res = mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    assert res.extraction_failed
    [p] = mem.pending_events()
    assert (p.key, p.text, p.interlocutor, p.seq) == (KEY, "bob:hi", "bob", 0)
    assert p.failure_category == res.failure_category != ""
    mem._core.llm = starling.make_stub_llm(default_response=CANNED_JSON)
    ok = mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    assert not ok.extraction_failed and ok.statement_ids
    assert mem.pending_events() == [] and mem.next_seq() == 1      # 重试不另分配 seq


def test_crash_before_phase_three_is_completed_from_engram(tmp_path):
    # 模拟"② 落了语句、③ 没写成":先留一条 pending 行,再用裸 remember 写同一 payload。
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=_failing_llm())
    mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    mem._core.llm = starling.make_stub_llm(default_response=CANNED_JSON)
    landed = mem.remember(f"[{KEY}] bob:hi", interlocutor="bob",
                          now="2026-01-01T00:00:00Z")
    assert landed.statement_ids
    n = _count(tmp_path, "SELECT COUNT(*) FROM statements")
    mem._core.llm = _failing_llm()                 # 补齐不得再抽取
    res = mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    assert not res.extraction_failed
    assert sorted(res.statement_ids) == sorted(landed.statement_ids)
    assert _count(tmp_path, "SELECT COUNT(*) FROM statements") == n
    assert mem.pending_events() == []


def test_pending_without_engram_reextracts_from_stored_text(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=_failing_llm())
    mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    with sqlite3.connect(str(tmp_path / "m.db")) as c:   # python sqlite3 默认不开外键
        c.execute("DELETE FROM engrams")
    mem._core.llm = starling.make_stub_llm(default_response=CANNED_JSON)
    res = mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    assert res.statement_ids and not res.extraction_failed
    assert _count(tmp_path, "SELECT COUNT(*) FROM engrams") == 1


def test_event_time_derives_from_seq(tmp_path):
    mem = _mem(tmp_path)
    mem.remember_event("a#0", "bob:one", interlocutor="bob")
    mem.remember_event("a#1", "bob:two", interlocutor="bob")
    with sqlite3.connect(str(tmp_path / "m.db")) as c:
        times = [r[0] for r in c.execute("SELECT created_at FROM engrams ORDER BY created_at")]
    assert times == ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"]


def test_remember_event_requires_llm(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice")
    with pytest.raises(starling._memory_core.LLMNotConfigured):
        mem.remember_event(KEY, "bob:hi", interlocutor="bob")
    assert mem.next_seq() == 0                      # 没写 pending 行
