"""WebSocket connection manager — broadcasts engine events to dashboards."""
from __future__ import annotations

import asyncio

from fastapi import WebSocket

# 单个 socket 一次推送的上限。命令路由在引擎租约内广播：一个不再读取的标签页若能让
# send_json 无限挂起，就会拉长每一份租约，世界切换随之等满上限回 ingest_busy。
_SEND_TIMEOUT_S = 2.0


class ConnectionManager:
    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)

    def register(self, ws: WebSocket) -> None:
        """Append an already-accepted socket (post-auth handshake path)."""
        self._active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._active:
            self._active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in list(self._active):
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=_SEND_TIMEOUT_S)
            except Exception:   # 含 TimeoutError：推不出去的 socket 一律当死连接摘掉
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
