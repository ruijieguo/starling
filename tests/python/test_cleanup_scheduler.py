"""自动清理的调度（记忆服务第 6 期 Task 6.2，spec §9；裁定 R44、R64、R74、R103）。

规则、删除与清理记录全在 C++（_core.world_cleanup_plan / execute / log，Task 6.1）。池只做三件事：按间隔调度一轮；对每个候选
在它的世界锁内、关闭窗口里确认此刻没开着（没有引擎，会话表 forget_world 通过）；仍持着世界锁时把这一个候选交给 C++ 删。
这里钉住的是这三件事，尤其是「确认没开」与「删除」在同一次世界锁持有期间完成（open 与清理的竞态，两种顺序都测）。
"""
import gc
import os
import threading
import time

import pytest

from starling import _core
from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine
from starling.dashboard.world_manager import WorldPool, WorldSwitchError

NOW = "2026-11-20T00:00:00Z"
STALE = "2026-11-01T00:00:00Z"      # 19 天前
FRESH = "2026-11-19T00:00:00Z"      # 1 天前


class _Wall:
    """注入的墙钟（YYYY-MM-DDTHH:MM:SSZ），测试手动推进。"""

    def __init__(self, now: str = NOW) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now


class _Mono:
    """注入的单调时钟（毫秒），会话表用。"""

    def __init__(self, start_ms: int = 1_000_000) -> None:
        self.now = start_ms

    def __call__(self) -> int:
        return self.now


def _cfg(tmp_path, **over):
    base = dict(db_path=str(tmp_path / "dashboard.db"), token="", tick_interval_s=0,
                source_lane_enabled=False, ingest_spool_path=str(tmp_path / "spool"))
    base.update(over)
    return DashboardConfig(**base)


def _pool(tmp_path, *, sessions: bool = True, **cfg_over):
    cfg = _cfg(tmp_path, **cfg_over)
    reg = _core.WorldRegistry.open(cfg.data_dir, cfg.db_path, cfg.tenant)
    wall, mono = _Wall(), _Mono()
    pool = WorldPool(reg, cfg, clock=wall, monotonic_ms=mono)
    table = None
    if sessions:
        table = _core.SessionTable()
        pool.attach_sessions(table)
    pool.sync_default_settings()
    pool.lease(pool.default_world()).release()
    return pool, reg, table, wall, mono


@pytest.fixture
def setup(tmp_path):
    pool, reg, table, wall, mono = _pool(tmp_path)
    try:
        yield pool, reg, table, wall, mono
    finally:
        pool.close_all()
        gc.collect()


def _rollout(pool, name: str, created_at: str, group: str = "run1") -> dict:
    """rise 的用法：从部署世界分叉一个可回收世界（分组 = run_id），created_at 由注入的墙钟定。"""
    try:
        pool.record("deploy")
    except WorldSwitchError:
        pool.create_world("deploy", "")
    saved = pool._clock
    pool._clock = lambda: created_at
    try:
        return pool.fork_world("deploy", name, reclaimable=True, retention_group=group)["world"]
    finally:
        pool._clock = saved


def _home(reg, dir_id: str) -> str:
    return os.path.join(str(reg.data_dir), "worlds", dir_id)


def _gone(pool, name: str) -> bool:
    try:
        pool.record(name)
    except WorldSwitchError as exc:
        return exc.code == "world_not_found"
    return False


def _log(reg, limit: int = 50) -> list[tuple[str, str, str]]:
    return [(e["world"], e["action"], e["reason"]) for e in _core.world_cleanup_log(reg, limit)]


# ───────────────────────── 一轮清理 ─────────────────────────

def test_cleanup_round_removes_over_count_and_over_age_and_logs(setup):
    pool, reg, _table, wall, _mono = setup
    old = _rollout(pool, "old", STALE)
    _rollout(pool, "c0", "2026-11-19T00:00:00Z", group="run2")
    _rollout(pool, "c1", "2026-11-19T00:00:01Z", group="run2")
    _rollout(pool, "c2", "2026-11-19T00:00:02Z", group="run2")
    keep = _rollout(pool, "new", FRESH)
    pool._cleanup_config = dict(pool._cleanup_config, keep_per_group=2)

    out = pool.cleanup_round()
    assert sorted(out["removed"]) == ["c0", "old"]
    assert out["skipped"] == [] and out["archives_removed"] == 0
    assert _gone(pool, "old") and _gone(pool, "c0")
    assert not os.path.exists(_home(reg, old["dir_id"]))
    assert os.path.isdir(_home(reg, keep["dir_id"]))
    for name in ("c1", "c2", "new", "deploy", "default"):
        assert pool.record(name)["name"] == name
    assert set(_log(reg)) == {("old", "removed", "over_age"), ("c0", "removed", "over_count")}
    assert all(e["at"] == wall.now for e in _core.world_cleanup_log(reg, 50))
    # 同一时刻再跑一轮：没有可删的，什么都不记。
    assert pool.cleanup_round() == {"removed": [], "skipped": [], "archives_removed": 0}
    assert len(_log(reg)) == 2


