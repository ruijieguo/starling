"""ConnectionManager.broadcast 的单 socket 推送上限。

命令路由在引擎租约内广播（routes/commands.py 的 _broadcast）。一个不再读取的仪表盘标签页
若能让 send_json 无限挂起，就会拉长每一份租约，世界切换随之等满上限回 ingest_busy。
"""
from __future__ import annotations

import asyncio
import time

from starling.dashboard import realtime
from starling.dashboard.realtime import ConnectionManager


class _StuckSocket:
    """send_json 永不返回：模拟停止读取、TCP 窗口塞满的客户端。"""

    def __init__(self) -> None:
        self.sent = 0

    async def send_json(self, message: dict) -> None:
        self.sent += 1
        await asyncio.Event().wait()


class _HealthySocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)


def test_broadcast_drops_a_stuck_socket_within_the_send_timeout(monkeypatch):
    monkeypatch.setattr(realtime, "_SEND_TIMEOUT_S", 0.2)
    mgr = ConnectionManager()
    stuck, healthy = _StuckSocket(), _HealthySocket()
    mgr.register(stuck)
    mgr.register(healthy)

    started = time.monotonic()
    asyncio.run(asyncio.wait_for(mgr.broadcast({"type": "tick"}), timeout=5.0))
    elapsed = time.monotonic() - started

    assert elapsed < 2.0, f"broadcast blocked for {elapsed:.2f}s on a stuck socket"
    assert stuck.sent == 1
    assert healthy.messages == [{"type": "tick"}]
    # 推不出去的 socket 当死连接摘掉；下一次广播不再为它等。
    assert stuck not in mgr._active
    assert healthy in mgr._active


def test_broadcast_default_timeout_is_bounded():
    # 上限本身必须是有限的小数：0 或 None 都会把「挂住的 socket 拖长租约」放回来。
    assert 0 < realtime._SEND_TIMEOUT_S <= 5.0
