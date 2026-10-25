"""世界管理：注册表读改写 + 世界切换时的引擎生命周期（W1）。

注册表、快照、保留策略都在 C++（`_core.world_*`）；这里只做 Python 才能做的事：
切换时重建 DashboardEngine（停线程、释放 C++ 写连接、开新库、失败回滚）。
设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §8
"""
from __future__ import annotations

import dataclasses
import gc
import logging
import os
import threading
import weakref
from datetime import datetime, timezone

from starling import _core
from starling.dashboard.engine import DashboardEngine

logger = logging.getLogger(__name__)


class WorldSwitchError(Exception):
    """code: "world_not_found" | "ingest_busy" | "world_open_failed"
    | "snapshot_unsupported_backend" """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def registry_path_for(config) -> str:
    env = os.environ.get("STARLING_WORLDS_REGISTRY")
    if env:
        return env
    return os.path.join(os.path.dirname(config.db_path), "worlds.json")


def bootstrap_worlds(config):
    """建立/读取注册表，并把 config 原地改写成活动世界（db_path + tenant）。

    返回注册表路径。库路径没有父目录（`:memory:`、空串、裸文件名）时无处安放
    注册表，整个跳过并返回 None：不写任何文件、不改 config，调用方据此让
    `app.state.worlds` 保持 None（路由回 503 worlds_unavailable）。这个判断必须先于
    STARLING_WORLDS_REGISTRY 环境变量，否则测试里的 :memory: 会被登记成
    `<cwd>/:memory:` 这个默认世界。"""
    db_path = config.db_path
    if not db_path or db_path == ":memory:" or not os.path.dirname(db_path):
        return None
    registry_path = registry_path_for(config)
    _core.world_ensure_registry(registry_path, config.db_path, config.tenant)
    reg = _core.world_load_registry(registry_path)
    entry = reg["worlds"][reg["active"]]
    if (os.path.abspath(config.db_path) != entry["db_path"]
            or config.tenant != entry["tenant"]):
        # 注册表优先于 starling.json / STARLING_DASH_DB：已存在的注册表里 default 的路径
        # 不会被改写。静默换库有写错库的风险，至少让它在日志里可见。
        logger.warning("worlds registry %s overrides config: db_path %s -> %s, tenant %s -> %s",
                       registry_path, config.db_path, entry["db_path"],
                       config.tenant, entry["tenant"])
    config.db_path = entry["db_path"]
    config.tenant = entry["tenant"]
    return registry_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorldManager:
    def __init__(self, app_state, registry_path: str) -> None:
        self._state = app_state
        self.registry_path = registry_path
        self.registry_dir = os.path.dirname(os.path.abspath(registry_path))
        self.lock = threading.RLock()
        self.workers_enabled = False
        self.on_tick = None

    def load(self) -> dict:
        return _core.world_load_registry(self.registry_path)

    def save(self, reg: dict) -> None:
        _core.world_save_registry(self.registry_path, reg)

    def active_world(self) -> dict:
        reg = self.load()
        entry = dict(reg["worlds"][reg["active"]])
        entry["name"] = reg["active"]
        return entry

    def persistable_config(self, cfg):
        reg = self.load()
        default = reg["worlds"][reg["default"]]
        return dataclasses.replace(cfg, db_path=default["db_path"], tenant=default["tenant"])

    def _start_workers(self, engine, cfg) -> None:
        if not self.workers_enabled:
            return
        if cfg.tick_interval_s > 0:
            engine.start_background_tick(cfg.tick_interval_s, self.on_tick)
        engine.start_ingest_worker()

    def _restart_workers(self, engine) -> None:
        self._start_workers(engine, self._state.config)

    def activate(self, name: str) -> None:
        """切换活动世界（spec §8.1）：停线程 → 等在飞请求 → 丢旧引擎 → 建新引擎。

        抛 WorldSwitchError：world_not_found（未登记）、ingest_busy（后台线程 5 秒内
        没停下，状态不前进）、world_open_failed（新世界打不开，已回到旧世界）。

        顺序是「先 quiesce，再拿引擎锁」，不能反过来：tick 线程在 tick() 与
        _sample_backpressure() 之间、摄入线程在逐块 remember() 之间都会放开引擎锁再
        重新去拿，切换线程若持着引擎锁 join，线程卡在拿锁上退不出，必然等满 5 秒后
        误报 ingest_busy。线程停稳之后再拿引擎锁，只剩一个作用：等在飞的路由请求
        （它们持锁）结束。

        关键事实：DashboardEngine.close() 不释放 C++ SQLite 句柄，只有丢掉最后一个
        引用并 gc.collect() 才会。所以这里丢引用，并断言旧 Runtime 的弱引用已失效，
        没失效只记 warning（见下）。

        已知限制：/ws/converse 的锁外生成阶段持有旧引擎的引用，切换只等得到持锁段。
        若切换时恰有一轮对话在锁外生成，切换会先返回；这轮对话在旧引擎上完成提交
        （写进旧世界，归属正确），旧 Runtime 在它结束前不会被回收，所以 rt_ref()
        非空只记 warning、不报错。SQLite 本身允许多连接，即便立刻切回同一世界也不会
        损坏数据，只是暂时违反「进程内单写连接」的约定。
        """
        with self.lock:
            reg = self.load()
            if name not in reg["worlds"]:
                raise WorldSwitchError("world_not_found", name)
            if reg["active"] == name and self._state.engine is not None:
                return
            old_engine = self._state.engine
            old_cfg = self._state.config
            new_cfg = dataclasses.replace(old_cfg)
            new_cfg.db_path = reg["worlds"][name]["db_path"]
            new_cfg.tenant = reg["worlds"][name]["tenant"]
            if old_engine is not None:
                if not old_engine.quiesce():
                    # 摄入线程没停下：恢复后台线程，状态不前进
                    self._restart_workers(old_engine)
                    raise WorldSwitchError("ingest_busy", "ingest worker did not stop in 5s")
                with old_engine._lock:           # 等在飞请求结束
                    pass
                rt_ref = weakref.ref(old_engine._rt)
                self._state.engine = None
                old_engine = None
                gc.collect()
                if rt_ref() is not None:
                    # C++ 连接没释放：同进程里会暂时有第二条写连接
                    logger.warning("old runtime still referenced after switch")
            try:
                new_engine = DashboardEngine(new_cfg)
            except Exception as exc:
                # 新世界打不开：回到旧世界
                self._state.engine = DashboardEngine(old_cfg)
                self._start_workers(self._state.engine, old_cfg)
                raise WorldSwitchError("world_open_failed", str(exc)) from exc
            self._state.config = new_cfg
            self._state.engine = new_engine
            self._start_workers(new_engine, new_cfg)
            reg = _core.world_set_active(reg, name)
            self.save(reg)

    def create(self, name: str, label: str) -> dict:
        with self.lock:
            reg = self.load()
            out = _core.world_create(reg, self.registry_dir, name, label, _now_iso())
            self.save(out["registry"])
            entry = dict(out["world"])
            entry["name"] = name
            return entry

    def delete(self, name: str) -> None:
        with self.lock:
            reg = self.load()
            self.save(_core.world_delete(reg, self.registry_dir, name))

    def take_snapshot(self, name: str, note: str) -> dict:
        with self.lock:
            if getattr(self._state.config, "vector_backend", "sqlite") == "zvec":
                raise WorldSwitchError("snapshot_unsupported_backend", "vector_backend=zvec")
            reg = self.load()
            out = _core.world_take_snapshot(reg, name, "manual", "manual", note)
            self.save(out["registry"])
            return out["snapshot"]

    def delete_snapshot(self, name: str, snapshot_id: str) -> None:
        with self.lock:
            reg = self.load()
            self.save(_core.world_delete_snapshot(reg, name, snapshot_id))