def _crash_after_unregister(reg_path, world: str, dir_id: str) -> None:
    """造出「注册项已摘、目录还在、cleanup_log 带待删标记」（execute_cleanup 摘完注册项、删目录之前被杀）。与 C++ 测试
    NextRunFinishesADirectoryLeftPendingByACrash 的 simulate_crash_after_unregister 同一组语句。调用时注册表不能有别的连接。"""
    import sqlite3
    con = sqlite3.connect(str(reg_path), isolation_level=None)
    try:
        con.executescript(
            "BEGIN;"
            "INSERT INTO cleanup_log (at, world, retention_group, action, reason, dir_id, pending_dir) "
            f"VALUES ('2026-11-19T00:00:00Z', '{world}', 'run1', 'removed', 'over_age', '{dir_id}', 1);"
            f"DELETE FROM world_labels WHERE name = '{world}';"
            f"DELETE FROM snapshots WHERE world = '{world}';"
            f"DELETE FROM worlds WHERE name = '{world}';"
            "COMMIT;")
    finally:
        con.close()


def _pending_marks(reg_path) -> int:
    import sqlite3
    con = sqlite3.connect(f"file:{reg_path}?mode=ro", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM cleanup_log WHERE pending_dir = 1").fetchone()[0]
    finally:
        con.close()


def test_round_with_nothing_due_finishes_a_directory_left_pending(tmp_path):
    """裁定 R106 I1：补删（C++ finish_pending_dirs）每轮都跑，不只在这一轮有候选、跳过项或归档时才跑。崩溃留下的待删目录
    在下一轮（哪怕什么都不该删）被删掉，标记清掉；补删不另记一条。"""
    pool, reg, _table, _wall, _mono = _pool(tmp_path)
    rec = _rollout(pool, "half-done", FRESH)
    home = _home(reg, rec["dir_id"])
    with open(os.path.join(home, "world.db.leftover"), "w", encoding="utf-8") as fh:
        fh.write("x")
    reg_path = os.path.join(str(reg.data_dir), "registry.db")
    pool.close_all()
    del pool, reg, _table
    gc.collect()
    _crash_after_unregister(reg_path, "half-done", rec["dir_id"])

    pool, reg, _table, _wall, _mono = _pool(tmp_path)        # 重启之后的第一轮
    try:
        assert os.path.isdir(home) and _pending_marks(reg_path) == 1
        plan = _core.world_cleanup_plan(reg, NOW, pool._cleanup_open_worlds(), **pool._cleanup_config)
        assert plan == {"remove": [], "skip": [], "archives": []}      # 这一轮没有任何活
        assert pool.cleanup_round() == {"removed": [], "skipped": [], "archives_removed": 0}
        assert not os.path.exists(home)
        assert _pending_marks(reg_path) == 0
        assert _log(reg) == [("half-done", "removed", "over_age")]   # 补删不另记
    finally:
        pool.close_all()
        gc.collect()


def test_pending_sweep_failure_is_logged_and_the_round_goes_on(setup, monkeypatch, caplog):
    """开头那次补删抛异常：记日志，这一轮照常往下跑（与单个候选出错一样）。"""
    pool, _reg, _table, _wall, _mono = setup
    _rollout(pool, "old", STALE)
    real_execute = _core.world_cleanup_execute

    def flaky(reg_, plan, now, **cfg):
        if not plan["remove"] and not plan["skip"] and not plan["archives"]:
            raise RuntimeError("sweep boom")
        return real_execute(reg_, plan, now, **cfg)
    monkeypatch.setattr(_core, "world_cleanup_execute", flaky)
    assert pool.cleanup_round()["removed"] == ["old"]
    assert "pending directory sweep failed" in caplog.text


def test_cleanup_round_uses_the_injected_clock(setup):
    """now 缺省取池注入的墙钟：时钟没推进时不超龄，推进 14 天以上才删。"""
    pool, _reg, _table, wall, _mono = setup
    _rollout(pool, "w", "2026-11-19T00:00:00Z")
    wall.now = "2026-11-20T00:00:00Z"
    assert pool.cleanup_round()["removed"] == []
    wall.now = "2026-12-04T00:00:01Z"                     # 14 天零 1 秒
    assert pool.cleanup_round()["removed"] == ["w"]
    # 显式给的 now 优先。
    _rollout(pool, "v", "2026-12-01T00:00:00Z")
    assert pool.cleanup_round(now="2026-12-02T00:00:00Z")["removed"] == []
    assert pool.cleanup_round(now="2026-12-20T00:00:00Z")["removed"] == ["v"]


def test_cleanup_round_passes_the_same_config_to_plan_and_execute(setup, monkeypatch):
    """裁定 R74：plan 与 execute 收同一份配置（只给 plan 传的话 execute 按默认值重算，删得更少）。"""
    pool, _reg, _table, _wall, _mono = setup
    for index in range(3):
        _rollout(pool, f"w{index}", f"2026-11-19T00:00:0{index}Z")
    pool._cleanup_config = {"keep_per_group": 2, "max_age_days": 14, "archive_max_age_days": 14}
    seen: list[tuple[str, dict]] = []
    real_plan, real_execute = _core.world_cleanup_plan, _core.world_cleanup_execute

    def spy_plan(reg, now, open_worlds, **cfg):
        seen.append(("plan", cfg))
        return real_plan(reg, now, open_worlds, **cfg)

    def spy_execute(reg, plan, now, **cfg):
        seen.append(("execute", cfg))
        return real_execute(reg, plan, now, **cfg)
    monkeypatch.setattr(_core, "world_cleanup_plan", spy_plan)
    monkeypatch.setattr(_core, "world_cleanup_execute", spy_execute)
    assert pool.cleanup_round()["removed"] == ["w0"]
    assert {kind for kind, _cfg in seen} == {"plan", "execute"}
    assert all(cfg == pool._cleanup_config for _kind, cfg in seen)


def test_execute_gets_one_candidate_per_call_under_its_world_lock(setup, monkeypatch):
    """裁定 R103：每次 execute 只交一个候选，调用时持着该世界的世界锁、处于它的关闭窗口里。"""
    pool, _reg, _table, _wall, _mono = setup
    _rollout(pool, "a", STALE)
    _rollout(pool, "b", STALE)
    calls: list[dict] = []
    real_execute = _core.world_cleanup_execute

    def spy_execute(reg, plan, now, **cfg):
        names = [item["world"] for item in plan["remove"]]
        held = {}
        for name in names:
            lock = pool._world_lock(name)
            probe: dict = {}

            def _try(lock=lock, probe=probe):
                probe["free"] = lock.acquire(blocking=False)
                if probe["free"]:
                    lock.release()
            prober = threading.Thread(target=_try)
            prober.start()
            prober.join(5)
            held[name] = (not probe["free"], name in pool.closing_worlds())
        calls.append({"remove": names, "archives": len(plan["archives"]), "held": held})
        return real_execute(reg, plan, now, **cfg)
    monkeypatch.setattr(_core, "world_cleanup_execute", spy_execute)
    assert sorted(pool.cleanup_round()["removed"]) == ["a", "b"]
    with_worlds = [c for c in calls if c["remove"]]
    assert [len(c["remove"]) for c in with_worlds] == [1, 1]
    assert all(c["archives"] == 0 for c in with_worlds)
    for call in with_worlds:
        assert all(locked and closing for locked, closing in call["held"].values()), call


# ───────────────────────── 开着的世界不删 ─────────────────────────

def test_world_with_an_engine_is_skipped_and_logged_open(setup):
    pool, reg, _table, _wall, _mono = setup
    rec = _rollout(pool, "busy", STALE)
    with pool.lease("busy"):
        pass
    assert "busy" in pool.open_worlds()
    out = pool.cleanup_round()
    assert out["removed"] == [] and out["skipped"] == ["busy"]
    assert pool.record("busy")["dir_id"] == rec["dir_id"]
    assert os.path.isdir(_home(reg, rec["dir_id"]))
    assert _log(reg) == [("busy", "skipped", "open")]
    pool.close_world("busy")
    assert pool.cleanup_round()["removed"] == ["busy"]


def test_world_with_live_client_handles_is_not_removed(setup):
    """有活句柄（只读也算）的世界不删，记 open；即使它此刻没有引擎（看板把它关了，spec §10.3 允许）。"""
    pool, reg, table, _wall, mono = setup
    rec = _rollout(pool, "held", STALE)
    sid = table.connect(mono())
    handle = pool.admit_client_handle("held", sid, "alice", True, mono())
    pool.close_world("held")
    assert "held" not in pool.open_worlds()
    out = pool.cleanup_round()
    assert out["removed"] == [] and out["skipped"] == ["held"]
    assert os.path.isdir(_home(reg, rec["dir_id"]))
    assert _log(reg) == [("held", "skipped", "open")]
    # 句柄关掉之后，下一轮照删，会话表里这个世界的记录也清掉了（forget_world）。
    table.close_handle(handle)
    assert pool.cleanup_round()["removed"] == ["held"]
    assert not table.world_has_live_handles("held", mono())


def test_world_with_an_in_flight_call_is_not_removed(setup):
    """句柄已关、调用还在途（R59）：forget_world 抛 world_in_use，跳过并记 open。"""
    pool, reg, table, _wall, mono = setup
    rec = _rollout(pool, "inflight", STALE)
    sid = table.connect(mono())
    handle = pool.admit_client_handle("inflight", sid, "alice", True, mono())
    pool.close_world("inflight")
    table.call_enter(handle, mono())
    table.close_handle(handle)
    assert not table.world_has_live_handles("inflight", mono())
    out = pool.cleanup_round()
    assert out["removed"] == [] and out["skipped"] == ["inflight"]
    assert os.path.isdir(_home(reg, rec["dir_id"]))
    assert _log(reg) == [("inflight", "skipped", "open")]
    table.call_exit(handle, mono())
    assert pool.cleanup_round()["removed"] == ["inflight"]


def test_world_with_an_in_flight_lease_is_left_for_the_next_round(setup, monkeypatch):
    """检视路由持着一份不建引擎的租约在读库（spec §5.5、R25）：与 delete_world 一样等租约归零才删；等不到（上限很短，后台路径
    不久等）就这一轮不删、不记，下一轮再来。"""
    pool, reg, _table, _wall, _mono = setup
    rec = _rollout(pool, "reading", STALE)
    monkeypatch.setattr("starling.dashboard.world_manager._CLEANUP_DRAIN_S", 0.05)
    lease = pool.lease("reading", build=False)
    try:
        assert lease.engine is None
        out = pool.cleanup_round()
        assert out == {"removed": [], "skipped": ["reading"], "archives_removed": 0}
        assert os.path.isdir(_home(reg, rec["dir_id"]))
        assert _log(reg) == []
    finally:
        lease.release()
    assert pool.cleanup_round()["removed"] == ["reading"]


def test_world_busy_under_another_world_lock_holder_is_left_for_the_next_round(setup):
    """世界锁被别的操作（快照、恢复）占着：这轮不等它，这一个候选留到下一轮，不删也不记。"""
    pool, reg, _table, _wall, _mono = setup
    rec = _rollout(pool, "locked", STALE)
    held, release = threading.Event(), threading.Event()

    def _holder():
        with pool._world_lock("locked"):
            held.set()
            release.wait(30)
    holder = threading.Thread(target=_holder, daemon=True)
    holder.start()
    assert held.wait(10)
    try:
        out = pool.cleanup_round()
    finally:
        release.set()
        holder.join(10)
    assert out == {"removed": [], "skipped": ["locked"], "archives_removed": 0}
    assert os.path.isdir(_home(reg, rec["dir_id"]))
    assert _log(reg) == []
    assert pool.cleanup_round()["removed"] == ["locked"]


def test_cleanup_round_also_removes_aged_archives_of_non_reclaimable_worlds(setup):
    pool, reg, _table, _wall, _mono = setup
    pool.create_world("deploy", "")
    home = _home(reg, pool.record("deploy")["dir_id"])
    archive = os.path.join(home, "archive")
    os.makedirs(archive, exist_ok=True)
    old = os.path.join(archive, "world.db.pre-rollback-20261101T000000Z-abcd")
    fresh = os.path.join(archive, "world.db.pre-rollback-20261119T000000Z-abcd")
    for path in (old, fresh):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("old library")
    out = pool.cleanup_round()
    assert out == {"removed": [], "skipped": [], "archives_removed": 1}
    assert not os.path.exists(old) and os.path.exists(fresh)
    assert _log(reg) == [("deploy", "archive_removed", "over_age")]


def test_cleanup_round_without_a_registry_is_a_no_op(tmp_path):
    cfg = DashboardConfig(db_path=":memory:", token="", tick_interval_s=0, source_lane_enabled=False)
    pool = WorldPool(None, cfg)
    try:
        assert pool.cleanup_round() == {"removed": [], "skipped": [], "archives_removed": 0}
    finally:
        pool.close_all()


def test_invalid_cleanup_config_is_reported_by_cpp(setup):
    pool, _reg, _table, _wall, _mono = setup
    pool._cleanup_config = dict(pool._cleanup_config, keep_per_group=0)
    with pytest.raises(_core.WorldStoreError) as err:
        pool.cleanup_round()
    assert _core.world_store_error_code(err.value) == "invalid_settings"


# ───────────────────────── open 与清理的竞态（裁定 R103） ─────────────────────────

_RACE_SLEEP_MS = 400


def _race_open(pool, table, mono, opener: str, world: str):
    """在另一个线程里 open(world)：看板租约（lease）或客户端只读句柄（admit_client_handle）。返回 (线程, 结果)。

    清理持着世界锁、处在关闭窗口里时，open 回瞬态的 world_busy（与 delete_world 同一种窗口），调用方照协议重试；这里同样
    重试（记下见过几次 busy），直到得到确定的结果。"""
    result: dict = {"busy": 0}

    def _run():
        deadline = time.monotonic() + 15
        while True:
            try:
                if opener == "lease":
                    lease = pool.lease(world)
                    result["engine_open"] = lease.engine is not None
                    lease.release()
                else:
                    sid = table.connect(mono())
                    result["handle"] = pool.admit_client_handle(world, sid, "alice", True, mono())
                result["ok"] = True
                return
            except WorldSwitchError as exc:
                if exc.code == "world_busy" and time.monotonic() < deadline:
                    result["busy"] += 1
                    time.sleep(0.01)
                    continue
                result["code"] = exc.code
                return
            except BaseException as exc:  # noqa: BLE001 — 测试要看见抛了什么
                result["error"] = exc
                return
    thread = threading.Thread(target=_run, daemon=True)
    return thread, result


def _assert_race_outcome(pool, reg, table, mono, rec: dict, out: dict, result: dict) -> str:
    """只允许两种结果：跳过且记 open（世界与文件都在）；或 open 回 world_not_found 且文件已不在。"""
    name = rec["name"]
    home = _home(reg, rec["dir_id"])
    assert "error" not in result, result
    if result.get("ok"):
        assert out["removed"] == [] and name in out["skipped"]
        assert pool.record(name)["dir_id"] == rec["dir_id"]
        assert os.path.isdir(home) and os.path.exists(rec["db_path"])
        assert (name, "skipped", "open") in _log(reg)
        return "skipped"
    assert result.get("code") == "world_not_found", result
    assert result["busy"] >= 1, "the open must have raced into the cleanup's closing window"
    assert out["removed"] == [name]
    assert not os.path.exists(home)
    assert name not in pool.open_worlds()
    assert not table.world_has_live_handles(name, mono())
    return "removed"


@pytest.mark.parametrize("opener", ["lease", "handle"])
def test_cleanup_races_open(tmp_path, monkeypatch, opener):
    """清理选中 W（plan 已出、W 没开着）的同时，另一个线程 open(W)。两种顺序都用确定的窗口造出来：

    - 先 open：plan 之后、取 W 的世界锁之前，open 完成（世界锁内的确认看到引擎或活句柄）→ 跳过，记 open。
    - 先删：清理在 W 的世界锁内、关闭窗口里刚确认完没开着，open 进来 → 窗口里回瞬态 world_busy；清理随后仍持着锁在
      C++ 里删（_test_sleep_ms 撑开窗口），open 重试到清理放锁之后是 world_not_found，文件已不在。
    两种都不允许 W 的引擎开着、文件却被删了。"""
    results = []
    for order in ("open_first", "delete_first"):
        base = tmp_path / order
        base.mkdir()
        pool, reg, table, _wall, mono = _pool(base)
        try:
            rec = _rollout(pool, "W", STALE)
            thread, result = _race_open(pool, table, mono, opener, "W")
            real_plan, real_execute = _core.world_cleanup_plan, _core.world_cleanup_execute
            in_execute = threading.Event()

            if order == "open_first":
                def plan_then_open(reg_, now, open_worlds, **cfg):
                    plan = real_plan(reg_, now, open_worlds, **cfg)
                    assert [r["world"] for r in plan["remove"]] == ["W"]
                    thread.start()
                    thread.join(10)                      # open 在取世界锁之前已完成
                    assert result.get("ok"), result
                    return plan
                monkeypatch.setattr(_core, "world_cleanup_plan", plan_then_open)
                out = pool.cleanup_round()
            else:
                real_forget = pool._forget_for_cleanup

                def forget_then_open(world):
                    # 世界锁内的确认刚通过：此刻发起 open，等它确实被关闭窗口挡回一次（world_busy），再往下走到删除。
                    # 确认与删除之间若放开过世界锁或关闭窗口，open 会在这段空隙里打开 W，随后 W 的文件被删。
                    confirmed = real_forget(world)
                    thread.start()
                    deadline = time.monotonic() + 10
                    while result["busy"] < 1 and "code" not in result and "ok" not in result \
                            and time.monotonic() < deadline:
                        time.sleep(0.005)
                    return confirmed

                def slow_execute(reg_, plan, now, **cfg):
                    if plan["remove"]:
                        in_execute.set()
                        return real_execute(reg_, plan, now, _test_sleep_ms=_RACE_SLEEP_MS, **cfg)
                    return real_execute(reg_, plan, now, **cfg)
                monkeypatch.setattr(pool, "_forget_for_cleanup", forget_then_open)
                monkeypatch.setattr(_core, "world_cleanup_execute", slow_execute)
                out = pool.cleanup_round()
                thread.join(20)
                assert not thread.is_alive() and in_execute.is_set()
            monkeypatch.undo()
            results.append(_assert_race_outcome(pool, reg, table, mono, rec, out, result))
        finally:
            monkeypatch.undo()
            pool.close_all()
            gc.collect()
    assert results == ["skipped", "removed"]


# ───────────────────────── 调度线程 ─────────────────────────

def _cleanup_threads() -> list:
    return [t for t in threading.enumerate() if t.name == "starling-cleanup" and t.is_alive()]


def test_cleanup_thread_starts_runs_and_stops(setup, monkeypatch):
    pool, _reg, _table, _wall, _mono = setup
    rounds: list[float] = []
    real_round = pool.cleanup_round

    def counting(now=None, stop=None):
        rounds.append(time.monotonic())
        return real_round(now, stop)
    monkeypatch.setattr(pool, "cleanup_round", counting)
    before = set(_cleanup_threads())
    pool.start_background(stats_interval_s=3600.0, scheduler_first_delay_s=3600.0,
                          idle_close_interval_s=0, cleanup_interval_s=0.05)
    started = [t for t in _cleanup_threads() if t not in before]
    assert len(started) == 1 and started[0].daemon
    deadline = time.monotonic() + 5
    while len(rounds) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(rounds) >= 2
    pool.stop_background()
    assert not started[0].is_alive()


def test_stop_background_interrupts_a_round_between_candidates(setup, monkeypatch):
    """裁定 R105 F3：一轮删到一半时 stop_background，剩下的候选这一轮不再删，清理线程在超时之内退出。第一个候选的 execute
    卡在 C++ 里（替身等一个事件），stop 置位之后才放它删完；之后的候选不再交给 C++。"""
    pool, reg, _table, _wall, _mono = setup
    recs = {name: _rollout(pool, name, STALE) for name in ("a", "b", "c")}
    in_execute, proceed = threading.Event(), threading.Event()
    removing: list[str] = []
    real_execute = _core.world_cleanup_execute

    def slow_execute(reg_, plan, now, **cfg):
        if plan["remove"]:
            removing.append(plan["remove"][0]["world"])
            in_execute.set()
            assert proceed.wait(10)
        return real_execute(reg_, plan, now, **cfg)
    monkeypatch.setattr(_core, "world_cleanup_execute", slow_execute)
    pool.start_background(stats_interval_s=3600.0, scheduler_first_delay_s=3600.0,
                          idle_close_interval_s=0, cleanup_interval_s=0.05)
    thread, stop = pool._threads["starling-cleanup"]
    assert in_execute.wait(10)
    stopper = threading.Thread(target=pool.stop_background, kwargs={"timeout_s": 5.0}, daemon=True)
    started = time.monotonic()
    stopper.start()
    assert stop.wait(5)                                   # stop_background 已置位，正在 join 清理线程
    proceed.set()
    stopper.join(10)
    assert not stopper.is_alive() and not thread.is_alive()
    assert time.monotonic() - started < 5.0
    assert len(removing) == 1                             # 只有卡住的那一个被交给 C++
    first = removing[0]
    assert _gone(pool, first) and not os.path.exists(_home(reg, recs[first]["dir_id"]))
    for name in sorted(set(recs) - {first}):
        assert pool.record(name)["dir_id"] == recs[name]["dir_id"], name
        assert os.path.isdir(_home(reg, recs[name]["dir_id"])), name


def test_cleanup_round_returns_early_when_stop_is_already_set(setup):
    pool, reg, _table, _wall, _mono = setup
    _rollout(pool, "a", STALE)
    stop = threading.Event()
    stop.set()
    assert pool.cleanup_round(stop=stop) == {"removed": [], "skipped": [], "archives_removed": 0}
    assert pool.record("a")["name"] == "a"
    assert pool.cleanup_round()["removed"] == ["a"]


def test_cleanup_thread_first_round_waits_one_interval(setup, monkeypatch):
    pool, _reg, _table, _wall, _mono = setup
    rounds: list[int] = []
    monkeypatch.setattr(pool, "cleanup_round", lambda now=None, stop=None: rounds.append(1))
    pool.start_background(stats_interval_s=3600.0, scheduler_first_delay_s=3600.0,
                          idle_close_interval_s=0, cleanup_interval_s=3600.0)
    time.sleep(0.2)
    assert rounds == []
    assert len(_cleanup_threads()) >= 1
    pool.stop_background()


def test_cleanup_thread_survives_a_failing_round(setup, monkeypatch, caplog):
    pool, _reg, _table, _wall, _mono = setup
    calls = {"n": 0}

    def boom(now=None, stop=None):
        calls["n"] += 1
        raise RuntimeError("boom")
    monkeypatch.setattr(pool, "cleanup_round", boom)
    pool.start_background(stats_interval_s=3600.0, scheduler_first_delay_s=3600.0,
                          idle_close_interval_s=0, cleanup_interval_s=0.02)
    deadline = time.monotonic() + 5
    while calls["n"] < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls["n"] >= 3
    assert any(t.name == "starling-cleanup" for t in _cleanup_threads())
    pool.stop_background()
    assert "cleanup round failed" in caplog.text


def test_cleanup_interval_zero_disables_the_thread(setup):
    pool, _reg, _table, _wall, _mono = setup
    before = set(_cleanup_threads())
    pool.start_background(stats_interval_s=3600.0, scheduler_first_delay_s=3600.0,
                          idle_close_interval_s=0, cleanup_interval_s=0)
    assert [t for t in _cleanup_threads() if t not in before] == []
    pool.stop_background()


def test_cleanup_thread_needs_a_registry(tmp_path):
    cfg = DashboardConfig(db_path=":memory:", token="", tick_interval_s=0, source_lane_enabled=False)
    pool = WorldPool(None, cfg)
    try:
        before = set(_cleanup_threads())
        pool.start_background(stats_interval_s=3600.0, cleanup_interval_s=0.01)
        assert [t for t in _cleanup_threads() if t not in before] == []
    finally:
        pool.close_all()


def test_cleanup_interval_defaults_to_600_seconds():
    import inspect
    assert inspect.signature(WorldPool.start_background).parameters["cleanup_interval_s"].default == 600.0


# ───────────────────────── 配置项与接线 ─────────────────────────

def test_config_defaults_and_pool_reads_them(tmp_path):
    cfg = _cfg(tmp_path)
    assert (cfg.cleanup_keep_per_group, cfg.cleanup_max_age_days, cfg.cleanup_archive_max_age_days,
            cfg.cleanup_interval_s) == (200, 14, 14, 600.0)
    cfg = _cfg(tmp_path, cleanup_keep_per_group=3, cleanup_max_age_days=7, cleanup_archive_max_age_days=30)
    reg = _core.WorldRegistry.open(cfg.data_dir, cfg.db_path, cfg.tenant)
    pool = WorldPool(reg, cfg)
    try:
        assert pool._cleanup_config == {"keep_per_group": 3, "max_age_days": 7, "archive_max_age_days": 30}
    finally:
        pool.close_all()


def test_config_keys_round_trip_through_starling_json(tmp_path):
    import json
    data_dir = tmp_path / "D"
    data_dir.mkdir()
    (data_dir / "starling.json").write_text(json.dumps({
        "cleanup_keep_per_group": 50, "cleanup_max_age_days": 3, "cleanup_archive_max_age_days": 30,
        "cleanup_interval_s": 120}), encoding="utf-8")
    cfg = DashboardConfig.load_service(str(data_dir), "tok")
    assert (cfg.cleanup_keep_per_group, cfg.cleanup_max_age_days, cfg.cleanup_archive_max_age_days,
            cfg.cleanup_interval_s) == (50, 3, 30, 120)
    cfg = DashboardConfig.load(str(data_dir / "starling.json"))
    assert cfg.cleanup_keep_per_group == 50 and cfg.cleanup_interval_s == 120
    assert {"cleanup_keep_per_group", "cleanup_max_age_days", "cleanup_archive_max_age_days",
            "cleanup_interval_s"} <= set(cfg.to_dict())


def test_invalid_config_value_reaches_cpp_as_invalid_settings(tmp_path):
    """取值不合法（0、负数、非整数）不在 Python 里另判，交给 C++ 报 invalid_settings。"""
    for bad in (0, -1, "3", 2.5, True):
        cfg = _cfg(tmp_path, cleanup_max_age_days=bad)
        reg = _core.WorldRegistry.open(cfg.data_dir, cfg.db_path, cfg.tenant)
        pool = WorldPool(reg, cfg)
        try:
            with pytest.raises(_core.WorldStoreError) as err:
                pool.cleanup_round(now=NOW)
            assert _core.world_store_error_code(err.value) == "invalid_settings", bad
        finally:
            pool.close_all()


def test_serve_cleanup_interval_option(tmp_path, monkeypatch, capsys):
    from starling.service import serve
    args = serve._parser().parse_args(["--data-dir", "/x", "--port", "0"])
    assert args.cleanup_interval is None                  # 没传时取 D/starling.json（裁定 R105 F1）
    args = serve._parser().parse_args(["--data-dir", "/x", "--port", "0", "--cleanup-interval", "0"])
    assert args.cleanup_interval == 0.0
    monkeypatch.setenv(serve.TOKEN_ENV, "tok")
    with pytest.raises(SystemExit):
        serve.main(["--data-dir", str(tmp_path), "--port", "0", "--cleanup-interval", "-1"])
    assert "--cleanup-interval must be a finite number >= 0" in capsys.readouterr().err
    seen: dict = {}

    def fake_serve(cfg, *_args):
        seen["interval"] = cfg.cleanup_interval_s
        return 0
    monkeypatch.setattr(serve, "_serve", fake_serve)
    assert serve.main(["--data-dir", str(tmp_path), "--port", "0", "--cleanup-interval", "30"]) == 0
    assert seen["interval"] == 30.0


def _serve_main_capture(monkeypatch, data_dir, argv_extra=()):
    """跑 starling-serve 的 main，_serve 换成在 TestClient 里起 app（不绑端口）：返回 (生效的间隔, 起没起清理线程)。"""
    from fastapi.testclient import TestClient

    from starling.dashboard import create_app
    from starling.service import serve
    seen: dict = {}

    def fake_serve(cfg, _drain, idle_close_interval_s, engine_factory):
        before = set(_cleanup_threads())
        seen["interval"] = cfg.cleanup_interval_s
        with TestClient(create_app(cfg, engine_factory=engine_factory,
                                   idle_close_interval_s=idle_close_interval_s)):
            seen["thread"] = bool([t for t in _cleanup_threads() if t not in before])
        return 0
    monkeypatch.setenv(serve.TOKEN_ENV, "tok")
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(serve, "_serve", fake_serve)
    assert serve.main(["--data-dir", str(data_dir), "--port", "0", "--idle-close-interval", "0",
                       *argv_extra]) == 0
    return seen["interval"], seen["thread"]


def _write_service_config(data_dir, **keys) -> None:
    import json
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "starling.json").write_text(json.dumps(
        {"tick_interval_s": 0, "source_lane_enabled": False, **keys}), encoding="utf-8")


