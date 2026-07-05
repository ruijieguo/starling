"""锁纪律:converse 的 chat 生成段不得持有 DashboardEngine._lock。
FakeLLMAdapter.set_delay_ms 在 C++ extract() 内睡(GIL 已释放)——生成段
人为拉长到 700ms;并发 tick 必须在生成期间拿到锁(<0.4s),拆锁前必然
阻塞 ≥0.55s(先 sleep(0.15) 再 tick)。chat/llm 注入模式抄
tests/python/test_dashboard_converse.py(eng._core.chat_llm = chat)。"""
import threading
import time

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "lock.db"), token="")
    eng = DashboardEngine(cfg)
    extraction = _core.FakeLLMAdapter()
    extraction.set_default_response(_STUB_JSON, True, "")
    eng.llm = extraction
    chat = _core.FakeLLMAdapter()
    chat.set_default_response("a slow reply", True, "")
    chat.set_delay_ms(700)          # 生成段 = C++ 内睡 700ms(零网络)
    return eng, chat


def test_tick_interleaves_during_generate(tmp_path):
    eng, chat = _engine(tmp_path)
    eng._core.chat_llm = chat             # 既有注入模式(test_dashboard_converse.py)
    out: dict = {}
    turn = threading.Thread(
        target=lambda: out.update(eng.converse("hello", holder="self")))
    turn.start()
    time.sleep(0.15)                       # prepare 是毫秒级 → 已进生成段
    start = time.monotonic()
    eng.tick("2026-07-05T00:00:00Z")       # 拆锁后:生成段中锁可得
    elapsed = time.monotonic() - start
    turn.join(timeout=5)
    assert out.get("ok") is True
    assert elapsed < 0.4, f"tick 等锁 {elapsed:.2f}s —— 生成段仍持锁"


def test_resolve_chat_local_reference(tmp_path):
    eng, chat = _engine(tmp_path)
    # None → role-bound 回退(chat_llm 未绑 → 抽取 llm)
    assert eng._resolve_chat(None) is eng._core.chat_llm or eng._resolve_chat(None) is eng._core.llm
    # 未配 provider → LLMNotConfigured
    import pytest
    from starling.dashboard.engine import _LLMNotConfigured
    with pytest.raises(_LLMNotConfigured):
        eng._resolve_chat("no-such-provider")
