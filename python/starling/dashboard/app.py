"""FastAPI app factory for the Starling dashboard engine-API."""
from __future__ import annotations

import asyncio
import hmac
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # P2.o 运行时闭环:默认启动后台维护 tick(tick_interval_s=0 关闭)。
        # 引擎在此即建(而非等首个命令请求)——闭环从进程启动起就在转。
        # lifespan 只在 ASGI 服务器/`with TestClient` 下运行;直接构造
        # TestClient(app) 的既有测试不受影响。
        if config.tick_interval_s > 0:
            eng = app.state.engine
            if eng is None:
                from starling.dashboard.engine import DashboardEngine
                eng = DashboardEngine(config)
                app.state.engine = eng
            # 测试可注入只实现部分接口的引擎替身,故按能力探测。
            if hasattr(eng, "start_background_tick"):
                loop = asyncio.get_running_loop()
                mgr = app.state.ws_manager

                def _on_tick(stats: dict) -> None:
                    # 维护线程 → 事件循环的桥;消息形状与手动 /api/tick 一致,
                    # 前端无需区分自动/手动。
                    asyncio.run_coroutine_threadsafe(
                        mgr.broadcast({"type": "tick", "payload": stats}), loop)

                eng.start_background_tick(config.tick_interval_s, _on_tick)
        yield
        eng = app.state.engine
        if eng is not None and hasattr(eng, "stop_background_tick"):
            eng.stop_background_tick()

    app = FastAPI(title="Starling Dashboard", version="0.1.0", lifespan=lifespan)
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
    from starling.dashboard.routes.config import build_config_router

    app.include_router(build_inspect_router(require_token))
    app.include_router(build_commands_router(require_token))
    app.include_router(build_eval_router(require_token))
    app.include_router(build_config_router(require_token))

    _build = Path(__file__).resolve().parents[3] / "dashboard" / "web" / "build"
    if _build.is_dir():
        _build_resolved = _build.resolve()

        @app.get("/{full_path:path}")
        async def spa(full_path: str):
            # SPA fallback: serve a real static file if present, else index.html.
            candidate = (_build / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(_build_resolved):
                return FileResponse(str(candidate))
            return FileResponse(str(_build_resolved / "index.html"))
    return app
