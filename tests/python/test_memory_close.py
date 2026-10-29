"""Memory.close:等在途调用返回,合并 WAL,关连接;关后公开方法抛 MemoryClosed。

门面自己不起线程。"在途调用"是别的 Python 线程上正在跑、已释放 GIL 的 C++ 调用
(抽取、嵌入),这里用 FakeLLMAdapter.set_delay_ms 在 C++ 里睡来造。

离线:stub LLM、默认 stub 嵌入器,不发任何真实网络请求。
"""
import inspect
import threading
import time

import pytest

import starling

# 与 tests/python/test_memory_digest.py 的 CANNED_JSON 相同:单元素 JSON 数组。
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _db(tmp_path, name):
    return starling.Memory.open(str(tmp_path / name), agent="alice",
                                llm=starling.make_stub_llm(default_response=CANNED_JSON))


def _remember_in_thread(mem, key, out):
    def run():
        try:
            out["r"] = mem.remember_event(key, "bob:hi", interlocutor="bob")
        except BaseException as e:   # 线程里的异常要带回主线程断言
            out["err"] = e
    t = threading.Thread(target=run)
    t.start()
    return t


def test_close_waits_for_in_flight_remember(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON)
    llm.set_delay_ms(400)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    out = {}
    t = threading.Thread(target=lambda: out.update(r=mem.remember_event("e#0", "bob:hi", interlocutor="bob")))
    t.start(); time.sleep(0.1)
    mem.close()
    assert "r" in out and out["r"].statement_ids             # close 返回时在途调用已完成
    t.join(timeout=5)
    assert not (tmp_path / "m.db-wal").exists() or (tmp_path / "m.db-wal").stat().st_size == 0
    again = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    assert again.next_seq() == 1 and again.pending_events() == []


def test_close_timeout_keeps_library_open(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON); llm.set_delay_ms(600)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    t = threading.Thread(target=lambda: mem.remember_event("e#0", "bob:hi", interlocutor="bob"))
    t.start(); time.sleep(0.1)
    with pytest.raises(TimeoutError):
        mem.close(timeout=0.05)
    t.join(timeout=5)
    mem.close()


def test_calls_after_close_raise_and_close_is_idempotent(tmp_path):
    mem = _db(tmp_path, "m.db")
    mem.close(); mem.close()
    for call in (lambda: mem.recall("x"), lambda: mem.digest(), lambda: mem.next_seq(),
                 lambda: mem.embed_pending("2026-01-01T00:00:00Z"),
                 lambda: mem.remember_event("e#0", "bob:hi", interlocutor="bob"),
                 lambda: mem.backup_to(tmp_path / "c.db")):
        with pytest.raises(starling.MemoryClosed):
            call()


def test_every_public_method_is_guarded():
    """新加的公开方法漏包的话,关库后会拿到 C++ 层的 logic_error 而不是 MemoryClosed。"""
    exempt = {"open", "close"}
    unguarded = [
        name for name, member in inspect.getmembers(starling.Memory, inspect.isfunction)
        if not name.startswith("_") and name not in exempt
        and not hasattr(member, "__wrapped__")
    ]
    assert unguarded == []


def test_every_guarded_method_raises_memory_closed_after_close(tmp_path):
    mem = _db(tmp_path, "m.db")
    mem.close()
    calls = {
        "remember": lambda: mem.remember("Bob owns auth"),
        "recall": lambda: mem.recall("x"),
        "query": lambda: mem.query("x"),
        "latest_event_location": lambda: mem.latest_event_location("ball"),
        "tick": lambda: mem.tick(),
        "embed_pending": lambda: mem.embed_pending("2026-01-01T00:00:00Z"),
        "digest": lambda: mem.digest(),
        "backup_to": lambda: mem.backup_to(tmp_path / "c.db"),
        "content_ids": lambda: mem.content_ids(["x"]),
        "next_seq": lambda: mem.next_seq(),
        "pending_events": lambda: mem.pending_events(),
        "remember_event": lambda: mem.remember_event("e#0", "bob:hi", interlocutor="bob"),
        "abandon_event": lambda: mem.abandon_event("e#0"),
        "render_working_set": lambda: mem.render_working_set("bob"),
    }
    public = {name for name, member in inspect.getmembers(starling.Memory, inspect.isfunction)
              if not name.startswith("_") and name not in {"open", "close"}}
    assert set(calls) == public                       # 清单与类同步
    for name, call in calls.items():
        with pytest.raises(starling.MemoryClosed):
            call()
    assert not (tmp_path / "c.db").exists()           # 关库后 backup_to 没有写出任何东西


