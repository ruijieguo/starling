"""FastAPI app factory for the Starling dashboard engine-API."""
from __future__ import annotations

import hmac
import urllib.parse

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from starling.dashboard.auth import make_require_token
from starling.dashboard.config import DashboardConfig


def _ws_origin_allowed(origin: str, cors_origins: list[str]) -> bool:
    """CSWSH guard. Browsers always send Origin on WS; non-browser clients omit it.

    - no Origin  -> allow (CLI / server-side client, not a CSWSH vector)
    - allowlist set -> Origin must be in it
    - no allowlist (loopback dev) -> allow only loopback-origin browsers
    """
    if not origin:
        return True
    if cors_origins:
        return origin in cors_origins
    host = urllib.parse.urlparse(origin).hostname
    return host in ("127.0.0.1", "localhost", "::1")


def create_app(config: DashboardConfig, *, engine: object | None = None) -> FastAPI:
    """Build the dashboard app.

    `engine` (a `DashboardEngine`) is the engine owner for command routes; when
    None it is lazily built from `config` at first command use (production).
    Inspection routes read the SQLite at `config.db_path` directly (read-only).
    """
    config.validate_bind()
    app = FastAPI(title="Starling Dashboard", version="0.1.0")
    app.state.config = config
    app.state.engine = engine

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    require_token = make_require_token(config.token)

    from starling.dashboard.realtime import ConnectionManager

    app.state.ws_manager = ConnectionManager()

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        origin = ws.headers.get("origin", "")
        if not _ws_origin_allowed(origin, config.cors_origins):
            await ws.close(code=1008)
            return
        # auth handshake: first text frame must be the token (when configured).
        # Sending the token in-band (not via URL query) avoids leaking it in logs.
        if config.token:
            await ws.accept()
            try:
                first = await ws.receive_text()
            except WebSocketDisconnect:
                return
            if not hmac.compare_digest(first, config.token):
                await ws.close(code=1008)
                return
            app.state.ws_manager.register(ws)
        else:
            await app.state.ws_manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            app.state.ws_manager.disconnect(ws)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": app.version}

    @app.get("/api/ping", dependencies=[Depends(require_token)])
    async def ping() -> dict:
        return {"pong": True}

    from starling.dashboard.routes.inspect import build_inspect_router
    from starling.dashboard.routes.commands import build_commands_router
    from starling.dashboard.routes.evalreport import build_eval_router

    app.include_router(build_inspect_router(require_token))
    app.include_router(build_commands_router(require_token))
    app.include_router(build_eval_router(require_token))

    return app
