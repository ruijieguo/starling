"""Read-only inspection routes (SQL-backed)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import partial

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request

from starling.dashboard import queries
from starling.dashboard.world_manager import WorldSwitchError, engine_lease


def _refuse_while_switching(request: Request) -> None:
    # 世界切换窗口里注册表可能已经指向新世界，config 还是旧的：此时的检视结果会把旧世界
    # 的数据显示在新世界的上下文里。回 503 world_switching。只读标志，不碰任何锁（本函数
    # 在事件循环上跑，不能阻塞）。
    worlds = getattr(request.app.state, "worlds", None)
    if worlds is not None and worlds.switching:
        raise HTTPException(status_code=503, detail="world_switching")


@contextmanager
def _leased_engine(request: Request):
    """读引擎内存态的路由用：持一份租约读完（不惰性建引擎，engine 可能是 None）。切换窗口
    内 → 503 world_switching，而不是让调用方把暂时的 None 当成「引擎还没建」。"""
    try:
        lease = engine_lease(request.app.state)
    except WorldSwitchError as exc:
        raise HTTPException(status_code=503, detail=exc.code) from exc
    with lease as engine:
        yield engine


def _metrics_to_dict(ms) -> dict:
    return {
        "outbox_lag_sequence": ms.outbox_lag_sequence,
        "subscriber_failure_rate": ms.subscriber_failure_rate,
        "extraction_queue_depth": ms.extraction_queue_depth,
        "projection_lag_seconds": ms.projection_lag_seconds,
        "runtime_event_loop_lag_ms": ms.runtime_event_loop_lag_ms,
        "vector_delete_lag": ms.vector_delete_lag,
        "erased_evidence_visible_count": ms.erased_evidence_visible_count,
    }


def _event_to_dict(e) -> dict:
    return {
        "previous_status": e.previous_status.name,
        "current_status": e.current_status.name,
        "trigger": e.trigger,
        "missing_capabilities": list(e.missing_capabilities),
        "metrics_snapshot": _metrics_to_dict(e.metrics_snapshot),
    }


def _default_since() -> str:
    # dogfood 子项 B(Task 2):metrics 路由 since 缺省 = 7 天前(与 bucket 缺省
    # 3600s 一起构成「近一周、按小时」的默认时间序列窗口)。
    return (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_inspect_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    def _cfg(request: Request):
        # 所有 SQL 检视路由都经这里取 config：切换窗口内一律 503（见 _refuse_while_switching）。
        _refuse_while_switching(request)
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
                         predicate: str = "", review_status: str = "",
                         consolidation_state: str = "", modality: str = "",
                         belief_order: str = "", subject_kind: str = "",
                         limit: int = 100, offset: int = 0):
        c = _cfg(request)
        return queries.statements(c.db_path, c.tenant, holder=holder,
                                  perspective=perspective, predicate=predicate,
                                  review_status=review_status,
                                  consolidation_state=consolidation_state,
                                  modality=modality,
                                  belief_order=belief_order,
                                  subject_kind=subject_kind,
                                  limit=limit, offset=offset)

    @router.get("/engrams")
    async def engrams(request: Request, source_kind: str = "", privacy_class: str = "",
                      erased: str = "", q: str = "", limit: int = 100, offset: int = 0):
        # T0a — 原始数据·证据浏览:engram(不可变原文证据)列表(只读派生查询)。
        c = _cfg(request)
        return queries.engrams_list(c.db_path, c.tenant, source_kind=source_kind,
                                    privacy_class=privacy_class, erased=erased, q=q,
                                    limit=limit, offset=offset)

    @router.get("/engram/{engram_id}")
    async def engram(request: Request, engram_id: str):
        # T0a — 单条 engram 详情:privacy-gated 预览(复用 provenance 同款抑制规则)+
        # 引用它的 statements 反查。
        c = _cfg(request)
        r = queries.engram_detail(c.db_path, c.tenant, engram_id)
        if r is None:
            raise HTTPException(status_code=404, detail="engram not found")
        return r

    @router.get("/personae")
    async def personae(request: Request):
        # T0d-2 — 新皮层·画像(Persona):containers WHERE kind='persona'(只读派生查询)。
        c = _cfg(request)
        return queries.personae(c.db_path, c.tenant)

    @router.get("/common_ground")
    async def common_ground(request: Request):
        # T0d-2 — 新皮层·共识(CommonGround):common_ground 五态,LEFT JOIN 带语句文本
        #(只读派生查询)。
        c = _cfg(request)
        return queries.common_ground(c.db_path, c.tenant)

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

    @router.get("/lifecycle")
    async def lifecycle(request: Request):   # Phase 3 片 4 — 生命周期(只读事件派生)
        c = _cfg(request)
        return queries.lifecycle(c.db_path, c.tenant)

    @router.get("/forecast")
    async def forecast(request: Request, limit: int = 200):
        # Phase 3 片 5 — 衰减预报:C++ forgetting_curve 只读投影(server now)。
        c = _cfg(request)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return queries.forecast(c.db_path, c.tenant, now=now,
                                limit=max(1, min(limit, 1000)))

    @router.get("/conflicts")
    async def conflicts(request: Request):
        c = _cfg(request)
        return queries.conflicts(c.db_path, c.tenant)

    @router.get("/gists")
    async def gists(request: Request):   # #38-C v2 — consolidation NORM gists (read-only)
        c = _cfg(request)
        return queries.gists(c.db_path, c.tenant)

    @router.get("/gist_members/{gist_id}")
    async def gist_members(request: Request, gist_id: str):   # #38-C v2 — gist lineage
        c = _cfg(request)
        return queries.gist_members(c.db_path, c.tenant, gist_id)

    @router.get("/queues")
    async def queues(request: Request):
        c = _cfg(request)
        return queries.queues(c.db_path, c.tenant)

    @router.get("/metrics/embed_depth")
    async def metrics_embed_depth(request: Request, since: str = "", bucket: int = 3600):
        # dogfood 子项 B(Task 2):embed 队列深度时间序列,读 Task 1 采样器写的
        # host metrics.db(与 dashboard.db 分离的文件;缺文件→空 series,不 500)。
        # bucket 钳制到 >=1(同 vitals/forecast/search 等兄弟路由的 limit 钳制一致)——
        # 0 或负值会在 _bucket 里对 bucket_s 取模,除零崩 500。
        c = _cfg(request)
        return queries.metrics_embed_depth(c.db_path, since or _default_since(), max(1, bucket))

    @router.get("/metrics/latency")
    async def metrics_latency(request: Request, since: str = "", bucket: int = 3600):
        # dogfood 子项 B(Task 2):抽取时延时间序列(p50/p95),派生 extraction_attempt。
        # bucket 钳制到 >=1,理由同 metrics_embed_depth。
        c = _cfg(request)
        return queries.metrics_latency(c.db_path, c.tenant, since or _default_since(), max(1, bucket))

    @router.get("/metrics/gist_quality")
    async def metrics_gist_quality(request: Request, since: str = "", bucket: int = 3600):
        # dogfood 子项 B(Task 3):gist 质量代理——funnel(gist_candidates→abstracted,
        # gated/failed 未持久化不派生)+ confidence/member/summary 分布。bucket 钳制到
        # >=1,理由同 metrics_embed_depth(否则 _bucket 对 bucket_s 取模会除零 500)。
        c = _cfg(request)
        return queries.metrics_gist_quality(c.db_path, c.tenant, since or _default_since(),
                                            max(1, bucket))

    @router.get("/vitals")
    async def vitals(request: Request, limit: int = 50):
        c = _cfg(request)
        # Z-suffixed to match the repo's stored-timestamp convention (engine.py
        # / commands.py _now_iso). The overdue-window filter is a STRING compare
        # against Z-suffixed close_deadline values, so a "+00:00" suffix here
        # would be a latent boundary bug.
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return queries.vitals(c.db_path, c.tenant, now=now,
                              list_limit=max(1, min(limit, 500)))   # clamp(同 forecast/search 一致)

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

    @router.get("/cascade_preview/{statement_id}")
    async def cascade_preview(request: Request, statement_id: str, max_depth: int = 6):
        # 片 6 — 级联预览:遗忘前看会波及哪些派生后代(只读 inform-only)。max_depth 钳制。
        # 唯一会全表扫(反向派生边无索引)的检视路由 → 丢线程,避免大租户下阻塞事件循环。
        c = _cfg(request)
        preview = await to_thread.run_sync(partial(
            queries.cascade_preview, c.db_path, c.tenant, statement_id,
            max_depth=max(1, min(max_depth, 12))))
        if preview is None:
            raise HTTPException(status_code=404, detail="not_found")
        return preview

    @router.get("/runtime_health")
    async def runtime_health(request: Request):
        with _leased_engine(request) as eng:
            if eng is None:
                # health/events are in-memory; with no live engine there is nothing to read.
                raise HTTPException(status_code=503, detail="engine not initialized")
            return {
                "status": eng.health().name,
                "events": [_event_to_dict(e) for e in eng.events()],
            }

    @router.get("/ingest_status")
    async def ingest_status(request: Request):
        # dogfood 子项 A(Task 3):spool 队列深度 —— 引擎内存态(remember 累计
        # 耗时计数器 ingest_remember_ms_total),无引擎则无可读(同
        # runtime_health 的能力探测模式)。
        with _leased_engine(request) as eng:
            if eng is None:
                raise HTTPException(status_code=503, detail="engine not initialized")
            return eng.ingest_status()

    return router
