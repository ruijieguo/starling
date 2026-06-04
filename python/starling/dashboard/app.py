"""FastAPI app factory for the Starling dashboard engine-API."""
from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from starling.dashboard.auth import make_require_token
from starling.dashboard.config import DashboardConfig


def create_app(config: DashboardConfig, *, memory: object | None = None) -> FastAPI:
    """Build the dashboard app.

    `memory` (a `starling.Memory`) is the engine owner for command routes; when
    None it is lazily built from `config` at first command use (production).
    Inspection routes read the SQLite at `config.db_path` directly (read-only).
    """
    config.validate_bind()
    app = FastAPI(title="Starling Dashboard", version="0.1.0")
    app.state.config = config
    app.state.memory = memory

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
