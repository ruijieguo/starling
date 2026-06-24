"""Read-only inspection routes (SQL-backed)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from starling.dashboard import queries


def build_inspect_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    def _cfg(request: Request):
        return request.app.state.config

    @router.get("/overview")
    async def overview(request: Request):
        c = _cfg(request)
        return queries.overview(c.db_path, c.tenant)

    @router.get("/statements")
    async def statements(request: Request, holder: str = "", perspective: str = "",
                         predicate: str = "", limit: int = 100, offset: int = 0):
        c = _cfg(request)
        return queries.statements(c.db_path, c.tenant, holder=holder,
                                  perspective=perspective, predicate=predicate,
                                  limit=limit, offset=offset)

    @router.get("/cognizers")
    async def cognizers(request: Request):
        c = _cfg(request)
        return queries.cognizers(c.db_path, c.tenant)

    @router.get("/commitments")
    async def commitments(request: Request):
        c = _cfg(request)
        return queries.commitments(c.db_path, c.tenant)

    @router.get("/replay")
    async def replay(request: Request):
        c = _cfg(request)
        return queries.replay(c.db_path, c.tenant)

    @router.get("/conflicts")
    async def conflicts(request: Request):
        c = _cfg(request)
        return queries.conflicts(c.db_path, c.tenant)

    @router.get("/queues")
    async def queues(request: Request):
        c = _cfg(request)
        return queries.queues(c.db_path, c.tenant)

    @router.get("/vitals")
    async def vitals(request: Request, limit: int = 50):
        c = _cfg(request)
        # Z-suffixed to match the repo's stored-timestamp convention (engine.py
        # / commands.py _now_iso). The overdue-window filter is a STRING compare
        # against Z-suffixed close_deadline values, so a "+00:00" suffix here
        # would be a latent boundary bug.
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return queries.vitals(c.db_path, c.tenant, now=now, list_limit=limit)

    @router.get("/statement/{statement_id}")
    async def statement(request: Request, statement_id: str):
        c = _cfg(request)
        row = queries.statement_by_id(c.db_path, c.tenant, statement_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found")
        return row

    return router