def test_new_calls_are_rejected_while_close_waits(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON); llm.set_delay_ms(500)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    out = {}
    t = _remember_in_thread(mem, "e#0", out)
    time.sleep(0.1)
    closer = threading.Thread(target=mem.close)
    closer.start(); time.sleep(0.1)                   # close 已置位、正在等 remember_event
    with pytest.raises(starling.MemoryClosed):
        mem.next_seq()
    closer.join(timeout=5); t.join(timeout=5)
    assert "r" in out and "err" not in out            # 在途调用不受影响,正常完成
    with pytest.raises(starling.MemoryClosed):
        mem.next_seq()


def test_timeout_leaves_library_usable_and_second_close_succeeds(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON); llm.set_delay_ms(500)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    out = {}
    t = _remember_in_thread(mem, "e#0", out)
    time.sleep(0.1)
    with pytest.raises(TimeoutError):
        mem.close(timeout=0.05)
    # 超时后库仍开着:新调用可以进来,在途数没有留下半关的计数。
    assert isinstance(mem.next_seq(), int)
    t.join(timeout=5)
    assert "r" in out and "err" not in out
    mem.close(timeout=5)
    with pytest.raises(starling.MemoryClosed):
        mem.next_seq()
    mem.close()                                       # 关后再关:无操作


def test_close_merges_wal_and_data_survives(tmp_path):
    mem = _db(tmp_path, "m.db")
    mem.remember_event("e#0", "bob:hi", interlocutor="bob")
    mem.embed_pending("2026-01-01T00:01:00Z")
    digest = mem.digest()
    mem.close()
    wal = tmp_path / "m.db-wal"
    assert not wal.exists() or wal.stat().st_size == 0
    again = _db(tmp_path, "m.db")
    assert again.digest() == digest
    again.close()


def test_close_releases_the_adapter_but_keeps_rt_addressable(tmp_path):
    mem = _db(tmp_path, "m.db")
    mem.close()
    assert mem._rt.adapter is not None               # examples/quickstart.py 与测试靠它
    assert mem._core.conn is None                    # MemoryCore.close 的既有行为不变
    with pytest.raises(RuntimeError, match="adapter closed"):
        mem._rt.adapter.connection()
    mem._rt.adapter.close()                          # 适配器层二次 close 也是无操作


def test_concurrent_closes_close_once(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON); llm.set_delay_ms(300)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    out = {}
    t = _remember_in_thread(mem, "e#0", out)
    time.sleep(0.1)
    errors = []

    def close():
        try:
            mem.close()
        except BaseException as e:
            errors.append(e)
    closers = [threading.Thread(target=close) for _ in range(3)]
    for c in closers:
        c.start()
    for c in closers:
        c.join(timeout=5)
    t.join(timeout=5)
    # join(timeout) returns silently on a hung thread, so check liveness
    # explicitly: a closer stuck in the state machine must fail the test, not
    # hang the suite at interpreter exit.
    assert not any(c.is_alive() for c in closers)
    assert not t.is_alive()
    assert errors == []
    assert "r" in out
    with pytest.raises(starling.MemoryClosed):
        mem.digest()


def test_close_timeout_zero_with_nothing_in_flight_still_closes(tmp_path):
    mem = _db(tmp_path, "m.db")
    mem.close(timeout=0)                             # 没有在途调用:不需要等,不会超时
    with pytest.raises(starling.MemoryClosed):
        mem.digest()


def test_failed_call_still_leaves_the_count_balanced(tmp_path):
    mem = _db(tmp_path, "m.db")
    with pytest.raises(KeyError):
        mem.abandon_event("never-recorded")          # 方法抛错,在途数也要减回去
    mem.close(timeout=1)                             # 计数没泄漏,不会超时


