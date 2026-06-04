"""WebSocket realtime tests: broadcast logic + connect + wrong-token rejection."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.realtime import ConnectionManager


class _FakeWS:
    """Minimal async WebSocket double for ConnectionManager unit tests."""

    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


def test_manager_broadcasts_to_connected():
    """Unit: a connected socket receives every broadcast message."""
    mgr = ConnectionManager()
    ws = _FakeWS()

    async def scenario() -> None:
        await mgr.connect(ws)
        await mgr.broadcast({"type": "tick", "payload": {"fired": 1}})

    asyncio.run(scenario())

    assert ws.accepted is True
    assert ws.sent == [{"type": "tick", "payload": {"fired": 1}}]


def test_manager_drops_dead_sockets():
    """Unit: a socket that raises on send is removed and does not block others."""
    mgr = ConnectionManager()
    live = _FakeWS()

    class _DeadWS(_FakeWS):
        async def send_json(self, message: dict) -> None:
            raise RuntimeError("boom")

    dead = _DeadWS()

    async def scenario() -> None:
        await mgr.connect(live)
        await mgr.connect(dead)
        await mgr.broadcast({"type": "tick", "payload": {}})

    asyncio.run(scenario())

    assert live.sent == [{"type": "tick", "payload": {}}]
    assert dead not in mgr._active
    assert live in mgr._active


def test_ws_receives_broadcast():
    """Integration: a tokenless client connects and receives a broadcast frame.

    The broadcast is triggered from inside the app's event loop via the
    TestClient portal so the WebSocket send happens on the right loop.
    """
    cfg = DashboardConfig(db_path=":memory:", token="")
    app = create_app(cfg)
    # Enter the TestClient as a context manager so `client.portal` is bound to a
    # live blocking portal; the websocket session then shares that portal/loop,
    # letting us drive a broadcast from the app's event loop deterministically.
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            client.portal.call(
                app.state.ws_manager.broadcast,
                {"type": "tick", "payload": {"fired": 1}},
            )
            msg = ws.receive_json()
            assert msg["type"] == "tick"
            assert msg["payload"]["fired"] == 1


def test_ws_token_rejects_wrong():
    """Integration: wrong handshake token closes the socket (code 1008)."""
    cfg = DashboardConfig(db_path=":memory:", token="secret")
    app = create_app(cfg)
    client = TestClient(app)
    from starlette.websockets import WebSocketDisconnect

    with client.websocket_connect("/ws") as ws:
        ws.send_text("wrong")
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
