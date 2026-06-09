"""Command routes — go through the DashboardEngine (single writer)."""
from __future__ import annotations

from datetime import datetime, timezone

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


class TickBody(BaseModel):
    now: str | None = None  # defaults to current UTC time at request handling


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
            r = eng.remember(body.text, holder=body.holder,
                             interlocutor=body.interlocutor, now=body.now)
        except _LLMNotConfigured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="llm_not_configured")
        await _broadcast(request, "statement_added", {"statement_ids": r["statement_ids"]})
        return r

    @router.post("/recall")
    async def recall(body: RecallBody, request: Request):
        eng = _engine(request)
        hits = eng.recall(body.query, perspective=body.perspective, k=body.k, mode=body.mode)
        out = [{"subject": h["row"].subject_id, "predicate": h["row"].predicate,
                "object": h["row"].object_value, "score": h["score"]} for h in hits]
        await _broadcast(request, "recall", {"n": len(out)})
        return {"results": out}

    @router.post("/tick")
    async def tick(body: TickBody, request: Request):
        eng = _engine(request)
        payload = eng.tick(body.now or _now_iso())
        await _broadcast(request, "tick", payload)
        if payload["fired"]:
            await _broadcast(request, "commitment_fired", {"fired": payload["fired"]})
        return payload

    @router.get("/working_set")
    async def working_set(request: Request, interlocutor: str, goal: str | None = None,
                          token_budget: int = 2000):
        eng = _engine(request)
        return eng.working_set(interlocutor, goal=goal, token_budget=token_budget)

    return router


async def _broadcast(request: Request, kind: str, payload: dict) -> None:
    mgr = getattr(request.app.state, "ws_manager", None)
    if mgr is not None:
        await mgr.broadcast({"type": kind, "payload": payload})
