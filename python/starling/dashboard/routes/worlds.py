"""/api/worlds：世界注册表与快照（W1/W2）。

写操作经 WorldManager（世界管理锁内），统计只读查各世界库、不开引擎。
世界路径只来自服务端注册表：任何路由都不接受客户端传入的文件路径，请求里只有
世界名（C++ 侧按 ^[a-z0-9][a-z0-9_-]{0,31}$ 校验）和快照 id（只在注册表里查找）。
设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §9
"""
from __future__ import annotations

import logging
import os
from functools import partial

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from starling import _core
from starling.dashboard.world_manager import WorldSwitchError

logger = logging.getLogger(__name__)

# 错误码 → HTTP 状态。码本身由 C++（WorldStoreError）或 WorldManager（WorldSwitchError）
# 给出，前端据 detail 字符串显示提示（dashboard/web/src/lib/worlds.ts），所以 detail
# 一律原样回传错误码。未登记的码按 500 处理。
_STATUS = {
    "invalid_world_name": 400, "confirm_mismatch": 400,
    "world_not_found": 404, "snapshot_not_found": 404,
    "world_exists": 409, "world_protected": 409, "ingest_busy": 409,
    "snapshot_unsupported_backend": 409, "invalid_retention": 409,
    "world_tenant_mismatch": 409,
    "insufficient_disk": 507, "world_switching": 503,
    "world_open_failed": 500, "snapshot_failed": 500, "registry_corrupt": 500,
}


class CreateWorldBody(BaseModel):
    name: str
    label: str = ""


class SnapshotBody(BaseModel):
    note: str = ""


def _fail(code: str) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(code, 500), detail=code)


def _manager(request: Request):
    """取 WorldManager。库路径没有父目录（`:memory:` 等）时 create_app 不建注册表，
    app.state.worlds 为 None（或测试替身里根本没有这个属性）→ 503。"""
    mgr = getattr(request.app.state, "worlds", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="worlds_unavailable")
    return mgr