def test_serve_takes_cleanup_interval_from_starling_json(tmp_path, monkeypatch):
    """裁定 R105 F1：不传 --cleanup-interval 时用 D/starling.json 的 cleanup_interval_s；写 0 就不起清理线程。"""
    data_dir = tmp_path / "D"
    _write_service_config(data_dir, cleanup_interval_s=0)
    assert _serve_main_capture(monkeypatch, data_dir) == (0, False)


def test_serve_command_line_interval_wins_over_starling_json(tmp_path, monkeypatch):
    data_dir = tmp_path / "D"
    _write_service_config(data_dir, cleanup_interval_s=0)
    interval, thread = _serve_main_capture(monkeypatch, data_dir, ["--cleanup-interval", "3600"])
    assert (interval, thread) == (3600.0, True)


def test_serve_interval_defaults_to_600_without_flag_or_config_key(tmp_path, monkeypatch):
    data_dir = tmp_path / "D"
    _write_service_config(data_dir)
    interval, thread = _serve_main_capture(monkeypatch, data_dir)
    assert (interval, thread) == (600.0, True)


_BAD_INTERVALS = [pytest.param("600", id="string"), pytest.param(float("nan"), id="nan"),
                  pytest.param(-1, id="negative"), pytest.param(float("inf"), id="inf"),
                  pytest.param(True, id="bool")]


