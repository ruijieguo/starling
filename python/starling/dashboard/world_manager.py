"""世界管理：注册表读改写 + 世界切换与回滚时的引擎生命周期（W1、W3）。

注册表、快照、保留策略、租户不变式、回滚的顺序与原子性都在 C++（`_core.world_*`）；这里
只做 Python 才能做的事：切换时重建 DashboardEngine（停线程、等在飞请求、释放 C++ 写连接、
开新库、失败回滚），回滚活动世界时同样停引擎、确认旧 Runtime 已回收、调 C++、再重建。
设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §5.1、§8

引擎租约（lease）
-----------------
每个用到引擎的请求在整个生命周期里持一份租约：线程池排队、remember 的锁外抽取、
/ws/converse 的锁外生成、最后的提交，全在租约之内。切换先置 switching（此后新租约一律
拒绝，路由回 503 world_switching），再等在途租约归零，然后才丢旧引擎。只等引擎锁是不够
的：锁外阶段不持引擎锁，旧实现会在这类请求还在飞时就完成切换，请求随后写进旧世界，
旧 Runtime 也一直活着，切回原世界就是同一个库上两条写连接。

租约按请求发放，不按 WebSocket 连接：长连接的对话 socket 在两轮之间不持租约，不挡切换。
后台 tick / 摄入线程不是租约，切换用 quiesce 停它们。

本进程里打开活动世界库文件的每条路径，从打开之前到关闭之后都持一份租约（只读的也一样）：
检视 SQL 路由（routes/inspect.py）与 GET /api/worlds 的统计（routes/worlds.py）都是。回滚把同一
路径上的 inode 换掉，一条在替换之前打开了旧 inode、替换之后才第一次读的只读连接会按路径打开
新库的 -shm，在同进程里认为自己是第一个连接，把引擎正在用的 wal-index 截断重建。C++ 的连接
探测（world_in_use）看不见这种「打开了还没读」的连接，在 delete 模式的库上连读过库的闲置连接
也看不见（实测表见 rollback 的文档），它只是纵深防御，所以要靠租约：回滚等租约归零才动文件。

锁顺序（全局唯一，任何代码都不得反向持有）
------------------------------------------
  1. manager.lock（RLock）：activate / create / delete / take_snapshot / delete_snapshot /
     rollback / purge_archives，以及 lifespan 关停。可能被占几秒到几十秒（VACUUM、复制快照、
     等租约），所以事件循环上的代码从不拿它。C++ 要求按世界串行化回滚，rollback 全程持它
     即满足。
  2. manager._gate（Lock，短）：只保护 switching 标志和租约计数，持有期间不做任何 I/O、
     不建引擎、不拿别的锁。_drained 是建在它上面的 Condition：切换等租约归零时 wait 会
     放开 _gate，所以「等租约」从不持着 _gate。
  3. manager._build_lock（Lock）：惰性建引擎（engine 还是 None 时第一条请求来建）。只由已
     拿到租约的请求在放开 _gate 之后持有；切换从不拿它（切换等租约归零时没有人在建）。
  4. engine._lock（RLock，DashboardEngine 内部）：由持租约的请求和后台线程持有。切换从不
     拿它：quiesce 在不持引擎锁的情况下 join 后台线程（线程分段拿锁，持锁 join 会卡住）。
  5. supervisor 互斥锁（C++ Runtime 内部）：只在持 engine._lock 时取（见 engine.py 的
     _sample_backpressure 一带），从不反向。

  即 manager.lock → _gate → _build_lock → engine._lock → supervisor。
  持租约的代码不得去拿 manager.lock：切换持着 manager.lock 等租约归零，反过来就是死锁
  （超时后 ingest_busy）。
"""
from __future__ import annotations

import dataclasses
import gc
import logging
import os
import threading
import time
import weakref
from contextlib import contextmanager
from datetime import datetime, timezone

from starling import _core
from starling.dashboard.engine import DashboardEngine

logger = logging.getLogger(__name__)

# 切换等在途请求（租约）归零的上限。超时：清标志、恢复旧引擎的后台线程、回 ingest_busy。
_LEASE_DRAIN_TIMEOUT_S = 30.0
# 丢掉旧引擎后等旧 Runtime 被回收的宽限：异常回溯、刚返回的栈帧可能还短暂引用着它。
_RUNTIME_RELEASE_GRACE_S = 1.0


