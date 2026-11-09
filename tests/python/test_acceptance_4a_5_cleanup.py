"""第 6 期验收（spec §16 第 4a、5 条；需求 §7 第 4a、5 条）。时间一律注入，不读墙钟。

4a：超过份数或天数的可回收世界被删；部署世界、种子、带 held 快照的世界、开着的世界不被删。
5：关掉后台任务的世界开着静置，推进注入时钟、让调度线程跑若干轮清理与调度，摘要不变。
"""
import gc
import os
from pathlib import Path

from starling import _core
from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine
from starling.dashboard.world_manager import WorldPool

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _stub_factory(ctx, providers):
    """池的引擎工厂：照常建引擎，再换上离线的抽取适配器（不发网络请求）。"""
    engine = DashboardEngine(ctx, providers)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    engine.llm = fake
    return engine

NOW = "2026-11-20T00:00:00Z"
STALE = "2026-11-01T00:00:00Z"      # 19 天前
FRESH = "2026-11-19T00:00:00Z"      # 1 天前


class _Wall:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now


class _Mono:
    def __init__(self) -> None:
        self.now = 1_000_000

    def __call__(self) -> int:
        return self.now


def _pool(tmp_path, wall, **cfg_over):
    base = dict(db_path=str(tmp_path / "dashboard.db"), token="", tick_interval_s=0,
                source_lane_enabled=False, ingest_spool_path=str(tmp_path / "spool"))
    base.update(cfg_over)
    cfg = DashboardConfig(**base)
    reg = _core.WorldRegistry.open(cfg.data_dir, cfg.db_path, cfg.tenant)
    mono = _Mono()
    pool = WorldPool(reg, cfg, clock=wall, monotonic_ms=mono, engine_factory=_stub_factory)
    table = _core.SessionTable()
    pool.attach_sessions(table)
    pool.sync_default_settings()
    pool.lease(pool.default_world()).release()
    return pool, reg, table, mono


def _at(pool, wall, stamp: str, fn, *args, **kwargs):
    """在注入时钟 = stamp 的那一刻调 fn（created_at 等由池的墙钟定）。"""
    saved = wall.now
    wall.now = stamp
    try:
        return fn(*args, **kwargs)
    finally:
        wall.now = saved


def _home(reg, rec: dict) -> str:
    return os.path.join(str(reg.data_dir), "worlds", rec["dir_id"])


def _exists(pool, name: str) -> bool:
    try:
        pool.record(name)
        return True
    except Exception:  # noqa: BLE001 — world_not_found
        return False


def test_4a_cleanup_respects_count_age_and_protections(tmp_path):
    wall = _Wall(NOW)
    pool, reg, table, mono = _pool(tmp_path, wall, cleanup_keep_per_group=2)
    try:
        # 部署世界：不可回收，19 天前建的，不论多老都不删。
        deploy = _at(pool, wall, STALE, pool.create_world, "deploy", "")
        # 种子：标成可回收、放进 run1 组、超龄（裁定 R105 F5）。不是种子的话它按天数、按份数都该删；种子规则让它不删，
        # 也不占 run1 的份数名额（c0–c3 的结果与没有它时相同）。
        seed = _at(pool, wall, STALE, pool.fork_world, "deploy", "seed-1", seed=True, reclaimable=True,
                   retention_group="run1")["world"]
        assert (seed["seed"], seed["reclaimable"], seed["retention_group"]) == (True, True, "run1")

        def rollout(name: str, stamp: str, group: str = "run1") -> dict:
            return _at(pool, wall, stamp, pool.fork_world, "deploy", name, reclaimable=True,
                       retention_group=group)["world"]

        # 份数：run1 组 4 个都在 14 天内，只留最新 2 个 → 最旧的两个超份数。
        count = {f"c{i}": rollout(f"c{i}", f"2026-11-19T00:00:0{i}Z") for i in range(4)}
        # 天数：另一组里超过 14 天的那个删，1 天前的留。
        aged = rollout("aged", STALE, group="run2")
        young = rollout("young", FRESH, group="run2")
        # 带 held 快照的超龄世界：跳过，记 held_snapshot。
        held = rollout("held", STALE, group="run3")
        pool.take_snapshot("held", "rise", kind="held")
        # 开着的超龄世界：一个有引擎（看板在看），一个只有客户端句柄（引擎已关）。
        open_engine = rollout("open-engine", STALE, group="run4")
        with pool.lease("open-engine"):
            pass
        open_handle = rollout("open-handle", STALE, group="run5")
        sid = table.connect(mono())
        handle = pool.admit_client_handle("open-handle", sid, "rise", True, mono())
        pool.close_world("open-handle")

        out = pool.cleanup_round()

        assert sorted(out["removed"]) == ["aged", "c0", "c1"]
        for name, rec in (("c0", count["c0"]), ("c1", count["c1"]), ("aged", aged)):
            assert not _exists(pool, name) and not os.path.exists(_home(reg, rec)), name
        kept = {"deploy": deploy, "seed-1": seed, "c2": count["c2"], "c3": count["c3"], "young": young,
                "held": held, "open-engine": open_engine, "open-handle": open_handle}
        for name, rec in kept.items():
            assert pool.record(name)["dir_id"] == rec["dir_id"], name
            assert os.path.exists(rec["db_path"]), name
        assert _exists(pool, "default")
        assert "open-engine" in pool.open_worlds()

        log = {(e["world"], e["action"], e["reason"]) for e in _core.world_cleanup_log(reg, 50)}
        assert log == {("c0", "removed", "over_count"), ("c1", "removed", "over_count"),
                       ("aged", "removed", "over_age"), ("held", "skipped", "held_snapshot"),
                       ("open-engine", "skipped", "open"), ("open-handle", "skipped", "open")}

        # 推进时钟一个月：受保护的照旧不删；放开保护之后照删。部署世界、种子、默认世界始终不删。
        wall.now = "2026-12-20T00:00:00Z"
        out = pool.cleanup_round()
        assert sorted(out["removed"]) == ["c2", "c3", "young"]
        table.close_handle(handle)
        pool.close_world("open-engine")
        assert sorted(pool.cleanup_round()["removed"]) == ["open-engine", "open-handle"]
        assert _exists(pool, "held")                                  # held 快照还在：仍跳过
        for name in ("deploy", "seed-1", "default"):
            assert _exists(pool, name), name
    finally:
        pool.close_all()
        gc.collect()


