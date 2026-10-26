"""世界注册表与快照（W1/W2）：绑定、切换、路由。

设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md
"""
import gc
import json
import os
import sqlite3
import threading
import time
import weakref

import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine
from starling.dashboard.world_manager import (WorldManager, WorldSwitchError,
                                              bootstrap_worlds, registry_path_for)


def _code(exc) -> str:
    return _core.world_store_error_code(exc)


def test_binding_registry_roundtrip(tmp_path):
    reg_path = str(tmp_path / "worlds.json")
    reg = _core.world_ensure_registry(reg_path, str(tmp_path / "dashboard.db"), "default")
    assert reg["active"] == "default"
    assert reg["snapshot_retention"] == 5
    assert set(reg["worlds"]) == {"default"}

    out = _core.world_create(reg, str(tmp_path), "sim-1", "模拟一", "2026-10-25T01:00:00Z")
    reg = out["registry"]
    assert out["world"]["tenant"] == "sim-1"
    assert out["world"]["db_path"].endswith("worlds/sim-1/world.db")
    _core.world_save_registry(reg_path, reg)
    assert set(_core.world_load_registry(reg_path)["worlds"]) == {"default", "sim-1"}


def test_binding_error_codes(tmp_path):
    reg = _core.world_ensure_registry(str(tmp_path / "w.json"), str(tmp_path / "d.db"), "default")
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_create(reg, str(tmp_path), "Bad Name", "", "2026-10-25T01:00:00Z")
    assert _code(ei.value) == "invalid_world_name"
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_set_active(reg, "nope")
    assert _code(ei.value) == "world_not_found"
    assert isinstance(ei.value, RuntimeError)


def test_binding_snapshot_and_stats(tmp_path):
    reg = _core.world_ensure_registry(str(tmp_path / "w.json"), str(tmp_path / "d.db"), "default")
    reg = _core.world_create(reg, str(tmp_path), "sim-1", "", "2026-10-25T01:00:00Z")["registry"]
    db = reg["worlds"]["sim-1"]["db_path"]
    _core.SqliteAdapter.open(db)   # 跑迁移建库
    stats = _core.world_stats(db, "sim-1")
    assert stats["engrams"] == 0 and stats["db_bytes"] > 0

    out = _core.world_take_snapshot(reg, "sim-1", note="手动")
    snap = out["snapshot"]
    assert snap["kind"] == "manual" and snap["note"] == "手动"
    con = sqlite3.connect(f"file:{snap['path']}?mode=ro", uri=True)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()
    reg = _core.world_delete_snapshot(out["registry"], "sim-1", snap["id"])
    assert reg["snapshots"]["sim-1"] == []


# ───────────────────────── W1 Task 4：世界切换（引擎生命周期） ─────────────────────────

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _cfg(tmp_path):
    return DashboardConfig(db_path=str(tmp_path / "dashboard.db"), token="",
                           tick_interval_s=0, source_lane_enabled=False,
                           ingest_spool_path=str(tmp_path / "spool"))


class _State:
    """最小 app.state 替身：WorldManager 只用 .engine 和 .config。"""
    def __init__(self, cfg):
        self.config = cfg
        self.engine = None


def _manager(tmp_path):
    cfg = _cfg(tmp_path)
    reg_path = bootstrap_worlds(cfg)
    state = _State(cfg)
    state.engine = DashboardEngine(cfg)
    return WorldManager(state, reg_path), state


def _remember(engine, text):
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    engine.llm = fake
    return engine.remember(text)


