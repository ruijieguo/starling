"""Command routes — go through the starling.Memory facade (single writer)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel


class RememberBody(BaseModel):
    text: str
    holder: str | None = None
    now: str | None = None


class RecallBody(BaseModel):
    query: str
    perspective: str = "first_person"
    k: int = 10
    mode: str = "semantic"


class TickBody(BaseModel):
    now: str = "2026-06-01T10:00:00Z"


def _memory(request: Request):
    """Return the engine-owning Memory, building it lazily from config.

    Single-process only: under `uvicorn --workers N` each worker would build
    its own Memory writing the same SQLite. Run one worker.
    """
    mem = request.app.state.memory
    if mem is None:
        from starling.memory import Memory, make_openai_llm
        c = request.app.state.config
        mem = Memory.open(c.db_path, agent=c.agent, tenant_id=c.tenant,
                          llm=make_openai_llm())
        request.app.state.memory = mem
    return mem


def build_commands_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.post("/remember")
    async def remember(body: RememberBody, request: Request):
        mem = _memory(request)
        r = mem.remember(body.text, holder=body.holder, now=body.now)
        await _broadcast(request, "statement_added", {"statement_ids": r.statement_ids})
        return {"engram_ref": r.engram_ref, "statement_ids": r.statement_ids,
                "outcome": r.outcome}

    @router.post("/recall")
    async def recall(body: RecallBody, request: Request):
        mem = _memory(request)
        hits = mem.recall(body.query, perspective=body.perspective, k=body.k, mode=body.mode)
        out = [{"subject": h["row"].subject_id, "predicate": h["row"].predicate,
                "object": h["row"].object_value, "score": h["score"]} for h in hits]
        await _broadcast(request, "recall", {"n": len(out)})
        return {"results": out}

    @router.post("/tick")
    async def tick(body: TickBody, request: Request):
        mem = _memory(request)
        st = mem.tick(body.now)
        payload = {"embedded": st.embedded, "fired": st.fired,
                   "broken": st.broken, "auto_withdrawn": st.auto_withdrawn}
        await _broadcast(request, "tick", payload)
        if st.fired:
            await _broadcast(request, "commitment_fired", {"fired": st.fired})
        return payload

    @router.get("/working_set")
    async def working_set(request: Request, interlocutor: str, goal: str | None = None,
                          token_budget: int = 2000):
        mem = _memory(request)
        cb = mem.render_working_set(interlocutor, goal=goal, token_budget=token_budget)
        return {"render": cb.render(),
                "blocks": [{"label": b.label, "content": b.content,
                            "tokens": b.token_estimate} for b in cb.blocks],
                "truncated": cb.truncated}

    return router


async def _broadcast(request: Request, kind: str, payload: dict) -> None:
    mgr = getattr(request.app.state, "ws_manager", None)
    if mgr is not None:
        await mgr.broadcast({"type": kind, "payload": payload})