class WorldSwitchError(Exception):
    """code: "world_not_found" | "ingest_busy" | "world_open_failed"
    | "world_tenant_mismatch" | "world_switching" | "rollback_reopen_failed" """

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
    if reg["active"] != reg["default"]:
        # 重启时活动世界不是默认世界：它的引擎马上会按这里的 config 建起来（run_dashboard.py
        # 急切建、lifespan 或首个命令惰性建），绕过了切换时的租户校验。在这里补上，不满足
        # 就拒绝启动（world_tenant_mismatch），而不是带着别的租户的数据开始写。
        # 默认世界（原地的 dashboard.db）不在此校验：它早于世界管理，既有部署与测试里可以
        # 按租户过滤地存多个租户；切换回默认世界时仍按 §2.1 校验。
        _core.world_verify_tenant(entry["db_path"], entry["tenant"])
    config.db_path = entry["db_path"]
    config.tenant = entry["tenant"]
    return registry_path


def _same_db(left: str, right: str) -> bool:
    """两个库路径是不是同一个文件。注册表存的是绝对路径，但 live config 可能带着另一种
    写法（符号链接目录、相对路径），所以按真实路径比，而不是字符串。"""
    return os.path.realpath(left) == os.path.realpath(right)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EngineLease:
    """一份引擎租约。`with lease as engine:` 或手动 `release()`；release 幂等。

    release 先丢掉自己对引擎的引用、再归还计数：计数一归零，切换就会丢旧引擎并断言旧
    Runtime 已回收，租约对象本身（可能还挂在某个栈帧或异常回溯上）不能再钉住它。
    调用方自己的局部变量要在 release 之前清掉（见 /ws/converse、/api/config）。"""

    __slots__ = ("_owner", "engine")

    def __init__(self, owner, engine) -> None:
        self._owner = owner          # WorldManager；无注册表（:memory:）时为 None，不计数
        self.engine = engine

    def release(self) -> None:
        owner, self._owner = self._owner, None
        self.engine = None
        if owner is not None:
            owner._return_lease()

    def __enter__(self):
        return self.engine

    def __exit__(self, *_exc) -> None:
        self.release()


def engine_lease(state, *, build=None) -> EngineLease:
    """路由取引擎的唯一入口。有 WorldManager 时经它发租约（切换中抛
    WorldSwitchError("world_switching")）；没有（:memory: 等无注册表的库）时没有切换，
    返回不计数的租约。build(config) -> engine 给出时，engine 还是 None 就惰性建一个并写回
    app.state（命令路由用）；不给时原样返回 app.state.engine（可能是 None）。"""
    worlds = getattr(state, "worlds", None)
    if worlds is not None:
        return worlds.lease(build=build)
    engine = state.engine
    if engine is None and build is not None:
        engine = build(state.config)
        state.engine = engine
    return EngineLease(None, engine)


