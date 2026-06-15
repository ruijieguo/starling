"""Command routes — go through the DashboardEngine (single writer).

Engine calls run real network I/O (LLM extraction / embedding, with C++-side
retry backoff up to tens of seconds), so handlers offload them to a worker
thread via anyio.to_thread — running them inline on the event loop would
freeze every other request and the WS heartbeat for the whole call.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import partial

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 'Z' string (tick default)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RememberBody(BaseModel):
    text: str
    holder: str | None = None
    interlocutor: str | None = None
    now: str | None = None


class RecallBody(BaseModel):
    query: str
    perspective: str = "first_person"
    k: int = 10
    mode: str = "semantic"
    intent: str | None = None    # 非空 → 走 RetrievalPlanner(P3.a1)
    target: str | None = None    # BELIEF_OF_OTHER / COMMON_GROUND 对方


class TickBody(BaseModel):
    now: str | None = None  # defaults to current UTC time at request handling


class ForgetBody(BaseModel):
    ids: list[str]
    now: str | None = None  # None → MemoryCore resolves to current UTC time


def _engine(request: Request):
    """Return the DashboardEngine, building it lazily from config.

    Single-process only: under `uvicorn --workers N` each worker would build
    its own engine writing the same SQLite. Run one worker.
    """
    eng = request.app.state.engine
    if eng is None:
        from starling.dashboard.engine import DashboardEngine
        eng = DashboardEngine(request.app.state.config)
        request.app.state.engine = eng
    return eng


def build_commands_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.post("/remember")
    async def remember(body: RememberBody, request: Request):
        from starling.dashboard.engine import _LLMNotConfigured
        eng = _engine(request)
        try:
            r = await to_thread.run_sync(partial(
                eng.remember, body.text, holder=body.holder,
                interlocutor=body.interlocutor, now=body.now))
        except _LLMNotConfigured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="llm_not_configured")
        await _broadcast(request, "statement_added", {"statement_ids": r["statement_ids"]})
        return r

    @router.post("/recall")
    async def recall(body: RecallBody, request: Request):
        eng = _engine(request)
        if body.intent:
            payload = await to_thread.run_sync(partial(
                eng.plan_query, body.query, intent=body.intent,
                target=body.target, k=body.k))
            await _broadcast(request, "recall", {"n": len(payload["results"])})
            return payload
        hits = await to_thread.run_sync(partial(
            eng.recall, body.query, perspective=body.perspective, k=body.k, mode=body.mode))
        out = [{"subject": h["row"].subject_id, "predicate": h["row"].predicate,
                "object": h["row"].object_value, "score": h["score"]} for h in hits]
        await _broadcast(request, "recall", {"n": len(out)})
        return {"results": out}

    @router.post("/tick")
    async def tick(body: TickBody, request: Request):
        eng = _engine(request)
        payload = await to_thread.run_sync(eng.tick, body.now or _now_iso())
        await _broadcast(request, "tick", payload)
        if payload["fired"]:
            await _broadcast(request, "commitment_fired", {"fired": payload["fired"]})
        return payload

    @router.get("/working_set")
    async def working_set(request: Request, interlocutor: str, goal: str | None = None,
                          token_budget: int = 2000):
        eng = _engine(request)
        return await to_thread.run_sync(partial(
            eng.working_set, interlocutor, goal=goal, token_budget=token_budget))

    @router.post("/forget")
    async def forget(body: ForgetBody, request: Request):
        eng = _engine(request)
        r = await to_thread.run_sync(partial(eng.forget, body.ids, now=body.now))
        await _broadcast(request, "statement_forgotten", r)
        return r

    return router


async def _broadcast(request: Request, kind: str, payload: dict) -> None:
    mgr = getattr(request.app.state, "ws_manager", None)
    if mgr is not None:
        await mgr.broadcast({"type": kind, "payload": payload})