# ── 关库中途失败:不能留下"永久半关" ─────────────────────────────────────────

class _FlakyAdapter:
    """包住真适配器:第一次 close() 在真正关库之前就抛,第二次起转发给真适配器。

    模拟"检查点没跑成、句柄没释放"的失败(例如 close 刚进入就被打断)。其余属性原样转发。"""

    def __init__(self, real, exc):
        self._real = real
        self._exc = exc
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        if self.close_calls == 1:
            raise self._exc
        self._real.close()

    def __getattr__(self, name):
        return getattr(self._real, name)


def _wal_bytes(tmp_path):
    wal = tmp_path / "m.db-wal"
    return wal.stat().st_size if wal.exists() else 0


@pytest.mark.parametrize("exc", [RuntimeError("checkpoint failed"), KeyboardInterrupt()],
                         ids=["runtime_error", "keyboard_interrupt"])
@pytest.mark.parametrize("where", ["adapter_close", "core_close"])
def test_failed_teardown_can_be_retried_and_then_merges_the_wal(tmp_path, monkeypatch, where, exc):
    mem = _db(tmp_path, "m.db")
    mem.remember_event("e#0", "bob:hi", interlocutor="bob")
    assert _wal_bytes(tmp_path) > 0                   # 前提:WAL 里有未合并的写入

    if where == "adapter_close":
        flaky = _FlakyAdapter(mem._rt.adapter, exc)
        monkeypatch.setattr(mem._rt, "adapter", flaky)
        teardown_attempts = lambda: flaky.close_calls   # noqa: E731
    else:
        real_core_close = mem._core.close
        core_calls = []

        def flaky_core_close():
            core_calls.append(1)
            if len(core_calls) == 1:
                raise exc
            real_core_close()
        monkeypatch.setattr(mem._core, "close", flaky_core_close)
        # 这一支数的是 _core.close 的次数,不是适配器的:首次失败时适配器根本没被调到,
        # 所以"适配器被调两次"在这一支不成立。两支共用的断言意思是「拆除被重做了一次,
        # 关完之后不再重做」;真正钉住 WAL 有没有合并的是 _wal_bytes。
        teardown_attempts = lambda: len(core_calls)      # noqa: E731

    with pytest.raises(type(exc)):
        mem.close()
    # 句柄没释放、WAL 没合并;库不是"关完"状态,对外仍是已关(拒绝新调用)。
    assert mem._released is False
    assert mem._closing is False                      # 没有谁还占着 close
    assert _wal_bytes(tmp_path) > 0
    with pytest.raises(starling.MemoryClosed):
        mem.next_seq()

    mem.close()                                       # 重试:补上检查点
    assert mem._released is True
    assert _wal_bytes(tmp_path) == 0
    assert teardown_attempts() == 2
    with pytest.raises(starling.MemoryClosed):
        mem.next_seq()
    mem.close()                                       # 关完之后再关:无操作,不再碰适配器
    assert teardown_attempts() == 2

    again = _db(tmp_path, "m.db")
    assert again.next_seq() == 1 and again.pending_events() == []
    again.close()


def test_the_two_timeouts_are_told_apart_by_message(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON); llm.set_delay_ms(600)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    out = {}
    t = _remember_in_thread(mem, "e#0", out)
    time.sleep(0.1)

    # 第一个 close 排空超时:什么都没拆,库保持打开。
    with pytest.raises(TimeoutError, match="still in flight"):
        mem.close(timeout=0.05)
    assert isinstance(mem.next_seq(), int)

    # 第二个 close 在别的 close 排空时等它超时:库正在关或已关,不会重开。
    closer = threading.Thread(target=mem.close)
    closer.start(); time.sleep(0.1)                   # 这个 close 已置位、正等 remember_event
    with pytest.raises(TimeoutError, match="another close\\(\\) is in progress"):
        mem.close(timeout=0.05)
    with pytest.raises(starling.MemoryClosed):
        mem.next_seq()                                # 第二个超时没有让库重开

    closer.join(timeout=5); t.join(timeout=5)
    assert not closer.is_alive() and not t.is_alive()
    assert "r" in out
    mem.close()                                       # 已关:无操作