async def _run(fn, *args):
    """在工作线程里跑阻塞的 manager / 只读统计调用，把两类领域错误映射成 HTTP 错误，
    其余异常一律兜成 JSON 500 internal_error。

    切换（等线程停稳 + 重开库）和快照（VACUUM 整库）都是阻塞操作，不能占着事件循环。
    每个请求只发起一次 _run，所以同一请求不会并发调用 manager；跨请求的互斥由
    WorldManager 自己的锁负责，这里不再加锁。"""
    try:
        return await to_thread.run_sync(partial(fn, *args))
    except HTTPException:
        raise                                   # 工作函数里已经决定好的 HTTP 错误（如 404）
    except WorldSwitchError as exc:
        raise _fail(exc.code) from exc
    except _core.WorldStoreError as exc:
        raise _fail(_core.world_store_error_code(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — 注册表写不进去（磁盘满、目录不可写）等非领域异常
        # 不兜住的话 Starlette 回的是纯文本 500，前端按 JSON detail 解析会炸。异常文本可能
        # 带服务器路径，只进日志，不回给客户端。
        logger.exception("worlds route failed")
        raise HTTPException(status_code=500, detail="internal_error") from exc


def _world_row(name: str, entry: dict, snaps: list[dict], active: bool) -> dict:
    # 只读查库、不开引擎：列 N 个世界不用建 N 个引擎。库文件不存在（新建未激活）时全 0。
    # 库文件存在但读不出（损坏、被占）时 world_stats 抛 snapshot_failed：不能让一个坏世界
    # 拖垮整张列表（/worlds 页打不开，坏世界也就没法从界面删掉），该行统计置 0，
    # 并带 stats_error: true（只在出错的行上出现的附加字段）。
    stats_error = False
    try:
        stats = _core.world_stats(entry["db_path"], entry["tenant"])
    except _core.WorldStoreError as exc:
        logger.warning("world_stats failed for %s: %s", name, exc)
        stats = {"db_bytes": 0, "live_bytes": 0, "statements": 0, "engrams": 0}
        stats_error = True
    row = {"name": name, "label": entry.get("label", ""), "tenant": entry["tenant"],
           "created_at": entry.get("created_at", ""), "active": active,
           "db_bytes": stats["db_bytes"], "live_bytes": stats["live_bytes"],
           "statements": stats["statements"], "engrams": stats["engrams"],
           "snapshots": len(snaps),
           "snapshot_bytes": sum(s["size_bytes"] for s in snaps if not _snapshot_missing(s))}
    if stats_error:
        row["stats_error"] = True
    return row


def _snapshot_missing(snap: dict) -> bool:
    # 注册项还在、文件已不在（保存失败的补偿删掉了被保留策略清理过的旧文件、手工删除）。
    return not os.path.exists(snap["path"])


def _snapshot_row(snap: dict) -> dict:
    # 白名单：条目里的 path 是服务器上的绝对路径，不外露。文件缺失的条目照常列出（还能
    # 从界面删掉），size_bytes 记 0，并带 missing: true（只在缺失的行上出现的附加字段）。
    row = {key: snap[key] for key in ("id", "kind", "reason", "note", "created_at",
                                      "world_time", "size_bytes")}
    if _snapshot_missing(snap):
        row["size_bytes"] = 0
        row["missing"] = True
    return row


def _list_worlds(mgr) -> dict:
    reg = mgr.load()
    snapshots = reg.get("snapshots", {})
    rows = [_world_row(name, reg["worlds"][name], snapshots.get(name, []),
                       name == reg["active"])
            for name in sorted(reg["worlds"])]
    return {"active": reg["active"], "default": reg["default"],
            "snapshot_retention": reg["snapshot_retention"], "worlds": rows}


def _create_world(mgr, name: str, label: str) -> dict:
    entry = mgr.create(name, label)
    # 新世界不会是活动世界，也还没有快照；用 create 返回的条目而不是重读注册表，
    # 避免与并发的删除/切换错位。
    return _world_row(name, entry, [], False)


def _list_snapshots(mgr, name: str) -> dict:
    reg = mgr.load()
    if name not in reg["worlds"]:
        raise _fail("world_not_found")
    snaps = reg.get("snapshots", {}).get(name, [])
    # 注册表本就是最新在前；显式按 created_at 降序（稳定排序，同秒保持注册表顺序）。
    ordered = sorted(snaps, key=lambda snap: snap["created_at"], reverse=True)
    return {"snapshots": [_snapshot_row(snap) for snap in ordered]}


async def _broadcast(request: Request, kind: str, payload: dict) -> None:
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.broadcast({"type": kind, "payload": payload})


def build_worlds_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.get("/worlds")
    async def list_worlds(request: Request):
        mgr = _manager(request)
        return await _run(_list_worlds, mgr)

    @router.post("/worlds")
    async def create_world(request: Request, body: CreateWorldBody):
        mgr = _manager(request)
        return await _run(_create_world, mgr, body.name, body.label)

    @router.post("/worlds/{name}/activate")
    async def activate_world(request: Request, name: str):
        mgr = _manager(request)
        await _run(mgr.activate, name)
        await _broadcast(request, "world_switched", {"active": name})
        return {"active": name}

    @router.delete("/worlds/{name}")
    async def delete_world(request: Request, name: str, confirm: str = ""):
        mgr = _manager(request)
        if confirm != name:
            raise _fail("confirm_mismatch")      # 不碰 manager
        await _run(mgr.delete, name)
        return {"deleted": name}

    @router.get("/worlds/{name}/snapshots")
    async def list_snapshots(request: Request, name: str):
        mgr = _manager(request)
        return await _run(_list_snapshots, mgr, name)

    @router.post("/worlds/{name}/snapshots")
    async def create_snapshot(request: Request, name: str, body: SnapshotBody = SnapshotBody()):
        mgr = _manager(request)
        snap = await _run(mgr.take_snapshot, name, body.note)
        await _broadcast(request, "snapshot_created", {"world": name, "id": snap["id"]})
        return _snapshot_row(snap)

    @router.delete("/worlds/{name}/snapshots/{snapshot_id}")
    async def delete_snapshot(request: Request, name: str, snapshot_id: str):
        mgr = _manager(request)
        await _run(mgr.delete_snapshot, name, snapshot_id)
        return {"deleted": snapshot_id}

    return router
