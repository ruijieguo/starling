"""GIL 释放回归(2026-06-11 修复:全绑定层原本 0 处 gil_scoped_release)。

被钉的事实:LLM/embedder 网络调用对应的绑定在 C++ 阻塞期间必须释放 GIL,
否则 dashboard 把工作丢进 anyio 线程也没用——线程换了、锁没放,事件循环
照样冻结(用户可见:remember 进行中全站无响应)。

测法:FakeLLMAdapter.set_delay_ms 在 C++ extract() 里制造确定性阻塞窗口
(零网络);线程 A 调被守护的绑定阻塞其中,主线程同时累加计数器——
GIL 已释放 ⇒ 计数推进;未释放 ⇒ 主线程第一条字节码就卡住,计数为 0。
阈值给得很宽(700ms 窗口只要求 ≥5 次 5ms 步进),CI 抖动安全。
"""
import threading
import time

import starling
from starling import _core

CANNED_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _progress_while(blocking_call) -> int:
    """跑 blocking_call 于线程 A,返回其阻塞期间主线程完成的步进数。"""
    started = threading.Event()
    done = threading.Event()

    def runner():
        started.set()
        try:
            blocking_call()
        finally:
            done.set()

    t = threading.Thread(target=runner)
    t.start()
    started.wait()
    progress = 0
    while not done.is_set():
        time.sleep(0.005)
        progress += 1
    t.join()
    return progress


def test_memory_remember_releases_gil(tmp_path):
    # 生产入口:MemoryCore.remember → _core.memory_remember(bind_13 守护)。
    llm = starling.make_stub_llm(default_response=CANNED_JSON)
    llm.set_delay_ms(700)
    mem = starling.Memory.open(str(tmp_path / "gil.db"), agent="alice", llm=llm)
    try:
        progress = _progress_while(lambda: mem.remember("Bob owns the auth module"))
    finally:
        mem.close()
    assert progress >= 5, (
        f"memory_remember 阻塞 C++ 期间主线程仅推进 {progress} 步——GIL 未释放")


def test_extractor_run_releases_gil(tmp_path):
    # 直调路径:_core.Extractor.run(bind_06 守护,eval 脚本等使用)。
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(tmp_path / "gil2.db")
    r.start()
    # 先经正常路径建好 engram(零延迟),再用带延迟的 run 复抽(noop 路径同样
    # 穿过 LLM 调用,阻塞窗口成立)。
    llm = starling.make_stub_llm(default_response=CANNED_JSON)
    mem = starling.Memory(r, agent="alice", tenant_id="default", llm=llm)
    engram_ref = mem.remember("Bob owns the auth module").engram_ref
    assert engram_ref

    llm.set_delay_ms(700)
    ex = _core.Extractor(r.adapter.connection(), llm)
    progress = _progress_while(
        lambda: ex.run(engram_ref, b"Bob owns the auth module", "alice", "default", {}, ""))
    mem.close()
    assert progress >= 5, (
        f"Extractor.run 阻塞 C++ 期间主线程仅推进 {progress} 步——GIL 未释放")
