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

    @router.get("/brain_map")
    async def brain_map(request: Request):   # Phase 3 片 1 — 类脑 IA 落地页 9 脑区计数
        c = _cfg(request)
        return queries.brain_map(c.db_path, c.tenant)

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

    @router.get("/statement_search")
    async def statement_search(request: Request, q: str = "", limit: int = 20):
        # Phase 3 片 3 — 透视镜取镜:只读文本查找(副作用自由,不走语义召回)。
        c = _cfg(request)
        return queries.search_statements(c.db_path, c.tenant, q,
                                         limit=max(1, min(limit, 100)))

    @router.get("/provenance/{statement_id}")
    async def provenance(request: Request, statement_id: str, max_depth: int = 6):
        # Phase 3 片 3 — 透视镜:来源取证树(只读)。max_depth 钳制防递归滥用。
        c = _cfg(request)
        tree = queries.provenance(c.db_path, c.tenant, statement_id,
                                  max_depth=max(1, min(max_depth, 12)))
        if tree is None:
            raise HTTPException(status_code=404, detail="not_found")
        return tree

    return router