class WorldManager:
    def __init__(self, app_state, registry_path: str) -> None:
        self._state = app_state
        self.registry_path = registry_path
        self.registry_dir = os.path.dirname(os.path.abspath(registry_path))
        self.lock = threading.RLock()
        self.workers_enabled = False
        self.on_tick = None
        # 切换窗口标志：activate 与活动世界回滚动引擎期间为 True（见 _switch_window）。此时新
        # 租约一律拒绝，路由回 503 world_switching，而不是在 engine 暂时为 None 时按旧 config
        # 惰性重建引擎。写它和发租约只在 _gate 内；rollback 开头与 GET /api/config 不加锁读。
        self.switching = False
        self._gate = threading.Lock()
        self._drained = threading.Condition(self._gate)   # 租约归零时 notify
        self._leases = 0
        self._build_lock = threading.Lock()
        # 切换后没能回收的旧 Runtime：[(它打开的库路径, 弱引用)]。它还开着那个库的写连接。
        # 那个库若被回滚替换，这条连接会继续写旧 inode 和它已被 unlink 的 WAL：这些写入在
        # 恢复出来的库里没有，静默丢失，归档（旧 inode 唯一剩下的名字）也可能被改动。关掉它时
        # SQLite 发现主文件已被换掉，不做 checkpoint、不删文件，恢复出来的库不受影响（实测）。
        # rollback 据此拒绝。只在 manager.lock 内读写。
        self._leaked_runtimes: list[tuple[str, weakref.ref]] = []

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

    def lease(self, *, build=None) -> EngineLease:
        """发一份引擎租约（见模块文档）。切换中抛 WorldSwitchError("world_switching")。

        build 见 engine_lease。计数先于惰性构建增加：切换置位后等租约归零，也就等到了
        正在进行的构建，构建完写回的引擎会被切换当作旧引擎接手，不会在切换之后才冒出来。
        _gate 只在计数时短暂持有（调用方可能在事件循环上），构建在 _build_lock 下进行。"""
        with self._gate:
            if self.switching:
                raise WorldSwitchError("world_switching")
            self._leases += 1
        lease = EngineLease(self, None)
        try:
            engine = self._state.engine
            if engine is None and build is not None:
                with self._build_lock:
                    engine = self._state.engine
                    if engine is None:
                        engine = build(self._state.config)
                        self._state.engine = engine
            lease.engine = engine
        except BaseException:
            lease.release()
            raise
        return lease

    def _return_lease(self) -> None:
        with self._gate:
            self._leases -= 1
            if self._leases == 0:
                self._drained.notify_all()

    def _drain_leases(self) -> None:
        """等在途租约归零（切换窗口内调用，标志已置位，不会再有新租约）。超过
        _LEASE_DRAIN_TIMEOUT_S 抛 ingest_busy。Condition.wait 放开 _gate，不挡归还。"""
        deadline = time.monotonic() + _LEASE_DRAIN_TIMEOUT_S
        with self._gate:
            while self._leases > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorldSwitchError(
                        "ingest_busy", f"{self._leases} request(s) still in flight")
                self._drained.wait(remaining)

    @contextmanager
    def _switch_window(self):
        """activate 动引擎的整个区间：进入时置标志（此后新租约一律拒绝），任何退出路径
        （成功、ingest_busy、world_open_failed、world_tenant_mismatch）都清标志。"""
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
        """切换活动世界（spec §8.1）：校验租户 → 停线程 → 等在飞请求 → 丢旧引擎 → 建新引擎。

        抛 WorldSwitchError：world_not_found（未登记）、world_tenant_mismatch（新世界的库里
        有别的租户的行，spec §2.1，状态不前进）、ingest_busy（后台线程 5 秒内没停下，或在途
        请求 _LEASE_DRAIN_TIMEOUT_S 内没结束，状态不前进）、world_open_failed（新世界打不开，
        或注册表写不进去，都已回到旧世界）。

        发布顺序：开新库 → 存注册表 → 发布 config/engine 并起线程。注册表是「当前是
        哪个世界」的唯一持久记录，必须先落盘再对外生效：若先发布再存、存又失败
        （磁盘满、目录不可写），就会出现注册表说 A、引擎实际在写 B 的分叉——此后
        「切回 A」被当成 no-op，写入全进 B，B 的目录还能被删掉。

        顺序是「先 quiesce，再等在途请求」：后台线程不是租约，quiesce 停它们；quiesce 不持
        引擎锁 join（tick 线程在 tick() 与 _sample_backpressure() 之间、摄入线程在逐块
        remember() 之间都会放开引擎锁再重新去拿，持锁 join 会卡满 5 秒误报 ingest_busy）。
        线程先停，等请求的这段时间里就不会再有新的摄入 job 开始写旧世界。

        等在途请求等的是租约（见模块文档），不是引擎锁：remember 的抽取段、converse 的
        生成段都在引擎锁外，持锁段之外的请求也要等完。超时（_LEASE_DRAIN_TIMEOUT_S）恢复
        旧引擎的后台线程，状态不前进，回 ingest_busy。

        关键事实：DashboardEngine.close() 不释放 C++ SQLite 句柄，只有丢掉最后一个
        引用并 gc.collect() 才会。所以这里丢引用，并断言旧 Runtime 的弱引用已失效。
        租约归零之后已没有请求持有旧引擎；仍短暂可达（刚返回的栈帧、异常回溯）时在
        _RUNTIME_RELEASE_GRACE_S 内重试回收，还没失效才记 warning。

        切换窗口：从开始动引擎到新引擎发布（或回滚完成）之间 `self.switching` 为 True，
        新租约一律拒绝（路由回 503 world_switching），检视路由同样回 503。否则窗口里
        app.state.engine 暂时是 None 而 config 还是旧的，惰性建引擎会造出旧世界的引擎写回
        app.state，与注册表、config 错位。正在进行的惰性构建持着租约，切换会等它建完。
        """
        with self.lock:
            reg = self.load()
            if name not in reg["worlds"]:
                raise WorldSwitchError("world_not_found", name)
            # 已是活动世界才 no-op，且要看 live config 而不只看注册表的 active：两者一旦
            # 分叉（注册表说 A、引擎实际在写 B），只信注册表就会把「切回 A」当成已完成，
            # 之后的写入全落进 B。库相同、租户不同同样不是「已激活」。
            entry = reg["worlds"][name]
            cfg = self._state.config
            if (reg["active"] == name and self._state.engine is not None
                    and _same_db(cfg.db_path, entry["db_path"])
                    and cfg.tenant == entry["tenant"]):
                return
            with self._switch_window():
                self._swap_engine(reg, name)

    def _verify_tenant(self, entry: dict) -> None:
        """租户不变式（spec §2.1，C++ world_verify_tenant）。在动旧引擎之前做：拒开时
        什么都没变。库读不出按「新世界打不开」报 world_open_failed。"""
        try:
            _core.world_verify_tenant(entry["db_path"], entry["tenant"])
        except _core.WorldStoreError as exc:
            code = _core.world_store_error_code(exc)
            if code == "world_tenant_mismatch":
                raise WorldSwitchError("world_tenant_mismatch", str(exc)) from exc
            raise WorldSwitchError("world_open_failed", str(exc)) from exc

    def _release_old_runtime(self, rt_ref, db_path: str, after: str = "switch") -> bool:
        """丢掉引擎之后等旧 Runtime 被回收，返回是否已回收。宽限期过了仍活着就记 warning，
        并把 (db_path, 弱引用) 记进 _leaked_runtimes（见 _refuse_leaked_runtime）。"""
        gc.collect()
        deadline = time.monotonic() + _RUNTIME_RELEASE_GRACE_S
        while rt_ref() is not None and time.monotonic() < deadline:
            time.sleep(0.02)
            gc.collect()
        if rt_ref() is None:
            return True
        # C++ 连接没释放：同进程里会暂时有第二条写连接
        logger.warning("old runtime still referenced after %s", after)
        self._prune_leaked_runtimes()
        self._leaked_runtimes.append((db_path, rt_ref))
        return False

    def _prune_leaked_runtimes(self) -> None:
        self._leaked_runtimes = [(path, ref) for path, ref in self._leaked_runtimes
                                 if ref() is not None]

    def _refuse_leaked_runtime(self, db_path: str) -> None:
        """之前的切换或回滚留下的旧 Runtime 还开着 db_path 的写连接时抛 ingest_busy。先 gc 并
        摘掉已回收的条目。在动任何引擎或文件之前调用。"""
        gc.collect()
        self._prune_leaked_runtimes()
        if any(_same_db(path, db_path) for path, _ref in self._leaked_runtimes):
            raise WorldSwitchError(
                "ingest_busy", "old runtime still referenced: an earlier switch or rollback left "
                               "a write connection open on this database")

    def _quiesce_and_drain(self) -> None:
        """停当前引擎的后台线程，再等在途租约归零（切换窗口内调用）。任一步失败：恢复后台
        线程、引擎原样留在 app.state 上，抛 ingest_busy。activate 与 rollback 共用。"""
        quiesced = self._state.engine
        if quiesced is not None and not quiesced.quiesce():
            # 后台线程没停下：恢复后台线程，状态不前进。码保持 ingest_busy（前端按
            # 这个字符串映射），detail 点名实际卡住的线程。
            stuck = "/".join(getattr(quiesced, "quiesce_stuck", ())) or "background"
            self._restart_workers(quiesced)
            raise WorldSwitchError("ingest_busy", f"{stuck} thread did not stop in 5s")
        try:
            self._drain_leases()
        except WorldSwitchError:
            if quiesced is not None:
                self._restart_workers(quiesced)
            raise

    def _swap_engine(self, reg: dict, name: str) -> None:
        """activate 的主体，调用时已持管理锁并处于切换窗口内（标志已置位）。
        engine 与 config 都在租约归零之后才定稿：等待期间惰性构建可能刚写回一个引擎，
        在途的配置请求也可能刚改过 config。"""
        self._verify_tenant(reg["worlds"][name])
        self._quiesce_and_drain()
        old_engine = self._state.engine
        old_cfg = self._state.config
        new_cfg = dataclasses.replace(old_cfg)
        new_cfg.db_path = reg["worlds"][name]["db_path"]
        new_cfg.tenant = reg["worlds"][name]["tenant"]
        if old_engine is not None:
            rt_ref = weakref.ref(old_engine._rt)
            old_db = old_engine._db_path
            self._state.engine = None
            old_engine = None
            self._release_old_runtime(rt_ref, old_db)
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
        """拍快照。是否支持当前向量后端由 C++ 判（snapshot_unsupported_backend）。

        C++ 返回时新快照文件已落盘（保留策略也可能已删掉旧快照文件）；注册表存不下来时
        删掉新文件再把错误抛出去，否则它没有登记、列不出来。已被保留策略删掉的旧快照
        回不来：它们的注册项仍在旧注册表里，列表把它们标成 missing，可以照常删除。"""
        with self.lock:
            reg = self.load()
            backend = getattr(self._state.config, "vector_backend", "sqlite")
            out = _core.world_take_snapshot(reg, name, "manual", "manual", note,
                                            vector_backend=backend)
            try:
                self.save(out["registry"])
            except Exception:
                try:
                    _core.world_discard_snapshot_file(out["registry"], name,
                                                      out["snapshot"]["id"])
                except Exception:  # noqa: BLE001 — 补偿失败不能盖掉原始错误
                    logger.exception("cannot discard unregistered snapshot %s",
                                     out["snapshot"]["id"])
                raise
            return out["snapshot"]

    def delete_snapshot(self, name: str, snapshot_id: str) -> None:
        with self.lock:
            reg = self.load()
            self.save(_core.world_delete_snapshot(reg, name, snapshot_id))

    # ---- 回滚语义 A 与归档（W3，spec §5.1） ----

    def rollback(self, name: str, snapshot_id: str) -> dict:
        """把世界 name 恢复到快照 snapshot_id（丢掉快照之后的一切）。替换、校验、归档都在
        C++（world_rollback）；注册表不变，被替换的库留在 <世界 home>/archive/。

        返回 {"world", "snapshot_id", "archived", "active"}。active 看 live config 指着哪个
        库（与 delete 同一判据），不看注册表的 active，也不看引擎在不在：引擎还是 None 时，
        窗口外的惰性构建同样会在回滚中途打开这个库。

        抛错：world_switching（切换窗口已打开：切换或另一次活动世界回滚正在进行；不排队等
        管理锁）；world_not_found 与 C++ 的码
        （snapshot_not_found / snapshot_corrupt / world_tenant_mismatch / insufficient_disk /
        snapshot_failed / snapshot_unsupported_backend / world_in_use）是 _core.WorldStoreError，
        原样抛出，失败时目标库原样不动；ingest_busy（之前的切换留下的旧 Runtime 还开着这个库、
        后台线程停不下、在途请求不结束，或旧 Runtime 回收不了，库未动）；world_open_failed
        （库未动，但活动世界的引擎重建失败）；rollback_reopen_failed（库已替换成快照的内容，
        但活动世界的引擎重建失败）。后两种 engine 都留 None，路由之后惰性重建。

        动引擎之前先调 C++ 的预检（world_check_rollback，只读、什么都不动）：不存在的快照、缺失
        或不是普通文件的快照文件、不支持的向量后端、磁盘不足，这几种不改输入重试也过不了，在
        这里直接原样抛出，活动世界的引擎、线程、库文件都不动，也不进切换窗口。预检通过之后
        world_rollback 仍会再查一遍，以它为准。

        C++ 的连接探测（world_in_use）只是纵深防御。它看得见哪些连接取决于库的日志模式（在生产库
        副本上实测）：WAL 库上读过库的闲置连接（只读、读写都算）与开着的读事务都看得见；
        rollback-journal（delete）模式的库上只看得见开着的读事务；只打开、从没读过的连接两种模式
        都看不见。恢复出来的库是 VACUUM INTO 的产物，引擎打开它之前一直是 delete 模式。别的进程
        对 dashboard 管的库开写连接不在支持的使用方式之内；进程内的安全靠这里：在切换窗口内停
        线程、等租约（打开这个库的每条路径都持租约，见模块文档）、丢引擎，旧 Runtime 的弱引用
        失效了才调 C++，失效不了就不动文件（切换时这里只记 warning；回滚替换的是同一个库文件，
        必须严格）；切换遗留的 Runtime 还开着这个库就拒绝（_refuse_leaked_runtime）。活动世界的
        每个出口都按原 config 重建引擎、起线程（打开时会跑迁移，旧 schema 的快照会补齐）；
        app.state.config 不变。"""
        with self._gate:
            if self.switching:
                raise WorldSwitchError("world_switching")
        with self.lock:
            reg = self.load()
            entry = reg["worlds"].get(name)
            if entry is None:
                raise _core.WorldStoreError(f"world_not_found: {name}")
            backend = getattr(self._state.config, "vector_backend", "sqlite")
            # 停引擎之前的只读预检（C++），失败原样抛出。
            _core.world_check_rollback(reg, self.registry_dir, name, snapshot_id,
                                       vector_backend=backend)
            self._refuse_leaked_runtime(entry["db_path"])
            active = _same_db(self._state.config.db_path, entry["db_path"])
            if active:
                with self._switch_window():
                    result = self._rollback_live_world(reg, name, snapshot_id)
            else:
                # 没有引擎在写它（上面已排除切换遗留的旧 Runtime）。
                result = _core.world_rollback(reg, self.registry_dir, name, snapshot_id,
                                              vector_backend=backend)
            return {"world": name, "snapshot_id": snapshot_id,
                    "archived": bool(result["archive_path"]), "active": active}

    def _rollback_live_world(self, reg: dict, name: str, snapshot_id: str) -> dict:
        """rollback 的活动世界路径，调用时已持管理锁并处于切换窗口内。config 在租约归零之后
        才定稿（与 _swap_engine 同理）。"""
        self._quiesce_and_drain()                 # ingest_busy：引擎原样、线程已恢复
        cfg = self._state.config
        engine = self._state.engine
        if engine is not None:
            rt_ref = weakref.ref(engine._rt)
            db_path = engine._db_path
            self._state.engine = None
            engine = None
            if not self._release_old_runtime(rt_ref, db_path, after="rollback"):
                busy = WorldSwitchError(
                    "ingest_busy", "old runtime still referenced; the database was not replaced")
                self._reopen_live_world(cfg, busy)
                raise busy
        backend = getattr(cfg, "vector_backend", "sqlite")
        try:
            result = _core.world_rollback(reg, self.registry_dir, name, snapshot_id,
                                          vector_backend=backend)
        except Exception as exc:
            self._reopen_live_world(cfg, exc)     # C++ 已保证目标库未动；原样抛出
            raise
        self._reopen_live_world(cfg, None)
        return result

    def _reopen_live_world(self, cfg, cause: Exception | None) -> None:
        """回滚活动世界的每个出口：按原 config 重建引擎、起线程。重建失败时 engine 留 None，
        路由之后惰性重建。码按库有没有被替换来分：
        - cause 为 None（替换成功之后）：库已是快照的内容，抛 rollback_reopen_failed，链到
          重建的异常。路由仍广播 world_rolled_back，前端整页刷新。
        - 其余出口（C++ 失败、弱引用拒绝、遗留 Runtime 拒绝）：库未动，抛 world_open_failed，
          链到 cause。
        重建成功则返回，由调用方抛 cause 或返回结果。"""
        try:
            engine = DashboardEngine(cfg)
        except Exception as exc:
            self._state.engine = None
            # 路由只回码，detail 不进响应，所以在这里留日志。
            if cause is None:
                detail = f"rollback applied, but the world cannot be reopened: {exc}"
                logger.error("world rollback: %s", detail)
                raise WorldSwitchError("rollback_reopen_failed", detail) from exc
            detail = f"{cause}; reopening the world also failed: {exc}"
            logger.error("world rollback: %s", detail)
            raise WorldSwitchError("world_open_failed", detail) from cause
        self._state.engine = engine
        self._start_workers(engine, cfg)

    def archives(self, name: str, reg: dict | None = None) -> list[dict]:
        """该世界 archive/ 下的回滚归档 [{"name", "size_bytes"}]，最新在前。只读，不持管理锁，
        不打开库。reg 给出时直接用（GET /api/worlds 已经读过注册表），否则重读。"""
        return _core.world_list_archives(self.load() if reg is None else reg,
                                         self.registry_dir, name)

    def purge_archives(self, name: str) -> int:
        """删除该世界的全部回滚归档，返回删掉的文件数。"""
        with self.lock:
            return _core.world_purge_archives(self.load(), self.registry_dir, name)