@pytest.mark.parametrize("bad", _BAD_INTERVALS)
def test_invalid_cleanup_interval_in_starling_json_fails_at_load(tmp_path, bad):
    """裁定 R105 F2：加载配置时就报错，消息里写出键名（starling-serve 的 load_service 与 8787 的 load 都一样），不等到
    start_background 里才抛 TypeError，也不静默不起线程。json 写得出 NaN / Infinity，Python 也读得回来。"""
    data_dir = tmp_path / "D"
    _write_service_config(data_dir, cleanup_interval_s=bad)
    with pytest.raises(RuntimeError, match="cleanup_interval_s must be a finite number >= 0"):
        DashboardConfig.load_service(str(data_dir), "tok")
    with pytest.raises(RuntimeError, match="cleanup_interval_s must be a finite number >= 0"):
        DashboardConfig.load(str(data_dir / "starling.json"))


@pytest.mark.parametrize("bad", _BAD_INTERVALS)
def test_create_app_refuses_an_invalid_cleanup_interval(tmp_path, bad):
    """直接构造的配置（不经 load）与显式参数同样在 create_app 里拒绝，不开池、不起线程。"""
    from starling.dashboard import create_app
    with pytest.raises(RuntimeError, match="cleanup_interval_s must be a finite number >= 0"):
        create_app(_cfg(tmp_path / "a", cleanup_interval_s=bad), idle_close_interval_s=0)
    with pytest.raises(RuntimeError, match="cleanup_interval_s must be a finite number >= 0"):
        create_app(_cfg(tmp_path / "b"), idle_close_interval_s=0, cleanup_interval_s=bad)


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "-1"])
def test_serve_rejects_an_invalid_cleanup_interval_flag(tmp_path, monkeypatch, capsys, bad):
    from starling.service import serve
    monkeypatch.setenv(serve.TOKEN_ENV, "tok")

    def must_not_start(*_args, **_kwargs):
        raise AssertionError("an invalid --cleanup-interval must be refused before the service starts")
    monkeypatch.setattr(serve, "run", must_not_start)          # 不拒绝时也不会真的起服务、挂在监听上
    with pytest.raises(SystemExit) as exit_info:
        serve.main(["--data-dir", str(tmp_path), "--port", "0", f"--cleanup-interval={bad}"])
    assert exit_info.value.code == 2
    assert "--cleanup-interval" in capsys.readouterr().err


