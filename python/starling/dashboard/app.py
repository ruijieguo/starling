"""FastAPI app factory for the Starling dashboard engine-API."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starling.dashboard.auth import make_require_token
from starling.dashboard.config import DashboardConfig


def create_app(config: DashboardConfig, *, memory: Optional[object] = None) -> FastAPI:
    """Build the dashboard app.

    `memory` (a `starling.Memory`) is the engine owner for command routes; when
    None it is lazily built from `config` at first command use (production).
    Inspection routes read the SQLite at `config.db_path` directly (read-only).
    """
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
    app.state.require_token = require_token

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": app.version}

    @app.get("/api/ping", dependencies=[Depends(require_token)])
    async def ping() -> dict:
        return {"pong": True}

    return app