def _counting(pool, monkeypatch, name: str) -> list[int]:
    """把池的一轮调度函数换成计数的包装（后台线程调 self.<name>，实例属性生效）。"""
    calls: list[int] = []
    real = getattr(pool, name)

    def wrapped(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)
    monkeypatch.setattr(pool, name, wrapped)
    return calls


# 让调度线程至少跑这么久：盖过摄入线程的首轮轮询（engine.start_ingest_worker 缺省 2 秒）。后台被打开时（变异），
# 探针 job 在这段时间里会被摄入，摘要随之改变。
_SETTLE_S = 3.0


def test_5_background_off_world_digest_stable(tmp_path, monkeypatch):
    """世界开着、设置为后台关闭（裁定 R105 F4）：先断言实际生效的 tick、摄入都是关的，再让调度线程（清理、按时间的快照、
    统计刷新，间隔都 > 0）在推进的注入时钟下跑若干轮，摘要不变。世界的摄入分区里放一份待摄入的 job 作探针：后台若开着，
    摄入线程会把它吃进库里。"""
    import json
    import time
    wall = _Wall(STALE)
    pool, reg, _table, _mono = _pool(tmp_path, wall)
    try:
        pool.create_world("quiet", "", overrides={
            "background": {"tick_interval_s": 0, "ingest": False,
                           "auto_snapshot": {"on_session": False, "interval_hours": 0}}})
        with pool.lease("quiet") as engine:
            engine.remember("Bob owns auth")
            engine = None
        ctx = pool.context("quiet")
        spool = Path(ctx.ingest_spool_dir)
        spool.mkdir(parents=True, exist_ok=True)
        transcript = tmp_path / "probe.jsonl"
        transcript.write_text(json.dumps({"type": "user", "message": {"role": "user",
                                                                      "content": "Carol owns billing"}}),
                              encoding="utf-8")
        (spool / "probe.json").write_text(json.dumps({"session_id": "probe", "transcript_path": str(transcript),
                                                      "cwd": "/proj/probe", "tenant": ctx.tenant}),
                                          encoding="utf-8")

        lease = pool.lease("quiet")                               # 世界开着，整段都不关
        try:
            engine = lease.engine
            assert engine is not None and "quiet" in pool.open_worlds()
            effective = pool._effective_settings(pool.record("quiet"))["background"]
            assert (effective["tick_interval_s"], effective["ingest"]) == (0, False)
            assert (engine._settings["background"]["tick_interval_s"],
                    engine._settings["background"]["ingest"]) == (0, False)
            before = pool.world_digest("quiet")
            assert before
            rec = pool.record("quiet")
            stat_before = os.stat(rec["db_path"])

            rounds = {name: _counting(pool, monkeypatch, name)
                      for name in ("cleanup_round", "auto_snapshot_round", "refresh_stats")}
            pool.start_background(stats_interval_s=0.02, scheduler_poll_s=0.02, scheduler_first_delay_s=0.02,
                                  idle_close_interval_s=0, cleanup_interval_s=0.02)
            try:
                assert engine._tick_thread is None and engine._ingest_thread is None
                started = time.monotonic()
                day = 0
                while day < 40 or time.monotonic() - started < _SETTLE_S:     # 注入时钟推进 40 天以上
                    day += 3
                    seen = {name: len(calls) for name, calls in rounds.items()}
                    wall.now = f"2026-{11 + (day // 30):02d}-{(day % 30) + 1:02d}T00:00:00Z" if day < 60 \
                        else "2027-01-15T00:00:00Z"
                    deadline = time.monotonic() + 10
                    while any(len(calls) <= seen[name] for name, calls in rounds.items()) \
                            and time.monotonic() < deadline:
                        time.sleep(0.005)
                    assert all(len(calls) > seen[name] for name, calls in rounds.items()), wall.now
                    assert pool.world_digest("quiet") == before, wall.now
            finally:
                pool.stop_background()
            assert all(len(calls) >= 10 for calls in rounds.values()), {k: len(v) for k, v in rounds.items()}
            assert engine.ingest_status()["pending"] == 1             # 探针 job 没被摄入
            assert pool.world_digest("quiet") == before
            engine = None
        finally:
            lease.release()

        assert pool.snapshots("quiet") == []                       # 调度没给它拍快照
        stat_after = os.stat(rec["db_path"])
        assert (stat_after.st_size, stat_after.st_mtime_ns) == (stat_before.st_size, stat_before.st_mtime_ns)
        assert _exists(pool, "quiet")
    finally:
        pool.close_all()
        gc.collect()
