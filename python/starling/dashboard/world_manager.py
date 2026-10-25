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
from contextlib import contextmanager
from datetime import datetime, timezone

from starling import _core
from starling.dashboard.engine import DashboardEngine

logger = logging.getLogger(__name__)


class WorldSwitchError(Exception):
    """code: "world_not_found" | "ingest_busy" | "world_open_failed"
    | "snapshot_unsupported_backend" | "world_switching" """

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


def _same_db(left: str, right: str) -> bool:
    """两个库路径是不是同一个文件。注册表存的是绝对路径，但 live config 可能带着另一种
    写法（符号链接目录、相对路径），所以按真实路径比，而不是字符串。"""
    return os.path.realpath(left) == os.path.realpath(right)


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
        # 切换窗口标志：activate 动引擎期间为 True（见 _switch_window）。路由据此对新请求
        # 回 503 world_switching，而不是在 engine 暂时为 None 时按旧 config 惰性重建引擎。
        # 读它不加锁（事件循环上读，不能阻塞）；写它只在 _gate 内。
        self.switching = False
        self._gate = threading.Lock()

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

    @contextmanager
    def engine_gate(self):
        """路由里惰性建引擎的门：切换中 → 抛 WorldSwitchError("world_switching")；
        否则放行，并在 with 体内（检查 engine、必要时建引擎、写回 app.state）阻止切换
        置位——切换要等这里的惰性构建完成，之后才读 app.state.engine，所以不会漏掉
        一个正在建的引擎，建完的旧配置引擎也不会在切换之后才写回去。

        _gate 只被「置/清标志」和这里的惰性构建持有，从不与管理锁嵌套持有的方向相反
        （切换先拿管理锁再拿 _gate，这里只拿 _gate），所以不会死锁。它不是管理锁：
        管理锁在快照期间会被占上几秒，而调用方在事件循环上，不能被它阻塞。"""
        with self._gate:
            if self.switching:
                raise WorldSwitchError("world_switching")
            yield

    @contextmanager
    def _switch_window(self):
        """activate 动引擎的整个区间。进入时等在途的惰性构建完成，之后新请求一律 503；
        任何退出路径（成功、ingest_busy、world_open_failed）都清标志。"""
        with self._gate:
            self.switching = True
        try:
            yield
        finally:
            with self._gate:
                self.switching = False

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
        没停下，状态不前进）、world_open_failed（新世界打不开，或注册表写不进去，
        都已回到旧世界）。

        发布顺序：开新库 → 存注册表 → 发布 config/engine 并起线程。注册表是「当前是
        哪个世界」的唯一持久记录，必须先落盘再对外生效：若先发布再存、存又失败
        （磁盘满、目录不可写），就会出现注册表说 A、引擎实际在写 B 的分叉——此后
        「切回 A」被当成 no-op，写入全进 B，B 的目录还能被删掉。

        顺序是「先 quiesce，再拿引擎锁」，不能反过来：tick 线程在 tick() 与
        _sample_backpressure() 之间、摄入线程在逐块 remember() 之间都会放开引擎锁再
        重新去拿，切换线程若持着引擎锁 join，线程卡在拿锁上退不出，必然等满 5 秒后
        误报 ingest_busy。线程停稳之后再拿引擎锁，只剩一个作用：等在飞的路由请求
        （它们持锁）结束。

        关键事实：DashboardEngine.close() 不释放 C++ SQLite 句柄，只有丢掉最后一个
        引用并 gc.collect() 才会。所以这里丢引用，并断言旧 Runtime 的弱引用已失效，
        没失效只记 warning（见下）。

        切换窗口：从开始动引擎到新引擎发布（或回滚完成）之间 `self.switching` 为 True，
        此时 app.state.engine 暂时是 None 而 config 还是旧的。路由的惰性建引擎
        （commands._engine）和 inspect 的引擎读取据此回 503 world_switching，否则会按旧
        config 造出旧世界的引擎写回 app.state，与注册表、config 错位。标志的置位会等
        在途的惰性构建完成（见 engine_gate），所以不会漏掉一个正在建的引擎。

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
            # 已是活动世界才 no-op，且要看 live config 而不只看注册表的 active：两者一旦
            # 分叉（注册表说 A、引擎实际在写 B），只信注册表就会把「切回 A」当成已完成，
            # 之后的写入全落进 B。
            if (reg["active"] == name and self._state.engine is not None
                    and _same_db(self._state.config.db_path, reg["worlds"][name]["db_path"])):
                return
            with self._switch_window():
                self._swap_engine(reg, name)

    def _swap_engine(self, reg: dict, name: str) -> None:
        """activate 的主体，调用时已持管理锁并处于切换窗口内（标志已置位）。
        engine 必须在标志置位之后才读：置位会等在途的惰性构建完成。"""
        old_engine = self._state.engine
        old_cfg = self._state.config
        new_cfg = dataclasses.replace(old_cfg)
        new_cfg.db_path = reg["worlds"][name]["db_path"]
        new_cfg.tenant = reg["worlds"][name]["tenant"]
        if old_engine is not None:
            if not old_engine.quiesce():
                # 后台线程没停下：恢复后台线程，状态不前进。码保持 ingest_busy（前端按
                # 这个字符串映射），detail 点名实际卡住的线程。
                stuck = "/".join(getattr(old_engine, "quiesce_stuck", ())) or "background"
                self._restart_workers(old_engine)
                raise WorldSwitchError("ingest_busy", f"{stuck} thread did not stop in 5s")
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
            self._rollback(old_cfg, str(exc), exc)           # 必抛
        # 先落盘再发布。新引擎此时还没起线程；存失败就丢掉它（丢引用 + gc 释放它的
        # C++ 写连接），再走与「新库打不开」同一条回滚路径，码仍是 world_open_failed，
        # 前端「已留在原世界」的提示依然成立。
        try:
            self.save(_core.world_set_active(reg, name))
        except Exception as exc:
            new_engine = None
            gc.collect()
            self._rollback(old_cfg, f"registry write failed: {exc}", exc)   # 必抛
        self._state.config = new_cfg
        self._state.engine = new_engine
        self._start_workers(new_engine, new_cfg)

    def _rollback(self, old_cfg, detail: str, cause: Exception) -> None:
        """新世界没能生效：回到旧世界并抛 world_open_failed。回滚本身也可能失败（旧库
        同样打不开）——此时 engine 留 None、config 仍是旧世界，路由之后惰性重建；
        对调用方仍然是 WorldSwitchError（路由只映射它），不让裸异常漏出去。"""
        try:
            self._state.engine = DashboardEngine(old_cfg)
        except Exception as rollback_exc:
            self._state.engine = None
            raise WorldSwitchError(
                "world_open_failed",
                f"{detail}; rollback to the previous world also failed: {rollback_exc}",
            ) from cause
        self._start_workers(self._state.engine, old_cfg)
        raise WorldSwitchError("world_open_failed", detail) from cause

    def create(self, name: str, label: str) -> dict:
        with self.lock:
            reg = self.load()
            out = _core.world_create(reg, self.registry_dir, name, label, _now_iso())
            self.save(out["registry"])
            entry = dict(out["world"])
            entry["name"] = name
            return entry

    def delete(self, name: str) -> None:
        """删世界（目录整个删掉）。C++ 已拒绝删 default 和注册表里的活动世界；这里再按
        live config 补一道：引擎此刻正在写的库，不论注册表怎么说都不能删——删了目录，
        进程仍在往已 unlink 的 inode 里写，重启后数据就没了。"""
        with self.lock:
            reg = self.load()
            entry = reg["worlds"].get(name)
            if entry is not None and _same_db(self._state.config.db_path, entry["db_path"]):
                raise _core.WorldStoreError(
                    f"world_protected: world '{name}' is the one the live engine is writing to")
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