def test_registry_path_defaults_next_to_db(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    assert registry_path_for(_cfg(tmp_path)) == str(tmp_path / "worlds.json")
    monkeypatch.setenv("STARLING_WORLDS_REGISTRY", str(tmp_path / "x" / "r.json"))
    assert registry_path_for(_cfg(tmp_path)) == str(tmp_path / "x" / "r.json")


def test_bootstrap_rewrites_config_to_active_world(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    cfg = _cfg(tmp_path)
    reg_path = bootstrap_worlds(cfg)
    reg = _core.world_load_registry(reg_path)
    reg = _core.world_create(reg, str(tmp_path), "sim-1", "", "2026-10-25T01:00:00Z")["registry"]
    reg = _core.world_set_active(reg, "sim-1")
    _core.world_save_registry(reg_path, reg)
    cfg2 = _cfg(tmp_path)
    bootstrap_worlds(cfg2)
    assert cfg2.tenant == "sim-1"
    assert cfg2.db_path.endswith("worlds/sim-1/world.db")


def test_bootstrap_warns_when_registry_overrides_config(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    bootstrap_worlds(_cfg(tmp_path))                     # 建注册表：default -> dashboard.db
    caplog.clear()
    bootstrap_worlds(_cfg(tmp_path))
    assert "overrides config" not in caplog.text         # 一致时不吵
    other = _cfg(tmp_path)
    other.db_path = str(tmp_path / "other.db")           # 例如 STARLING_DASH_DB 指到别处
    with caplog.at_level("WARNING"):
        bootstrap_worlds(other)
    assert "overrides config" in caplog.text
    assert other.db_path == str(tmp_path / "dashboard.db")


@pytest.mark.parametrize("db_path", [":memory:", "", "bare.db"])
def test_bootstrap_skips_db_without_parent_dir(tmp_path, monkeypatch, db_path):
    """:memory: / 无父目录的路径：不建注册表，不改 config，app.state.worlds 为 None。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    cfg = DashboardConfig(db_path=db_path, token="", tick_interval_s=0)
    assert bootstrap_worlds(cfg) is None
    assert (cfg.db_path, cfg.tenant) == (db_path, "default")
    app = create_app(DashboardConfig(db_path=db_path, token="", tick_interval_s=0))
    assert app.state.worlds is None
    assert list(tmp_path.iterdir()) == []          # cwd 里没有悄悄落下 worlds.json


def test_create_app_wires_world_manager(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    cfg = _cfg(tmp_path)
    app = create_app(cfg)
    assert isinstance(app.state.worlds, WorldManager)
    assert app.state.worlds.registry_path == str(tmp_path / "worlds.json")
    assert app.state.worlds.workers_enabled is False and app.state.worlds.on_tick is None
    assert (tmp_path / "worlds.json").exists()


def test_lifespan_enables_workers_and_switch_restarts_them(tmp_path, monkeypatch):
    """lifespan 起完线程后才打开 workers_enabled 并挂上 on_tick；
    此后切换世界会为新引擎重启 tick/摄入线程，关停时再关掉开关。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    cfg = _cfg(tmp_path)
    cfg.tick_interval_s = 60.0
    app = create_app(cfg, engine=DashboardEngine(cfg))
    worlds = app.state.worlds
    assert worlds.workers_enabled is False
    with TestClient(app):                              # 进入 lifespan
        assert worlds.workers_enabled is True and worlds.on_tick is not None
        old = app.state.engine
        old_rt = weakref.ref(old._rt)
        old_threads = (old._tick_thread, old._ingest_thread)
        del old                                        # 测试自己不能钉住旧引擎
        worlds.create("sim-1", "")
        worlds.activate("sim-1")
        assert old_rt() is None, "第一次切换就必须释放旧 Runtime"
        new = app.state.engine
        assert all(t is not None and not t.is_alive() for t in old_threads)
        assert new._tick_thread is not None and new._tick_thread.is_alive()
        assert new._ingest_thread is not None and new._ingest_thread.is_alive()
    assert worlds.workers_enabled is False
    assert new._tick_thread is None and new._ingest_thread is None   # 关停时已停


@pytest.mark.parametrize("shape", ["injected", "assigned_after_create"])
@pytest.mark.parametrize("tick", [0, 60.0])
def test_lifespan_first_switch_releases_old_runtime(tmp_path, monkeypatch, caplog, tick, shape):
    """lifespan 在 yield 处挂起期间，它的局部变量一直活着：若其中有 eng 指向启动时的
    引擎，第一次切换就钉住旧 Runtime（第二次才正常释放），默认世界的 C++ 写连接留下，
    切回默认世界就是同一个库文件上的两条写连接。覆盖生产形态（create_app(cfg) 之后
    再给 app.state.engine 赋值）和注入形态，tick 开/关各一遍。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    cfg = _cfg(tmp_path)
    cfg.tick_interval_s = tick
    if shape == "injected":
        app = create_app(cfg, engine=DashboardEngine(cfg))
    else:
        app = create_app(cfg)
        app.state.engine = DashboardEngine(cfg)
    worlds = app.state.worlds
    with TestClient(app):
        worlds.create("sim-1", "")
        old_rt = weakref.ref(app.state.engine._rt)
        with caplog.at_level("WARNING"):
            worlds.activate("sim-1")
        assert old_rt() is None
        assert "old runtime still referenced" not in caplog.text
        default_rt = weakref.ref(app.state.engine._rt)
        with caplog.at_level("WARNING"):
            worlds.activate("default")                 # 切回默认世界，同一个库文件
        assert default_rt() is None
        assert "old runtime still referenced" not in caplog.text


def test_activate_switches_engine_and_isolates_data(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    _remember(state.engine, "Bob owns auth")
    mgr.create("sim-1", "")
    old_rt = weakref.ref(state.engine._rt)
    mgr.activate("sim-1")
    gc.collect()
    assert old_rt() is None, "旧 Runtime 必须被释放（否则同文件会有两条写连接）"
    assert state.config.tenant == "sim-1"
    assert mgr.load()["active"] == "sim-1"
    # 新世界是空的
    con = sqlite3.connect(f"file:{state.config.db_path}?mode=ro", uri=True)
    assert con.execute("SELECT COUNT(*) FROM engrams").fetchone()[0] == 0
    con.close()
    # 切回默认世界，原数据仍在
    mgr.activate("default")
    con = sqlite3.connect(f"file:{state.config.db_path}?mode=ro", uri=True)
    assert con.execute("SELECT COUNT(*) FROM engrams").fetchone()[0] == 1
    con.close()


def test_activate_keeps_config_path_and_is_a_copy(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    old_cfg = state.config
    old_cfg.config_path = str(tmp_path / "starling.json")
    mgr.create("sim-1", "")
    mgr.activate("sim-1")
    assert state.config is not old_cfg
    assert state.config.config_path == str(tmp_path / "starling.json")
    assert old_cfg.tenant == "default"             # 旧 config 对象不被改动


def test_activate_noop_when_already_active(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    eng, cfg = state.engine, state.config
    mgr.activate("default")
    assert state.engine is eng and state.config is cfg


def test_activate_unknown_world(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, _state = _manager(tmp_path)
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("nope")
    assert ei.value.code == "world_not_found"


def test_activate_rolls_back_when_new_world_fails_to_open(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    state.config.tick_interval_s = 60.0
    mgr.workers_enabled = True
    state.engine.start_background_tick(60.0)
    state.engine.start_ingest_worker()
    _remember(state.engine, "Bob owns auth")
    mgr.create("sim-1", "")
    # 让新世界的库文件是一个目录：SqliteAdapter.open 必然失败
    reg = mgr.load()
    os.makedirs(reg["worlds"]["sim-1"]["db_path"])
    old_cfg = state.config
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "world_open_failed"
    assert state.engine is not None
    assert state.config is old_cfg and state.config.tenant == "default"
    assert mgr.load()["active"] == "default"
    assert mgr.switching is False
    # 回滚回来的引擎真能用：读得到切换前写进去的数据、还能再写、健康、线程在跑
    assert state.engine.health().name == "READY"
    _remember(state.engine, "Carol owns billing")
    con = sqlite3.connect(f"file:{state.config.db_path}?mode=ro", uri=True)
    assert con.execute("SELECT COUNT(*) FROM engrams").fetchone()[0] == 2
    con.close()
    assert state.engine._tick_thread is not None and state.engine._tick_thread.is_alive()
    assert state.engine._ingest_thread is not None and state.engine._ingest_thread.is_alive()
    assert state.engine.quiesce() is True


def test_activate_rollback_failure_surfaces_as_world_open_failed(tmp_path, monkeypatch):
    """新世界打不开、回滚重建旧世界也失败：仍是 WorldSwitchError（路由只映射它），
    不是裸异常；engine 留 None，config 仍是旧世界，之后惰性重建得到的是旧世界。"""
    import starling.dashboard.world_manager as wm
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    real = wm.DashboardEngine

    def _always_fail(_cfg):
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(wm, "DashboardEngine", _always_fail)
    old_cfg = state.config
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "world_open_failed"
    assert "disk on fire" in ei.value.detail
    assert state.engine is None and state.config is old_cfg
    assert mgr.load()["active"] == "default" and mgr.switching is False
    monkeypatch.setattr(wm, "DashboardEngine", real)
    assert real(state.config).health().name == "READY"      # 旧世界的库并没有被破坏


def test_activate_refuses_when_ingest_will_not_stop(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    state.config.tick_interval_s = 60.0
    mgr.workers_enabled = True
    eng, cfg = state.engine, state.config
    eng.start_background_tick(60.0)
    eng.start_ingest_worker()
    mgr.create("sim-1", "")

    def _stopped_but_reports_busy(timeout_s=5.0):
        eng.stop_ingest_worker()
        eng.stop_background_tick()
        return False
    monkeypatch.setattr(eng, "quiesce", _stopped_but_reports_busy)
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "ingest_busy"
    assert mgr.load()["active"] == "default"
    assert state.engine is eng and state.config is cfg      # 状态不前进
    assert mgr.switching is False
    # 失败后必须把后台线程恢复出来，否则摄入悄悄停摆
    assert eng._tick_thread is not None and eng._tick_thread.is_alive()
    assert eng._ingest_thread is not None and eng._ingest_thread.is_alive()
    monkeypatch.undo()
    assert eng.quiesce() is True


class _StuckThread:
    """join 不动、一直 is_alive 的线程替身。"""
    def join(self, timeout=None):
        pass

    def is_alive(self):
        return True


def test_ingest_busy_detail_names_the_stuck_thread(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    eng = state.engine
    eng._tick_thread, eng._tick_stop = _StuckThread(), threading.Event()   # 卡的是 tick
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "ingest_busy"                   # 前端按这个字符串映射，码不变
    assert "tick" in ei.value.detail and "ingest" not in ei.value.detail
    eng._tick_thread = eng._tick_stop = None
    eng._ingest_thread, eng._ingest_stop = _StuckThread(), threading.Event()
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert "ingest" in ei.value.detail and "tick" not in ei.value.detail
    eng._ingest_thread = eng._ingest_stop = None


def test_switching_flag_spans_the_whole_swap_and_clears_on_every_exit(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    assert mgr.switching is False
    seen = []
    real_quiesce = state.engine.quiesce

    def _spy(timeout_s=5.0):
        seen.append(mgr.switching)
        return real_quiesce(timeout_s)
    monkeypatch.setattr(state.engine, "quiesce", _spy)
    mgr.activate("sim-1")
    assert seen == [True]                    # 停线程阶段就已经拒绝新请求
    assert mgr.switching is False
    with pytest.raises(WorldSwitchError):    # world_not_found 路径：根本没置位过
        mgr.activate("nope")
    assert mgr.switching is False
    mgr.activate("sim-1")                    # 已是活动世界的 no-op
    assert mgr.switching is False


def test_activate_does_not_hold_engine_lock_while_joining_workers(tmp_path, monkeypatch):
    """后台线程每个循环会分几段各自拿引擎锁，段与段之间锁是空的：
    tick() 与 _sample_backpressure() 之间，或摄入逐块 remember() 之间。切换恰好卡在
    空档时，若 quiesce 是持着引擎锁 join，线程下一段拿不到锁、永远退不出，
    5 秒后误报 ingest_busy，而且这 5 秒里所有请求都排在引擎锁后面。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    eng = state.engine
    stop = threading.Event()
    in_first, go_first, gap = threading.Event(), threading.Event(), threading.Event()

    def _loop():
        with eng._lock:                 # 第一段：tick() / 一块 remember()
            in_first.set()
            go_first.wait(10)
        gap.wait(10)                    # 空档：锁是空的
        with eng._lock:                 # 第二段：_sample_backpressure() / 下一块 remember()
            pass
        stop.wait(10)

    worker = threading.Thread(target=_loop, daemon=True)
    eng._tick_thread, eng._tick_stop = worker, stop
    worker.start()
    assert in_first.wait(5)
    outcome: list = []
    done = threading.Event()

    def _switch():
        try:
            mgr.activate("sim-1")
            outcome.append("ok")
        except WorldSwitchError as exc:
            outcome.append(exc.code)
        finally:
            done.set()

    switcher = threading.Thread(target=_switch, daemon=True)
    switcher.start()
    try:
        time.sleep(0.2)                 # 切换线程此刻已在 quiesce 里 join worker（它没持引擎锁）；
                                        # worker 还卡在第一段里，join 要等它退出
        go_first.set()                  # 第一段结束，worker 进入空档
        time.sleep(0.2)
        gap.set()                       # worker 进入第二段，要拿引擎锁
        assert done.wait(3), "切换被持锁 join 拖住了（worker 在等切换线程释放引擎锁）"
        assert outcome == ["ok"], outcome
        assert not worker.is_alive() and state.config.tenant == "sim-1"
    finally:
        go_first.set()
        gap.set()
        stop.set()
        switcher.join(10)


def test_activate_waits_for_in_flight_request(tmp_path, monkeypatch):
    """在飞请求（持租约）结束之前，旧引擎不能被丢弃；结束之后旧 Runtime 必须真的被释放。
    请求不一定持着引擎锁（remember 的抽取段、converse 的生成段都在锁外），所以等的是
    租约而不是引擎锁。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    old_rt = weakref.ref(state.engine._rt)
    holding, release = threading.Event(), threading.Event()

    def _request():
        with mgr.lease() as eng:
            assert eng is state.engine
            holding.set()
            release.wait(10)
            del eng                      # 请求结束：引用随栈帧一起走

    req = threading.Thread(target=_request, daemon=True)
    req.start()
    assert holding.wait(5)
    done = threading.Event()
    switcher = threading.Thread(target=lambda: (mgr.activate("sim-1"), done.set()), daemon=True)
    switcher.start()
    # 不能只看「切换还没返回」：丢掉旧引擎后切换会在宽限期内等旧 Runtime 回收，同样
    # 不会立即返回。要看旧引擎此刻仍在 app.state 上——不等租约的实现会立即把它丢成 None。
    for _ in range(3):
        assert not done.wait(0.4), "请求还没结束，切换不该完成"
        assert state.engine is not None and state.config.tenant == "default"
        assert mgr.switching is True
    release.set()
    assert done.wait(10)
    req.join(5)
    assert state.config.tenant == "sim-1" and mgr.switching is False
    assert old_rt() is None, "等到请求结束才丢旧引擎，旧 Runtime 必须已释放"


def test_quiesce_stops_threads(tmp_path):
    cfg = _cfg(tmp_path)
    eng = DashboardEngine(cfg)
    eng.start_background_tick(60.0)
    eng.start_ingest_worker(poll_interval_s=60.0)
    assert eng.quiesce() is True
    assert eng._tick_thread is None and eng._ingest_thread is None


def test_quiesce_failure_keeps_stuck_worker_runnable(tmp_path):
    """join 超时：返回 False，句柄原样保留，且撤销停止信号——否则调用方回滚后
    这条线程一旦退出就再也没人重启，摄入悄悄停摆；句柄和事件不一致还会让
    之后的 stop_ingest_worker() 在 None.set() 上炸。"""
    eng = DashboardEngine(_cfg(tmp_path))

    class _Stuck:
        def join(self, timeout=None):
            pass

        def is_alive(self):
            return True

    stuck, stop = _Stuck(), threading.Event()
    eng._ingest_thread, eng._ingest_stop = stuck, stop
    assert eng.quiesce() is False
    assert eng._ingest_thread is stuck and eng._ingest_stop is stop
    assert not stop.is_set()
    eng._ingest_thread = eng._ingest_stop = None     # 收尾，别留下假线程


def test_activate_does_not_start_workers_unless_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    state.config.tick_interval_s = 60.0
    mgr.create("sim-1", "")
    mgr.activate("sim-1")                              # workers_enabled 默认 False
    assert state.engine._tick_thread is None and state.engine._ingest_thread is None


def test_activate_restarts_workers_when_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    state.config.tick_interval_s = 60.0
    seen = []
    mgr.on_tick = seen.append
    mgr.workers_enabled = True
    state.engine.start_background_tick(60.0, mgr.on_tick)
    state.engine.start_ingest_worker()
    mgr.create("sim-1", "")
    old = state.engine
    mgr.activate("sim-1")
    try:
        assert old._tick_thread is None and old._ingest_thread is None   # 旧线程已停
        assert state.engine._tick_thread is not None and state.engine._tick_thread.is_alive()
        assert state.engine._ingest_thread is not None and state.engine._ingest_thread.is_alive()
    finally:
        assert state.engine.quiesce() is True


def test_activate_without_engine_builds_one(tmp_path, monkeypatch):
    """惰性引擎（app.state.engine 还是 None）：切换照样能建出新世界的引擎。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    cfg = _cfg(tmp_path)
    state = _State(cfg)
    mgr = WorldManager(state, bootstrap_worlds(cfg))
    mgr.create("sim-1", "")
    mgr.activate("sim-1")
    assert state.engine is not None and state.config.tenant == "sim-1"


def test_active_world_carries_name(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, _state = _manager(tmp_path)
    mgr.create("sim-1", "一号")
    assert mgr.active_world()["name"] == "default"
    mgr.activate("sim-1")
    entry = mgr.active_world()
    assert entry["name"] == "sim-1" and entry["label"] == "一号" and entry["tenant"] == "sim-1"


def test_create_returns_entry_with_name_and_delete_protects_active(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, _state = _manager(tmp_path)
    entry = mgr.create("sim-1", "一号")
    assert entry["name"] == "sim-1" and entry["tenant"] == "sim-1"
    assert os.path.isdir(os.path.dirname(entry["snapshot_dir"]))
    with pytest.raises(_core.WorldStoreError) as ei:
        mgr.create("sim-1", "")
    assert _code(ei.value) == "world_exists"
    with pytest.raises(_core.WorldStoreError) as ei:
        mgr.delete("default")
    assert _code(ei.value) == "world_protected"
    mgr.delete("sim-1")
    assert set(mgr.load()["worlds"]) == {"default"}
    assert not os.path.exists(os.path.dirname(entry["snapshot_dir"]))


def test_manager_snapshot_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    _remember(state.engine, "Bob owns auth")
    snap = mgr.take_snapshot("default", "手动")
    assert snap["kind"] == "manual" and snap["note"] == "手动"
    assert [s["id"] for s in mgr.load()["snapshots"]["default"]] == [snap["id"]]
    mgr.delete_snapshot("default", snap["id"])
    assert mgr.load()["snapshots"]["default"] == []
    with pytest.raises(_core.WorldStoreError) as ei:
        mgr.delete_snapshot("default", "nope")
    assert _code(ei.value) == "snapshot_not_found"


def test_snapshot_rejects_zvec_backend(tmp_path, monkeypatch):
    """拒绝由 C++ 给出（WorldStoreError），WorldManager 只把当前配置的后端传过去。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    state.config.vector_backend = "zvec"
    with pytest.raises(_core.WorldStoreError) as ei:
        mgr.take_snapshot("default", "")
    assert _code(ei.value) == "snapshot_unsupported_backend"
    assert mgr.load()["snapshots"].get("default", []) == []
    snap_dir = mgr.load()["worlds"]["default"]["snapshot_dir"]
    assert not os.path.isdir(snap_dir) or os.listdir(snap_dir) == []


def test_concurrent_snapshots_do_not_lose_entries(tmp_path, monkeypatch):
    """绑定在 VACUUM 期间释放 GIL，没有管理锁时两个线程各持旧 dict，后保存者覆盖先保存者。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, _state = _manager(tmp_path)
    mgr.save({**mgr.load(), "snapshot_retention": 20})
    errors = []

    def _snap():
        try:
            mgr.take_snapshot("default", "")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_snap) for _ in range(6)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(30)
    assert not errors
    listed = mgr.load()["snapshots"]["default"]
    assert len(listed) == 6
    assert len({s["id"] for s in listed}) == 6
    assert all(os.path.exists(s["path"]) for s in listed)


# ── POST /api/config：永远把默认世界写进 starling.json ──

_CFG_BODY = {"providers": {"default": {"provider": "openai", "model": "m",
                                       "base_url": "", "api_key": "sk-x"}},
             "roles": {"extraction": "default"}}


def _config_app(tmp_path, monkeypatch):
    import starling.dashboard.engine as engmod
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    monkeypatch.setattr(engmod, "_build_chat_adapter", lambda c: _core.FakeLLMAdapter())
    cfgfile = tmp_path / "starling.json"
    cfg = _cfg(tmp_path)
    cfg.config_path = str(cfgfile)
    eng = DashboardEngine(cfg)
    app = create_app(cfg, engine=eng)
    return app, cfgfile


def test_post_config_persists_default_world_while_other_world_active(tmp_path, monkeypatch):
    app, cfgfile = _config_app(tmp_path, monkeypatch)
    client = TestClient(app)                     # 不进 lifespan：切换不会起后台线程
    app.state.worlds.create("sim-1", "")
    app.state.worlds.activate("sim-1")
    assert app.state.config.tenant == "sim-1"
    assert client.post("/api/config", json=_CFG_BODY).status_code == 200
    saved = json.loads(cfgfile.read_text())
    assert saved["db_path"] == str(tmp_path / "dashboard.db")
    assert saved["tenant"] == "default"
    assert saved["providers"]["default"]["api_key"] == "sk-x"
    assert app.state.config.tenant == "sim-1"    # 运行时 config 不被改动
    assert client.delete("/api/config/provider/default").status_code == 200
    saved = json.loads(cfgfile.read_text())
    assert saved["db_path"] == str(tmp_path / "dashboard.db") and saved["tenant"] == "default"
    assert "default" not in saved["providers"]


def test_post_config_without_world_manager_saves_plain_config(tmp_path, monkeypatch):
    app, cfgfile = _config_app(tmp_path, monkeypatch)
    app.state.worlds = None
    client = TestClient(app)
    assert client.post("/api/config", json=_CFG_BODY).status_code == 200
    assert json.loads(cfgfile.read_text())["db_path"] == str(tmp_path / "dashboard.db")


def test_persistable_config_keeps_default_world(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    mgr.activate("sim-1")
    out = mgr.persistable_config(state.config)
    assert out.db_path == str(tmp_path / "dashboard.db")
    assert out.tenant == "default"
    assert state.config.tenant == "sim-1"      # 运行时 config 不被改动


# ───────────────────────── W1 Task 5：/api/worlds 路由 ─────────────────────────

def _client(tmp_path):
    cfg = _cfg(tmp_path)
    app = create_app(cfg)
    return TestClient(app), app


def test_routes_list_create_activate_delete(tmp_path):
    client, app = _client(tmp_path)
    body = client.get("/api/worlds").json()
    assert body["active"] == "default" and body["snapshot_retention"] == 5
    assert [w["name"] for w in body["worlds"]] == ["default"]

    assert client.post("/api/worlds", json={"name": "Bad"}).json()["detail"] == "invalid_world_name"
    row = client.post("/api/worlds", json={"name": "sim-1", "label": "模拟"}).json()
    assert row["name"] == "sim-1" and row["active"] is False and row["engrams"] == 0
    assert client.post("/api/worlds", json={"name": "sim-1"}).status_code == 409

    r = client.post("/api/worlds/sim-1/activate")
    assert r.status_code == 200 and r.json() == {"active": "sim-1"}
    assert app.state.config.tenant == "sim-1"
    assert client.post("/api/worlds/nope/activate").status_code == 404

    r = client.delete("/api/worlds/sim-1", params={"confirm": "sim-1"})
    assert r.status_code == 409 and r.json()["detail"] == "world_protected"
    client.post("/api/worlds/default/activate")
    r = client.delete("/api/worlds/sim-1", params={"confirm": "wrong"})
    assert r.status_code == 400 and r.json()["detail"] == "confirm_mismatch"
    r = client.delete("/api/worlds/sim-1", params={"confirm": "sim-1"})
    assert r.status_code == 200
    assert [w["name"] for w in client.get("/api/worlds").json()["worlds"]] == ["default"]


def test_routes_snapshots(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)   # 建库
    snap = client.post("/api/worlds/default/snapshots", json={"note": "n1"}).json()
    assert snap["kind"] == "manual" and snap["note"] == "n1" and snap["size_bytes"] > 0
    listed = client.get("/api/worlds/default/snapshots").json()["snapshots"]
    assert [s["id"] for s in listed] == [snap["id"]]
    assert client.get("/api/worlds").json()["worlds"][0]["snapshots"] == 1
    assert client.delete(f"/api/worlds/default/snapshots/{snap['id']}").status_code == 200
    assert client.delete("/api/worlds/default/snapshots/missing").status_code == 404
    assert client.post("/api/worlds/nope/snapshots", json={}).status_code == 404


def test_routes_snapshot_refused_for_zvec(tmp_path):
    client, app = _client(tmp_path)
    app.state.config.vector_backend = "zvec"
    r = client.post("/api/worlds/default/snapshots", json={})
    assert r.status_code == 409 and r.json()["detail"] == "snapshot_unsupported_backend"


def test_routes_require_token(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.token = "s3cret"
    client = TestClient(create_app(cfg))
    assert client.get("/api/worlds").status_code == 401
    assert client.get("/api/worlds", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_routes_never_accept_paths(tmp_path):
    client, _app = _client(tmp_path)
    # 名称校验本身就挡掉了路径；这里钉住它，防止将来放宽。
    for evil in ("../x", "a/b", "/abs"):
        assert client.post("/api/worlds", json={"name": evil}).status_code in (400, 404, 422)


@pytest.mark.parametrize("method,path", [
    ("get", "/api/worlds"),
    ("post", "/api/worlds"),
    ("post", "/api/worlds/default/activate"),
    ("delete", "/api/worlds/default?confirm=default"),
    ("get", "/api/worlds/default/snapshots"),
    ("post", "/api/worlds/default/snapshots"),
    ("delete", "/api/worlds/default/snapshots/x"),
])
def test_routes_503_when_world_manager_absent(method, path):
    """:memory: 库没有注册表（app.state.worlds 为 None）：全部路由回 503，不是 AttributeError。"""
    app = create_app(DashboardConfig(db_path=":memory:", token="", tick_interval_s=0))
    assert app.state.worlds is None
    kwargs = {"json": {"name": "sim-1"}} if (method, path) == ("post", "/api/worlds") else {}
    r = getattr(TestClient(app), method)(path, **kwargs)
    assert r.status_code == 503 and r.json()["detail"] == "worlds_unavailable"


def test_routes_worldrow_shape_and_stats(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    _remember(app.state.engine, "Bob is responsible for auth")
    client.post("/api/worlds", json={"name": "sim-1"})
    rows = {w["name"]: w for w in client.get("/api/worlds").json()["worlds"]}
    assert list(rows) == ["default", "sim-1"]
    keys = {"name", "label", "tenant", "created_at", "active", "db_bytes", "live_bytes",
            "statements", "engrams", "snapshots", "snapshot_bytes"}
    assert set(rows["default"]) == keys and set(rows["sim-1"]) == keys
    assert rows["default"]["active"] is True and rows["sim-1"]["active"] is False
    assert rows["default"]["engrams"] >= 1 and rows["default"]["db_bytes"] > 0
    assert rows["sim-1"]["engrams"] == 0 and rows["sim-1"]["db_bytes"] == 0   # 库未建
    assert rows["sim-1"]["tenant"] == "sim-1"


def test_routes_snapshot_rows_hide_server_paths_and_sum_bytes(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    first = client.post("/api/worlds/default/snapshots", json={"note": "a"}).json()
    second = client.post("/api/worlds/default/snapshots", json={"note": "b"}).json()
    assert set(first) == {"id", "kind", "reason", "note", "created_at", "world_time", "size_bytes"}
    listed = client.get("/api/worlds/default/snapshots").json()["snapshots"]
    stamps = [s["created_at"] for s in listed]
    assert stamps == sorted(stamps, reverse=True)            # 降序
    assert {s["id"] for s in listed} == {first["id"], second["id"]}
    row = client.get("/api/worlds").json()["worlds"][0]
    assert row["snapshots"] == 2
    assert row["snapshot_bytes"] == first["size_bytes"] + second["size_bytes"]


def test_routes_snapshot_body_is_optional(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    r = client.post("/api/worlds/default/snapshots")          # 无 body
    assert r.status_code == 200 and r.json()["note"] == ""


def test_routes_confirm_mismatch_does_not_touch_manager(tmp_path, monkeypatch):
    client, app = _client(tmp_path)
    client.post("/api/worlds", json={"name": "sim-1"})

    def _boom(*_a, **_k):
        raise AssertionError("manager must not be called")
    monkeypatch.setattr(app.state.worlds, "delete", _boom)
    assert client.delete("/api/worlds/sim-1").json()["detail"] == "confirm_mismatch"   # 缺 confirm
    r = client.delete("/api/worlds/sim-1", params={"confirm": "other"})
    assert r.status_code == 400 and r.json()["detail"] == "confirm_mismatch"


@pytest.mark.parametrize("code,status", [
    ("ingest_busy", 409), ("world_open_failed", 500), ("world_not_found", 404),
    ("snapshot_unsupported_backend", 409), ("world_switching", 503),
])
def test_routes_activate_maps_switch_errors(tmp_path, monkeypatch, code, status):
    client, app = _client(tmp_path)

    def _raise(_name):
        raise WorldSwitchError(code, "x")
    monkeypatch.setattr(app.state.worlds, "activate", _raise)
    r = client.post("/api/worlds/default/activate")
    assert r.status_code == status and r.json()["detail"] == code


def test_routes_snapshot_insufficient_disk_is_507(tmp_path, monkeypatch):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)

    def _no_space(*_args, **_kwargs):
        # C++ 的 free_space 钩子没有暴露给 Python，没法真造出磁盘不足；这里在绑定边界
        # 抛出同形异常（what() 形如 "<code>: <detail>"），只验证路由的 507 映射。
        raise _core.WorldStoreError("insufficient_disk: need 3x live bytes")
    monkeypatch.setattr(_core, "world_take_snapshot", _no_space)
    r = client.post("/api/worlds/default/snapshots", json={})
    assert r.status_code == 507 and r.json()["detail"] == "insufficient_disk"
    monkeypatch.undo()
    assert client.get("/api/worlds/default/snapshots").json()["snapshots"] == []   # 没留下条目


def test_routes_unknown_error_code_falls_back_to_500(tmp_path, monkeypatch):
    client, app = _client(tmp_path)

    def _raise(_name):
        raise WorldSwitchError("something_new")
    monkeypatch.setattr(app.state.worlds, "activate", _raise)
    r = client.post("/api/worlds/default/activate")
    assert r.status_code == 500 and r.json()["detail"] == "something_new"


def test_routes_broadcast_world_switched_and_snapshot_created(tmp_path):
    cfg = _cfg(tmp_path)
    app = create_app(cfg)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            client.post("/api/worlds", json={"name": "sim-1"})
            assert client.post("/api/worlds/sim-1/activate").status_code == 200
            msg = ws.receive_json()
            assert msg == {"type": "world_switched", "payload": {"active": "sim-1"}}

            snap = client.post("/api/worlds/sim-1/snapshots", json={}).json()
            msg = ws.receive_json()
            assert msg == {"type": "snapshot_created",
                           "payload": {"world": "sim-1", "id": snap["id"]}}


def test_routes_failed_operations_do_not_broadcast(tmp_path):
    app = create_app(_cfg(tmp_path))
    sent = []

    async def _record(message):
        sent.append(message)
    app.state.ws_manager.broadcast = _record
    client = TestClient(app)
    assert client.post("/api/worlds/nope/activate").status_code == 404
    assert client.post("/api/worlds/nope/snapshots", json={}).status_code == 404
    assert sent == []


def test_routes_list_snapshots_unknown_world_is_404(tmp_path):
    client, _app = _client(tmp_path)
    r = client.get("/api/worlds/nope/snapshots")
    assert r.status_code == 404 and r.json()["detail"] == "world_not_found"
    # 已登记但从未拍过快照的世界：空列表，不是 404
    assert client.get("/api/worlds/default/snapshots").json() == {"snapshots": []}


# ── 切换窗口：engine=None 到新 engine 发布之间，请求不得惰性重建出旧配置的引擎 ──

def test_requests_get_503_world_switching_during_the_swap_window(tmp_path, monkeypatch):
    """窗口里 app.state.engine 是 None 而 app.state.config 还是旧的。_engine() 若此时
    惰性重建，会用旧配置造一个默认世界的引擎写回 app.state：activate 返回后，注册表和
    config 都说是 sim-1，真正的引擎却写着默认世界，activate 刚建好的引擎被丢成孤儿
    （它的 tick/摄入线程还在跑）。窗口内应当 503 world_switching。"""
    import starling.dashboard.engine as engmod
    import starling.dashboard.world_manager as wm
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    mgr = app.state.worlds
    mgr.create("sim-1", "")
    real = engmod.DashboardEngine
    building, proceed = threading.Event(), threading.Event()
    lazy_builds = []

    def _slow_open(cfg):
        if cfg.tenant == "sim-1":
            building.set()
            assert proceed.wait(15)
        return real(cfg)

    def _spy_lazy(cfg):
        lazy_builds.append(cfg.tenant)       # commands._engine 惰性重建走这里
        return real(cfg)
    monkeypatch.setattr(wm, "DashboardEngine", _slow_open)
    monkeypatch.setattr(engmod, "DashboardEngine", _spy_lazy)
    outcome: list = []
    switcher = threading.Thread(target=lambda: outcome.append(mgr.activate("sim-1")), daemon=True)
    switcher.start()
    try:
        assert building.wait(10)
        assert app.state.engine is None      # 窗口确实打开了：旧引擎已丢、新引擎未建好
        for method, path in (("post", "/api/tick"), ("get", "/api/runtime_health"),
                             ("get", "/api/ingest_status")):
            kwargs = {"json": {}} if method == "post" else {}
            r = getattr(client, method)(path, **kwargs)
            assert (r.status_code, r.json()["detail"]) == (503, "world_switching"), path
        assert app.state.engine is None and lazy_builds == []
    finally:
        proceed.set()
        switcher.join(15)
    assert outcome == [None]
    new = app.state.engine
    assert new is not None and new._cfg is app.state.config
    assert new._cfg.tenant == "sim-1" and lazy_builds == []
    assert client.post("/api/tick", json={}).status_code == 200      # 窗口一过，正常服务
    assert client.get("/api/runtime_health").status_code == 200
    assert new.quiesce() is True


def test_lazy_engine_build_still_works_when_not_switching(tmp_path):
    client, app = _client(tmp_path)
    assert app.state.engine is None
    assert client.post("/api/tick", json={}).status_code == 200
    assert app.state.engine is not None and app.state.engine._cfg is app.state.config


def test_lazy_build_and_switch_do_not_race_on_a_never_built_engine(tmp_path, monkeypatch):
    """engine 从未建过（惰性）时，切换开始的那一刻若有惰性构建正在进行，切换要等它
    建完再接手，而不是并行再建一个、互相覆盖。"""
    import starling.dashboard.engine as engmod
    client, app = _client(tmp_path)
    mgr = app.state.worlds
    mgr.create("sim-1", "")
    real = engmod.DashboardEngine
    in_build, proceed = threading.Event(), threading.Event()
    built = []

    def _slow(cfg):
        built.append(cfg.tenant)
        if len(built) == 1:
            in_build.set()
            assert proceed.wait(15)
        return real(cfg)
    monkeypatch.setattr(engmod, "DashboardEngine", _slow)
    import starling.dashboard.world_manager as wm
    monkeypatch.setattr(wm, "DashboardEngine", _slow)
    lazy = threading.Thread(target=lambda: client.post("/api/tick", json={}), daemon=True)
    lazy.start()
    assert in_build.wait(10)
    switch = threading.Thread(target=lambda: mgr.activate("sim-1"), daemon=True)
    switch.start()
    time.sleep(0.3)
    assert built == ["default"]              # 切换还在等惰性构建，没有并行再建
    proceed.set()
    lazy.join(15)
    switch.join(15)
    assert built == ["default", "sim-1"]
    assert app.state.engine._cfg.tenant == "sim-1" and app.state.config.tenant == "sim-1"
    assert app.state.engine.quiesce() is True


# ── 切换时先存注册表、后发布引擎；保存失败回到旧世界 ──

def _boom_save(_reg):
    raise OSError("No space left on device")


def test_activate_registry_save_failure_rolls_back_to_old_world(tmp_path, monkeypatch):
    """save 在引擎已发布之后才失败的旧顺序：activate 抛裸 OSError，注册表说 default 而
    config/engine 已是 sim-1，此后「切到 default」被当成 no-op，写入落进 sim-1，
    还能把正在写的 sim-1 目录删掉。新顺序：开库 -> 存注册表 -> 发布；存失败回滚。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    state.config.tick_interval_s = 60.0
    mgr.workers_enabled = True
    eng = state.engine
    eng.start_background_tick(60.0)
    eng.start_ingest_worker()
    _remember(eng, "Bob owns auth")
    mgr.create("sim-1", "")
    before = mgr.load()
    old_cfg = state.config
    built = []
    real_cls = DashboardEngine
    import starling.dashboard.world_manager as wm

    def _track(cfg):
        engine = real_cls(cfg)
        built.append((cfg.tenant, engine))
        return engine
    monkeypatch.setattr(wm, "DashboardEngine", _track)
    monkeypatch.setattr(mgr, "save", _boom_save)
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "world_open_failed"
    assert "registry write failed" in ei.value.detail and "No space left" in ei.value.detail
    monkeypatch.undo()
    assert state.config is old_cfg and state.config.tenant == "default"
    assert state.engine is not None and state.engine._cfg is old_cfg
    assert mgr.load() == before                              # 注册表原样
    assert mgr.switching is False
    # 被丢弃的 sim-1 引擎没起过线程；回滚回来的旧世界引擎线程在跑
    sim_engines = [e for tenant, e in built if tenant == "sim-1"]
    assert len(sim_engines) == 1
    assert sim_engines[0]._tick_thread is None and sim_engines[0]._ingest_thread is None
    assert state.engine._tick_thread is not None and state.engine._tick_thread.is_alive()
    assert state.engine._ingest_thread is not None and state.engine._ingest_thread.is_alive()
    _remember(state.engine, "Carol owns billing")            # 回滚回来的引擎能写
    # 之后一次正常的切换照样成功
    mgr.activate("sim-1")
    assert state.config.tenant == "sim-1" and mgr.load()["active"] == "sim-1"
    assert state.engine.quiesce() is True


def test_activate_save_failure_and_rollback_failure_both_reported(tmp_path, monkeypatch):
    import starling.dashboard.world_manager as wm
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    real_cls = wm.DashboardEngine
    calls = []

    def _second_build_fails(cfg):
        calls.append(cfg.tenant)
        if len(calls) == 2:                                   # 回滚重建旧世界
            raise RuntimeError("old db gone")
        return real_cls(cfg)
    monkeypatch.setattr(wm, "DashboardEngine", _second_build_fails)
    monkeypatch.setattr(mgr, "save", _boom_save)
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "world_open_failed"
    assert "registry write failed" in ei.value.detail and "old db gone" in ei.value.detail
    assert state.engine is None and state.config.tenant == "default"
    assert mgr.switching is False


def test_activate_noop_checks_live_config_not_just_registry(tmp_path, monkeypatch):
    """注册表说 default 是活动世界，但 live config 实际指着 sim-1（任何让两者分叉的
    路径）：切到 default 必须真的切，不能因为注册表这么说就当成 no-op。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    mgr.activate("sim-1")
    mgr.save(_core.world_set_active(mgr.load(), "default"))   # 人为造出分叉
    assert mgr.load()["active"] == "default" and state.config.tenant == "sim-1"
    old_engine = state.engine
    mgr.activate("default")
    assert state.engine is not old_engine
    assert state.config.tenant == "default"
    assert state.config.db_path == str(tmp_path / "dashboard.db")
    assert mgr.load()["active"] == "default"


def test_delete_refuses_the_world_the_live_engine_is_using(tmp_path, monkeypatch):
    """不信注册表的 active 字段：live config 指着的库，哪怕注册表说它不是活动世界，
    也不能删（macOS 上删目录后进程继续写 unlinked inode，重启即丢）。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    mgr.activate("sim-1")
    mgr.save(_core.world_set_active(mgr.load(), "default"))   # 注册表与 live config 分叉
    world_dir = os.path.dirname(state.config.db_path)
    with pytest.raises(_core.WorldStoreError) as ei:
        mgr.delete("sim-1")
    assert _code(ei.value) == "world_protected"
    assert os.path.isdir(world_dir) and "sim-1" in mgr.load()["worlds"]
    mgr.activate("default")
    mgr.delete("sim-1")                                       # 不再被使用后才能删
    assert not os.path.exists(world_dir)


def test_delete_of_an_unused_world_still_works(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    entry = mgr.create("sim-1", "")
    mgr.delete("sim-1")                                       # 没被使用：照常删
    assert not os.path.exists(os.path.dirname(entry["db_path"]))


def test_routes_non_domain_exception_is_json_500_internal_error(tmp_path, monkeypatch, caplog):
    client, app = _client(tmp_path)

    def _raise(_name):
        raise OSError("disk exploded at /secret/path")
    monkeypatch.setattr(app.state.worlds, "activate", _raise)
    with caplog.at_level("ERROR"):
        r = client.post("/api/worlds/default/activate")
    assert r.status_code == 500 and r.headers["content-type"].startswith("application/json")
    assert r.json() == {"detail": "internal_error"}            # 不把异常文本（含路径）泄给客户端
    assert "disk exploded" in caplog.text                       # 服务端日志里有


def test_routes_list_survives_one_unreadable_world_db(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    created = client.post("/api/worlds", json={"name": "sim-1"}).json()
    assert created["name"] == "sim-1" and "stats_error" not in created
    db = app.state.worlds.load()["worlds"]["sim-1"]["db_path"]
    os.makedirs(os.path.dirname(db), exist_ok=True)
    with open(db, "wb") as fh:
        fh.write(b"this is not a sqlite database" * 100)
    r = client.get("/api/worlds")
    assert r.status_code == 200
    rows = {w["name"]: w for w in r.json()["worlds"]}
    assert rows["sim-1"]["stats_error"] is True
    assert (rows["sim-1"]["db_bytes"], rows["sim-1"]["live_bytes"],
            rows["sim-1"]["statements"], rows["sim-1"]["engrams"]) == (0, 0, 0, 0)
    assert rows["default"].get("stats_error", False) is False
    assert rows["default"]["db_bytes"] > 0                      # 好的世界照常有统计
    assert client.delete("/api/worlds/sim-1", params={"confirm": "sim-1"}).status_code == 200
    assert [w["name"] for w in client.get("/api/worlds").json()["worlds"]] == ["default"]


# ───────────────────────── Codex 审查修复轮 ─────────────────────────

def _insert_foreign_engram(db_path: str, tenant: str) -> None:
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
        "VALUES('x-1',?,'hx','conversation','default','inline','normal','audit_retain',"
        "'2026-10-25T00:00:00Z','x-1')", (tenant,))
    con.commit()
    con.close()


def _migrated_world_db(mgr, name: str) -> str:
    db = mgr.load()["worlds"][name]["db_path"]
    adapter = _core.SqliteAdapter.open(db)   # 跑迁移建库
    del adapter
    gc.collect()
    return db


# ── I6：zvec 拒绝在 C++ 里 ──

def test_binding_take_snapshot_refuses_non_sqlite_backend_in_cpp(tmp_path):
    reg = _core.world_ensure_registry(str(tmp_path / "w.json"), str(tmp_path / "d.db"), "default")
    reg = _core.world_create(reg, str(tmp_path), "sim-1", "", "2026-10-25T01:00:00Z")["registry"]
    _core.SqliteAdapter.open(reg["worlds"]["sim-1"]["db_path"])
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_take_snapshot(reg, "sim-1", vector_backend="zvec")
    assert _code(ei.value) == "snapshot_unsupported_backend"
    assert os.listdir(reg["worlds"]["sim-1"]["snapshot_dir"]) == []


# ── I1：租户不变式在激活时校验 ──

def test_activate_refuses_world_with_foreign_tenant_rows(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    mgr = app.state.worlds
    mgr.create("sim-1", "")
    _insert_foreign_engram(_migrated_world_db(mgr, "sim-1"), "intruder")
    engine, cfg = app.state.engine, app.state.config
    r = client.post("/api/worlds/sim-1/activate")
    assert (r.status_code, r.json()["detail"]) == (409, "world_tenant_mismatch")
    assert app.state.engine is engine and app.state.config is cfg     # 状态不前进
    assert mgr.load()["active"] == "default" and mgr.switching is False
    assert client.post("/api/tick", json={}).status_code == 200      # 旧世界照常服务


def test_binding_verify_tenant(tmp_path):
    db = str(tmp_path / "w.db")
    _core.world_verify_tenant(db, "sim-1")                          # 库不存在：新世界，放行
    _core.SqliteAdapter.open(db)
    _core.world_verify_tenant(db, "sim-1")
    _insert_foreign_engram(db, "intruder")
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_verify_tenant(db, "sim-1")
    assert _code(ei.value) == "world_tenant_mismatch" and "engrams" in str(ei.value)


def test_activate_noop_also_compares_tenant(tmp_path, monkeypatch):
    """live config 指着同一个库、租户却与注册表不一致：不是「已激活」，要按注册表的租户
    重建引擎。只比 db_path 的话这次切换被当成 no-op，此后写入都带着错的租户。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    mgr.activate("sim-1")
    state.config.tenant = "drifted"                 # 人为造出租户分叉，库路径不变
    old_engine = state.engine
    mgr.activate("sim-1")
    assert state.engine is not old_engine
    assert state.config.tenant == "sim-1" and state.engine._core.tenant == "sim-1"


# ── I2 / I3：快照的崩溃残留与保存失败补偿 ──

def test_snapshot_save_failure_discards_new_file_and_is_json_500(tmp_path, monkeypatch):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    mgr = app.state.worlds
    before = mgr.load()
    snap_dir = before["worlds"]["default"]["snapshot_dir"]
    monkeypatch.setattr(mgr, "save", _boom_save)
    r = client.post("/api/worlds/default/snapshots", json={})
    assert r.status_code == 500 and r.json() == {"detail": "internal_error"}
    monkeypatch.undo()
    assert mgr.load() == before
    leftovers = [n for n in os.listdir(snap_dir)] if os.path.isdir(snap_dir) else []
    assert leftovers == [], "注册表没存下来，新快照文件必须删掉，否则就是列不出来的孤儿"


def test_snapshot_sweeps_crash_leftovers(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, _state = _manager(tmp_path)
    first = mgr.take_snapshot("default", "")
    snap_dir = os.path.dirname(first["path"])
    partial = os.path.join(snap_dir, "20260101T000000Z-dead.db.partial")
    orphan = os.path.join(snap_dir, "20260101T000000Z-beef.db")
    for path in (partial, orphan):
        with open(path, "w") as fh:
            fh.write("x")
    second = mgr.take_snapshot("default", "")
    assert not os.path.exists(partial) and not os.path.exists(orphan)
    assert os.path.exists(first["path"]) and os.path.exists(second["path"])


def test_routes_report_missing_snapshot_file_and_allow_delete(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    snap = client.post("/api/worlds/default/snapshots", json={}).json()
    path = app.state.worlds.load()["snapshots"]["default"][0]["path"]
    os.remove(path)
    listed = client.get("/api/worlds/default/snapshots").json()["snapshots"]
    assert len(listed) == 1
    assert listed[0]["missing"] is True and listed[0]["size_bytes"] == 0
    assert client.get("/api/worlds").json()["worlds"][0]["snapshot_bytes"] == 0
    assert client.delete(f"/api/worlds/default/snapshots/{snap['id']}").status_code == 200
    assert client.get("/api/worlds/default/snapshots").json() == {"snapshots": []}


# ── I5：切换窗口内所有检视路由都回 503 ──

def _force_switching(mgr, value: bool) -> None:
    with mgr._gate:
        mgr.switching = value


@pytest.mark.parametrize("path", ["/api/overview", "/api/statements", "/api/engrams",
                                  "/api/vitals", "/api/brain_map"])
def test_inspect_sql_routes_503_during_switch_window(tmp_path, path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    assert client.get(path).status_code == 200
    _force_switching(app.state.worlds, True)
    try:
        r = client.get(path)
        assert (r.status_code, r.json()["detail"]) == (503, "world_switching")
    finally:
        _force_switching(app.state.worlds, False)


# ── I8：注入的引擎必须与引导后的 config 一致 ──

def test_create_app_rejects_engine_for_another_db(tmp_path):
    eng = DashboardEngine(DashboardConfig(db_path=str(tmp_path / "other.db"), token="",
                                          tick_interval_s=0, source_lane_enabled=False))
    with pytest.raises(ValueError) as ei:
        create_app(_cfg(tmp_path), engine=eng)
    assert "other.db" in str(ei.value) and "dashboard.db" in str(ei.value)


def test_create_app_rejects_engine_when_registry_overrides_shared_config(tmp_path):
    """生产形态的隐患：引擎与 create_app 共用同一个 cfg 对象，bootstrap 原地把它改成注册表
    里的活动世界，而引擎早已按改之前的路径开了库。比 cfg 字段永远相等，必须比引擎实际
    打开的库。"""
    create_app(_cfg(tmp_path))                        # 注册表：default -> dashboard.db
    cfg = _cfg(tmp_path)
    cfg.db_path = str(tmp_path / "elsewhere.db")
    eng = DashboardEngine(cfg)
    with pytest.raises(ValueError):
        create_app(cfg, engine=eng)


def test_create_app_accepts_matching_injected_engine(tmp_path):
    cfg = _cfg(tmp_path)
    app = create_app(cfg, engine=DashboardEngine(cfg))
    assert app.state.engine is not None


# ── C1：引擎租约覆盖整个请求 ──

def test_activate_times_out_on_stuck_lease_and_old_world_keeps_working(tmp_path, monkeypatch):
    import starling.dashboard.world_manager as wm
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    monkeypatch.setattr(wm, "_LEASE_DRAIN_TIMEOUT_S", 0.3)
    mgr, state = _manager(tmp_path)
    state.config.tick_interval_s = 60.0
    mgr.workers_enabled = True
    eng, cfg = state.engine, state.config
    eng.start_background_tick(60.0)
    eng.start_ingest_worker()
    mgr.create("sim-1", "")
    holding, release = threading.Event(), threading.Event()

    def _request():
        with mgr.lease():
            holding.set()
            release.wait(10)

    req = threading.Thread(target=_request, daemon=True)
    req.start()
    assert holding.wait(5)
    try:
        with pytest.raises(WorldSwitchError) as ei:
            mgr.activate("sim-1")
        assert ei.value.code == "ingest_busy" and "1 request" in ei.value.detail
        assert state.engine is eng and state.config is cfg
        assert mgr.load()["active"] == "default" and mgr.switching is False
        assert eng._tick_thread is not None and eng._tick_thread.is_alive()
        assert eng._ingest_thread is not None and eng._ingest_thread.is_alive()
    finally:
        release.set()
        req.join(5)
    _remember(eng, "Bob owns auth")                    # 旧世界照常工作
    with mgr.lease() as again:                         # 窗口关了，新租约照常发
        assert again is eng
    assert eng.quiesce() is True


def test_new_request_during_lease_drain_gets_503(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    mgr = app.state.worlds
    mgr.create("sim-1", "")
    holding, release = threading.Event(), threading.Event()

    def _request():
        with mgr.lease():
            holding.set()
            release.wait(10)

    req = threading.Thread(target=_request, daemon=True)
    req.start()
    assert holding.wait(5)
    switcher = threading.Thread(target=lambda: mgr.activate("sim-1"), daemon=True)
    switcher.start()
    try:
        deadline = time.monotonic() + 5
        while not mgr.switching and time.monotonic() < deadline:
            time.sleep(0.01)
        assert mgr.switching is True                   # 切换在等租约归零
        for method, path in (("post", "/api/tick"), ("post", "/api/recall"),
                             ("get", "/api/overview"), ("get", "/api/runtime_health")):
            kwargs = {"json": {"query": "x"}} if path == "/api/recall" else (
                {"json": {}} if method == "post" else {})
            r = getattr(client, method)(path, **kwargs)
            assert (r.status_code, r.json()["detail"]) == (503, "world_switching"), path
    finally:
        release.set()
        req.join(5)
        switcher.join(15)
    assert app.state.config.tenant == "sim-1"
    assert client.post("/api/tick", json={}).status_code == 200


def test_ws_converse_refused_during_switch_window_gets_world_switching_frame(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    app.state.engine.llm = fake
    _force_switching(app.state.worlds, True)
    try:
        with client.websocket_connect("/ws/converse") as ws:
            ws.send_json({"message": "who owns auth?"})
            assert ws.receive_json() == {"type": "error", "error": "world_switching"}
    finally:
        _force_switching(app.state.worlds, False)
    with client.websocket_connect("/ws/converse") as ws:     # 窗口一过照常对话
        ws.send_json({"message": "who owns auth?"})
        while (msg := ws.receive_json())["type"] in ("token", "status"):
            pass
        assert msg["type"] == "done"


def test_config_hot_swap_holds_a_lease(tmp_path, monkeypatch):
    app, _cfgfile = _config_app(tmp_path, monkeypatch)
    client = TestClient(app)
    _force_switching(app.state.worlds, True)
    try:
        r = client.post("/api/config", json=_CFG_BODY)
        assert (r.status_code, r.json()["detail"]) == (503, "world_switching")
        r = client.delete("/api/config/provider/default")
        assert (r.status_code, r.json()["detail"]) == (503, "world_switching")
    finally:
        _force_switching(app.state.worlds, False)
    assert client.post("/api/config", json=_CFG_BODY).status_code == 200


def test_slow_remember_spanning_a_switch_then_switching_back_leaves_one_runtime(
        tmp_path, monkeypatch):
    """remember 的抽取段在引擎锁外：旧实现只等持锁段，切换先返回，这条请求之后在旧引擎
    上提交，旧 Runtime 一直活着；再切回原世界就是同一个库上的两条写连接。租约让切换等
    整条请求结束。"""
    import starling.dashboard.world_manager as wm
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    fake.set_delay_ms(800)                              # 锁外抽取段拉长
    app.state.engine.llm = fake
    mgr = app.state.worlds
    mgr.create("sim-1", "")
    runtimes = [weakref.ref(app.state.engine._rt)]
    real_cls = wm.DashboardEngine

    def _track(cfg):
        engine = real_cls(cfg)
        runtimes.append(weakref.ref(engine._rt))
        return engine
    monkeypatch.setattr(wm, "DashboardEngine", _track)
    del fake

    remembered: list = []
    req = threading.Thread(target=lambda: remembered.append(
        client.post("/api/remember", json={"text": "Bob owns auth"})), daemon=True)
    req.start()
    time.sleep(0.4)                                     # 已进锁外抽取段
    switched = threading.Event()
    switcher = threading.Thread(target=lambda: (mgr.activate("sim-1"), switched.set()),
                                daemon=True)
    switcher.start()
    assert not switched.wait(0.2), "remember 还在飞，切换不该完成"
    # 不等租约的实现此刻已把旧引擎丢成 None（只是在宽限期里等旧 Runtime 回收）。
    assert app.state.engine is not None and app.state.config.tenant == "default"
    req.join(15)
    assert switched.wait(15)
    switcher.join(5)
    assert remembered and remembered[0].status_code == 200
    gc.collect()
    assert runtimes[0]() is None, "请求结束后旧 Runtime 必须已释放"
    # 写入归属正确：切换前开始的请求写进旧世界
    default_db = mgr.load()["worlds"]["default"]["db_path"]
    con = sqlite3.connect(f"file:{default_db}?mode=ro", uri=True)
    assert con.execute("SELECT COUNT(*) FROM engrams").fetchone()[0] == 1
    con.close()

    mgr.activate("default")                             # 切回原世界
    gc.collect()
    alive = [ref for ref in runtimes if ref() is not None]
    assert len(alive) == 1 and alive[0]() is app.state.engine._rt


# ── M2：converse 与 config 热更新整段持有租约（不是「查一下就还」） ──

def _wait_until(pred, timeout=5.0) -> bool:
    deadline = time.monotonic() + timeout
    while not pred() and time.monotonic() < deadline:
        time.sleep(0.01)
    return pred()


def test_switch_waits_for_an_in_flight_converse_turn(tmp_path, monkeypatch):
    """/ws/converse 的生成段在引擎锁外。租约若只在入口查一下就还，切换会在这一轮还在生成时
    完成：旧引擎被丢、这一轮随后在旧引擎上沉淀，旧 Runtime 一直活着。要求：生成被卡住时
    切换在等，放行后这一轮先完成、切换后完成，旧 Runtime 随之释放。"""
    import starling.dashboard.world_manager as wm
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)
    mgr = app.state.worlds
    mgr.create("sim-1", "")
    old_rt = weakref.ref(app.state.engine._rt)
    generating, release = threading.Event(), threading.Event()
    real_stream = DashboardEngine.converse_stream

    def _blocked_stream(self, message, **kwargs):
        generating.set()
        assert release.wait(10), "test never released the turn"
        return {"reply": "ok", "statement_ids": [], "remember_ok": True}
    monkeypatch.setattr(DashboardEngine, "converse_stream", _blocked_stream)

    frames: list = []

    def _turn():
        with client.websocket_connect("/ws/converse") as ws:
            ws.send_json({"message": "who owns auth?"})
            while True:
                msg = ws.receive_json()
                frames.append(msg)
                if msg["type"] in ("done", "error"):
                    return
    turn = threading.Thread(target=_turn, daemon=True)
    turn.start()
    assert generating.wait(5), "converse turn never reached generation"

    switched = threading.Event()
    switcher = threading.Thread(target=lambda: (mgr.activate("sim-1"), switched.set()),
                                daemon=True)
    switcher.start()
    try:
        assert _wait_until(lambda: mgr.switching), "switch never started"
        assert not switched.wait(0.3), "converse turn still generating; switch must wait"
        # 不等租约的实现此刻已经把旧引擎丢成 None（只是在宽限期里等旧 Runtime 回收）。
        assert app.state.engine is not None and app.state.config.tenant == "default"
    finally:
        release.set()
    turn.join(15)
    assert switched.wait(15)
    switcher.join(5)
    assert frames and frames[-1]["type"] == "done", frames
    assert app.state.config.tenant == "sim-1" and mgr.load()["active"] == "sim-1"
    monkeypatch.setattr(DashboardEngine, "converse_stream", real_stream)
    gc.collect()
    assert old_rt() is None, "the turn finished, so the old Runtime must be released"
    assert wm._LEASE_DRAIN_TIMEOUT_S > 0.3                  # 测试窗口远小于超时


def test_switch_waits_for_an_in_flight_config_hot_swap(tmp_path, monkeypatch):
    """config 热更新在线程池里换适配器（_apply）。租约若只在入口查一下就还，切换会在热更新
    还在跑时完成，适配器装到已被丢弃的旧引擎上。要求：_apply 被卡住时切换在等。"""
    app, _cfgfile = _config_app(tmp_path, monkeypatch)
    client = TestClient(app)
    mgr = app.state.worlds
    mgr.create("sim-1", "")
    applying, release = threading.Event(), threading.Event()
    eng = app.state.engine
    real_set_llm = eng.set_llm

    def _blocked_set_llm(spec):
        applying.set()
        assert release.wait(10), "test never released the hot-swap"
        return real_set_llm(spec)
    monkeypatch.setattr(eng, "set_llm", _blocked_set_llm)
    del eng

    responses: list = []
    req = threading.Thread(target=lambda: responses.append(
        client.post("/api/config", json=_CFG_BODY)), daemon=True)
    req.start()
    assert applying.wait(5), "hot-swap never reached _apply"

    switched = threading.Event()
    switcher = threading.Thread(target=lambda: (mgr.activate("sim-1"), switched.set()),
                                daemon=True)
    switcher.start()
    try:
        assert _wait_until(lambda: mgr.switching), "switch never started"
        assert not switched.wait(0.3), "hot-swap still running; switch must wait"
        assert app.state.engine is not None and app.state.config.tenant == "default"
    finally:
        release.set()
    req.join(15)
    assert switched.wait(15)
    switcher.join(5)
    assert responses and responses[0].status_code == 200
    assert app.state.config.tenant == "sim-1"
