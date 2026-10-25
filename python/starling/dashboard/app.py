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
    # 左脑 lane 的开关一致性在启动时就拒绝，而不是等到第一次摄入才发现。
    config.validate_source_lane()
    # 世界注册表引导：必须在 create_app 内、引擎建立之前原地把 config 改成活动世界。
    # 生产入口 run_dashboard.py 先 create_app(cfg) 再 DashboardEngine(cfg)，两者共用
    # 同一个 cfg，所以引擎自然打开活动世界的库。:memory: 等无父目录的库没有地方放
    # 注册表，bootstrap 返回 None，app.state.worlds 保持 None（路由据此回 503）。
    from starling.dashboard.world_manager import WorldManager, bootstrap_worlds
    registry_path = bootstrap_worlds(config)

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
                    # 前端无需区分自动/手动。子项 B 的 embed-depth 采样已下沉到
                    # engine._loop 里无条件调用(review fix:此处受 did_work
                    # 门控,会丢空闲/卡死轮的样本),不再挂在这个回调上。
                    asyncio.run_coroutine_threadsafe(
                        mgr.broadcast({"type": "tick", "payload": stats}), loop)

                eng.start_background_tick(config.tick_interval_s, _on_tick)
                if app.state.worlds is not None:
                    app.state.worlds.on_tick = _on_tick   # 切换世界后新引擎沿用同一广播
        # dogfood 子项 A(Task 3):spool ingest worker——独立于 tick_interval_s
        # (codex:关掉维护 tick 不该连带禁掉摄入,两者是不同的闭环)。只要有引擎
        # (刚才按 tick 建的,或外部注入的),就启动它;tick_interval_s=0 时引擎
        # 本就可能是 None(见上面的分支),此时无引擎可启——与 tick 关闭时的
        # 既有行为一致,不额外建引擎。
        eng = app.state.engine
        if eng is not None and hasattr(eng, "start_ingest_worker"):
            eng.start_ingest_worker()
        if app.state.worlds is not None:
            # 线程已起：此后切换世界才需要为新引擎重启它们。无 lifespan 的
            # TestClient(app) 不会走到这里，切换也就不会凭空起线程。
            app.state.worlds.workers_enabled = True
        yield
        if app.state.worlds is not None:
            # 等进行中的切换收尾，并禁止收尾之后再起线程。
            with app.state.worlds.lock:
                app.state.worlds.workers_enabled = False
        eng = app.state.engine
        if eng is not None:
            # D-P2-6: enter DRAINING on host shutdown — post-yield, NOT a signal
            # handler (a signal handler races uvicorn's own shutdown). Drain ENTRY
            # first (flips the write gate to reject), THEN stop the ingest worker
            # (in-flight remember() calls stop being picked up before the
            # maintenance tick — codex's specified order), THEN stop the
            # background tick. Capability-probed: tests inject partial-interface
            # engine doubles.
            if hasattr(eng, "begin_drain"):
                eng.begin_drain()
            if hasattr(eng, "stop_ingest_worker"):
                eng.stop_ingest_worker()
            if hasattr(eng, "stop_background_tick"):
                eng.stop_background_tick()

    app = FastAPI(title="Starling Dashboard", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.engine = engine
    app.state.worlds = WorldManager(app.state, registry_path) if registry_path else None

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

    @app.websocket("/ws/converse")
    async def ws_converse(ws: WebSocket) -> None:
        # Streaming converse (#37): a per-turn, per-client token stream. A NEW
        # endpoint, not the broadcast /ws — tokens are request-scoped and must
        # never fan out to every dashboard. Auth mirrors /ws (in-band token as
        # the first text frame). Protocol: client sends one JSON request
        # {message, provider?, holder?, interlocutor?, k?}; server replies
        # optionally {"type":"status","status":"grounding"} (once, before any
        # token: the model is writing a hidden evidence block first), then
        # {"type":"token","delta":...} ×N then {"type":"done", ...outcome}, or
        # {"type":"error","error":...}. The reply still persists (remember runs
        # after the stream) — disconnect mid-stream does not abort the turn.
        from starling.dashboard.engine import _LLMNotConfigured

        origin = ws.headers.get("origin", "")
        if not _ws_origin_allowed(origin, config.cors_origins):
            await ws.close(code=1008)
            return
        await ws.accept()
        if config.token:
            try:
                first = await ws.receive_text()
            except WebSocketDisconnect:
                return
            if not hmac.compare_digest(first, config.token):
                await ws.close(code=1008)
                return
        try:
            req = await ws.receive_json()
        except WebSocketDisconnect:
            return
        if not isinstance(req, dict) or not isinstance(req.get("message"), str) \
                or not req["message"]:
            await ws.send_json({"type": "error", "error": "empty_message"})
            await ws.close()
            return

        message = req["message"]
        holder = req.get("holder")
        interlocutor = req.get("interlocutor")
        provider = req.get("provider")
        try:
            k = max(1, min(int(req.get("k", 6) or 6), 50))
        except (TypeError, ValueError):
            k = 6

        eng = app.state.engine
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        done = object()
        box: dict = {}

        def on_token(delta: str) -> None:
            # Runs on the C++ worker thread (binding re-acquires the GIL per
            # delta). Only hand the delta to the loop — never touch the socket
            # or DB from here.
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "token", "delta": delta})

        def on_status(status: str) -> None:
            # Same queue as tokens, so call_soon_threadsafe ordering guarantees the
            # status frame reaches the client before the first token of the reply.
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "status", "status": status})

        def run_blocking() -> None:
            try:
                box["result"] = eng.converse_stream(
                    message, on_token=on_token, on_status=on_status, holder=holder,
                    interlocutor=interlocutor, k=k, provider=provider)
            except Exception as exc:  # surfaced to the client as an error frame
                box["error"] = exc
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, done)

        loop.run_in_executor(None, run_blocking)

        # Drain deltas until the worker signals done. call_soon_threadsafe
        # preserves order, so every delta is dequeued before `done`. If the
        # client vanishes we keep draining (cheap) so converse runs to completion
        # and the turn still persists — we just stop sending.
        disconnected = False
        while True:
            item = await queue.get()
            if item is done:
                break
            if disconnected:
                continue
            try:
                await ws.send_json(item)
            except Exception:  # noqa: BLE001 — client closed; finish server-side quietly
                disconnected = True
        if disconnected:
            return

        if "error" in box:
            code = "llm_not_configured" if isinstance(box["error"], _LLMNotConfigured) \
                else "converse_failed"
            await ws.send_json({"type": "error", "error": code})
            await ws.close()
            return
        result = box.get("result") or {}
        await ws.send_json({"type": "done", **result})
        # Mirror POST /converse: a consolidated turn tells other views to refresh.
        if result.get("statement_ids"):
            await app.state.ws_manager.broadcast(
                {"type": "statement_added",
                 "payload": {"statement_ids": result["statement_ids"]}})
        await ws.close()

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
