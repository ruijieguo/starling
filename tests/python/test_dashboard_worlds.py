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
        worlds.create("sim-1", "")
        worlds.activate("sim-1")
        new = app.state.engine
        assert new is not old
        assert old._tick_thread is None and old._ingest_thread is None
        assert new._tick_thread is not None and new._tick_thread.is_alive()
        assert new._ingest_thread is not None and new._ingest_thread.is_alive()
    assert worlds.workers_enabled is False
    assert new._tick_thread is None and new._ingest_thread is None   # 关停时已停


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
    mgr.create("sim-1", "")
    # 让新世界的库文件是一个目录：SqliteAdapter.open 必然失败
    reg = mgr.load()
    os.makedirs(reg["worlds"]["sim-1"]["db_path"])
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "world_open_failed"
    assert state.engine is not None
    assert state.config.tenant == "default"
    assert mgr.load()["active"] == "default"


def test_activate_refuses_when_ingest_will_not_stop(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    monkeypatch.setattr(state.engine, "quiesce", lambda timeout_s=5.0: False)
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "ingest_busy"
    assert mgr.load()["active"] == "default"


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
        time.sleep(0.2)                 # 切换线程已在排队等引擎锁（在飞段还没结束）
        go_first.set()                  # 在飞段结束，切换线程拿到锁
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
    """在飞请求（持引擎锁）结束之前，旧引擎不能被丢弃。"""
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    eng = state.engine
    holding, release = threading.Event(), threading.Event()

    def _request():
        with eng._lock:
            holding.set()
            release.wait(10)

    req = threading.Thread(target=_request, daemon=True)
    req.start()
    assert holding.wait(5)
    done = threading.Event()
    switcher = threading.Thread(target=lambda: (mgr.activate("sim-1"), done.set()), daemon=True)
    switcher.start()
    assert not done.wait(0.3), "请求还没结束，切换不该完成"
    assert state.engine is eng
    release.set()
    assert done.wait(10)
    assert state.config.tenant == "sim-1"
    req.join(5)


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
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    state.config.vector_backend = "zvec"
    with pytest.raises(WorldSwitchError) as ei:
        mgr.take_snapshot("default", "")
    assert ei.value.code == "snapshot_unsupported_backend"
    assert mgr.load()["snapshots"].get("default", []) == []


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
    ("snapshot_unsupported_backend", 409),
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