def test_invalid_cleanup_interval_stops_the_8787_entry_with_the_key_in_the_log(tmp_path):
    """8787 的入口（scripts/run_dashboard.py）：配置不合法就起不来（退出码非 0），stderr 里写明键名。HOME 指到 tmp、去掉
    STARLING_* / OPENAI_*，库与端口都在 tmp 下（端口 0），读不到也碰不到本机的真实配置。"""
    import json
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    home = tmp_path / "home"
    data_dir = home / ".starling"
    data_dir.mkdir(parents=True)
    config = data_dir / "starling.json"
    config.write_text(json.dumps({"db_path": str(data_dir / "dashboard.db"), "port": 0, "token": "tok",
                                  "tick_interval_s": 0, "source_lane_enabled": False,
                                  "cleanup_interval_s": "600"}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "STARLING_"))}
    env["HOME"] = str(home)
    proc = subprocess.run([sys.executable, str(root / "scripts" / "run_dashboard.py"), "--config", str(config),
                           "--no-build"], env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0
    # 报错写明键名与规则（不只是回溯里碰巧出现这个变量名）。
    assert "cleanup_interval_s must be a finite number >= 0" in proc.stderr, proc.stderr[-2000:]


def test_start_pool_passes_cleanup_interval_on_both_paths(tmp_path, monkeypatch):
    """create_app 的两条开池路径（lifespan 内与 deferred_open 的工作线程）都把清理间隔交给 start_background。
    8787（run_dashboard → token_from_config）走第一条，spec §9 要求它同样每 10 分钟跑一轮。"""
    from starling.dashboard import app as app_mod
    seen: list[dict] = []
    real = WorldPool.start_background

    def spy(self, **kwargs):
        seen.append(kwargs)
        return real(self, **dict(kwargs, cleanup_interval_s=0))
    monkeypatch.setattr(WorldPool, "start_background", spy)
    pool, _reg, _table, _wall, _mono = _pool(tmp_path)
    try:
        app_mod._start_pool(pool, _Bridge(), None, idle_close_interval_s=0, cleanup_interval_s=42.0)
        assert seen[-1]["cleanup_interval_s"] == 42.0
        pool.stop_background()
        app_mod._start_pool(pool, _Bridge(), None)
        assert seen[-1]["cleanup_interval_s"] == 600.0
    finally:
        pool.close_all()


def test_create_app_and_serve_thread_the_interval(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from starling.dashboard import create_app
    seen: list[float] = []
    real = WorldPool.start_background

    def spy(self, **kwargs):
        seen.append(kwargs.get("cleanup_interval_s"))
        return real(self, **dict(kwargs, cleanup_interval_s=0))
    monkeypatch.setattr(WorldPool, "start_background", spy)
    cfg = _cfg(tmp_path, cleanup_interval_s=77.0)
    with TestClient(create_app(cfg, idle_close_interval_s=0)):
        pass
    assert seen[-1] == 77.0                                   # 缺省取 config.cleanup_interval_s
    with TestClient(create_app(_cfg(tmp_path / "b"), idle_close_interval_s=0, cleanup_interval_s=5.0)):
        pass
    assert seen[-1] == 5.0                                    # 显式参数优先（starling-serve --cleanup-interval）


class _Bridge:
    def bridge(self, _loop, _kind):
        return lambda *_a: None
