"""spec §18 的时限与间隔做成服务配置项（裁定 R115）：空闲关闭时限、会话租约、空闲检查间隔、统计刷新间隔。

加载与校验；接线用真实的 SessionTable 与 WorldPool（不 mock 会话表）；starling-serve 的取值顺序（命令行 > D/starling.json > 缺省）。
会起服务的路径一律给 serve._serve 打桩（TestClient 起 app，不绑端口）。
"""
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from starling import _core
from starling.dashboard import create_app
from starling.dashboard.config import DashboardConfig
from starling.dashboard.world_manager import WorldPool

API = "/api/v1/client"
KEYS = ("idle_close_after_s", "session_lease_s", "idle_close_interval_s", "stats_refresh_s")
VALID = {"idle_close_after_s": 90, "session_lease_s": 6.5, "idle_close_interval_s": 0, "stats_refresh_s": 12.5}
BAD = [pytest.param("5", id="string"), pytest.param(float("nan"), id="nan"), pytest.param(-1, id="negative"),
       pytest.param(float("inf"), id="inf"), pytest.param(True, id="bool"), pytest.param(1e12, id="over-max")]


def _cfg(tmp_path, **over):
    base = dict(db_path=str(tmp_path / "dashboard.db"), token="", tick_interval_s=0.0,
                source_lane_enabled=False, ingest_spool_path=str(tmp_path / "spool"))
    base.update(over)
    return DashboardConfig(**base)


def _write(path, **keys):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"tick_interval_s": 0, "source_lane_enabled": False, **keys}), encoding="utf-8")


class _Clock:
    def __init__(self) -> None:
        self.now = int(time.monotonic() * 1000)

    def __call__(self) -> int:
        return self.now


def _threads(name):
    return [t for t in threading.enumerate() if t.name == name and t.is_alive()]


# ───────────────────────── 加载与校验 ─────────────────────────

def test_defaults_are_the_old_hard_coded_values():
    cfg = DashboardConfig()
    assert (cfg.idle_close_after_s, cfg.session_lease_s, cfg.idle_close_interval_s, cfg.stats_refresh_s) \
        == (600.0, 30.0, 30.0, 30.0)
    assert set(KEYS) <= set(cfg.to_dict())


def test_both_load_paths_read_the_four_keys(tmp_path):
    _write(tmp_path / "D" / "starling.json", **VALID)
    service = DashboardConfig.load_service(str(tmp_path / "D"), "tok")
    _write(tmp_path / "L" / "starling.json", token="tok", **VALID)
    local = DashboardConfig.load(str(tmp_path / "L" / "starling.json"))
    for cfg in (service, local):
        assert {k: getattr(cfg, k) for k in KEYS} == VALID


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("bad", BAD)
def test_invalid_value_fails_at_load_with_the_key(tmp_path, key, bad):
    _write(tmp_path / "D" / "starling.json", **{key: bad})
    with pytest.raises(RuntimeError, match=key):
        DashboardConfig.load_service(str(tmp_path / "D"), "tok")
    with pytest.raises(RuntimeError, match=key):
        DashboardConfig.load(str(tmp_path / "D" / "starling.json"))


@pytest.mark.parametrize("key", ["session_lease_s", "stats_refresh_s"])
def test_zero_is_refused_for_lease_and_stats(tmp_path, key):
    _write(tmp_path / "D" / "starling.json", **{key: 0})
    with pytest.raises(RuntimeError, match=key):
        DashboardConfig.load_service(str(tmp_path / "D"), "tok")
    with pytest.raises(RuntimeError, match=key):
        DashboardConfig.load(str(tmp_path / "D" / "starling.json"))


@pytest.mark.parametrize("key", ["idle_close_after_s", "idle_close_interval_s"])
def test_zero_is_accepted_for_idle_close_keys(tmp_path, key):
    _write(tmp_path / "D" / "starling.json", **{key: 0})
    assert getattr(DashboardConfig.load_service(str(tmp_path / "D"), "tok"), key) == 0


def test_lease_below_one_millisecond_is_refused_in_python(tmp_path):
    _write(tmp_path / "D" / "starling.json", session_lease_s=0.0004)
    with pytest.raises(RuntimeError, match="session_lease_s"):
        DashboardConfig.load_service(str(tmp_path / "D"), "tok")
    _write(tmp_path / "D" / "starling.json", session_lease_s=0.001)
    assert DashboardConfig.load_service(str(tmp_path / "D"), "tok").session_lease_s == 0.001


@pytest.mark.parametrize("key", KEYS)
def test_create_app_refuses_an_invalid_directly_built_config(tmp_path, key):
    with pytest.raises(RuntimeError, match=key):
        create_app(_cfg(tmp_path, **{key: -1}), idle_close_interval_s=0)


# ───────────────────────── 接线 ─────────────────────────

def test_session_lease_reaches_the_connect_reply(tmp_path):
    app = create_app(_cfg(tmp_path, session_lease_s=6), idle_close_interval_s=0)
    with TestClient(app) as client:
        out = client.post(f"{API}/connect", json={"protocol": 1}).json()
    assert (out["lease_ms"], out["heartbeat_ms"]) == (6000, 2000)


def test_default_lease_and_heartbeat_unchanged(tmp_path):
    with TestClient(create_app(_cfg(tmp_path), idle_close_interval_s=0)) as client:
        out = client.post(f"{API}/connect", json={"protocol": 1}).json()
    assert (out["lease_ms"], out["heartbeat_ms"]) == (30000, 10000)


def _idle_round_closes(tmp_path, idle_close_after_s) -> list[str]:
    app = create_app(_cfg(tmp_path, idle_close_after_s=idle_close_after_s), idle_close_interval_s=0)
    with TestClient(app):
        pool = app.state.pool
        clock = _Clock()
        pool._monotonic_ms = clock
        pool.create_world("w1", "")
        with pool.lease("w1"):
            pass
        clock.now += 1_500
        return pool.idle_close_round()


def test_small_idle_close_after_closes_an_idle_world(tmp_path):
    assert _idle_round_closes(tmp_path, 1) == ["w1"]


def test_large_idle_close_after_keeps_it_open(tmp_path):
    assert _idle_round_closes(tmp_path, 3600) == []


def test_idle_close_interval_zero_starts_no_thread(tmp_path):
    before = set(_threads("starling-idle-close"))
    with TestClient(create_app(_cfg(tmp_path, idle_close_interval_s=0))):
        assert not [t for t in _threads("starling-idle-close") if t not in before]


def test_idle_close_interval_from_config_starts_the_thread(tmp_path):
    before = set(_threads("starling-idle-close"))
    with TestClient(create_app(_cfg(tmp_path, idle_close_interval_s=3600))):
        assert len([t for t in _threads("starling-idle-close") if t not in before]) == 1


def test_explicit_argument_wins_over_config_idle_interval(tmp_path):
    before = set(_threads("starling-idle-close"))
    with TestClient(create_app(_cfg(tmp_path, idle_close_interval_s=3600), idle_close_interval_s=0)):
        assert not [t for t in _threads("starling-idle-close") if t not in before]


def _record_start_background(monkeypatch) -> list[dict]:
    seen: list[dict] = []
    real = WorldPool.start_background

    def recording(self, **kwargs):
        seen.append(kwargs)
        return real(self, **kwargs)
    monkeypatch.setattr(WorldPool, "start_background", recording)
    return seen


def test_stats_refresh_reaches_start_background_on_both_open_paths(tmp_path, monkeypatch):
    seen = _record_start_background(monkeypatch)
    with TestClient(create_app(_cfg(tmp_path / "a", stats_refresh_s=77.0, idle_close_interval_s=0))):
        pass
    assert seen[-1]["stats_interval_s"] == 77.0
    app = create_app(_cfg(tmp_path / "b", stats_refresh_s=88.0, idle_close_interval_s=0), deferred_open=True)
    with TestClient(app):
        deadline = time.monotonic() + 30
        while not app.state.ready and time.monotonic() < deadline:
            time.sleep(0.02)
        assert app.state.ready
    assert seen[-1]["stats_interval_s"] == 88.0


def test_config_idle_interval_reaches_start_background_on_the_deferred_path(tmp_path, monkeypatch):
    seen = _record_start_background(monkeypatch)
    app = create_app(_cfg(tmp_path, idle_close_interval_s=0), deferred_open=True)
    with TestClient(app):
        deadline = time.monotonic() + 30
        while not app.state.ready and time.monotonic() < deadline:
            time.sleep(0.02)
        assert app.state.ready
    assert seen[-1]["idle_close_interval_s"] == 0


# ───────────────────────── starling-serve ─────────────────────────

def _serve_capture(monkeypatch, data_dir, argv_extra=()):
    """serve.main，_serve 换成在 TestClient 里起 app（不绑端口）：返回 (传给 _serve 的空闲检查间隔, 起没起空闲关闭线程)。"""
    from starling.service import serve
    seen: dict = {}

    def fake_serve(cfg, _drain, idle_close_interval_s, engine_factory):
        before = set(_threads("starling-idle-close"))
        seen["interval"] = idle_close_interval_s
        with TestClient(create_app(cfg, engine_factory=engine_factory, idle_close_interval_s=idle_close_interval_s)):
            seen["thread"] = bool([t for t in _threads("starling-idle-close") if t not in before])
        return 0
    monkeypatch.setenv(serve.TOKEN_ENV, "tok")
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(serve, "_serve", fake_serve)
    assert serve.main(["--data-dir", str(data_dir), "--port", "0", "--cleanup-interval", "0", *argv_extra]) == 0
    return seen["interval"], seen["thread"]


def test_serve_idle_interval_flag_defaults_to_none():
    from starling.service import serve
    assert serve._parser().parse_args(["--data-dir", "/x", "--port", "0"]).idle_close_interval is None


def test_serve_takes_idle_interval_from_starling_json(tmp_path, monkeypatch):
    _write(tmp_path / "D" / "starling.json", idle_close_interval_s=0)
    assert _serve_capture(monkeypatch, tmp_path / "D") == (0, False)


def test_serve_command_line_idle_interval_wins(tmp_path, monkeypatch):
    _write(tmp_path / "D" / "starling.json", idle_close_interval_s=0)
    assert _serve_capture(monkeypatch, tmp_path / "D", ["--idle-close-interval", "3600"]) == (3600.0, True)


def test_serve_idle_interval_defaults_to_30(tmp_path, monkeypatch):
    _write(tmp_path / "D" / "starling.json")
    assert _serve_capture(monkeypatch, tmp_path / "D") == (30.0, True)


@pytest.mark.parametrize("bad", ["nan", "inf", "-1"])
def test_serve_rejects_an_invalid_idle_interval_flag(tmp_path, monkeypatch, capsys, bad):
    from starling.service import serve
    monkeypatch.setenv(serve.TOKEN_ENV, "tok")

    def must_not_start(*_args, **_kwargs):
        raise AssertionError("an invalid --idle-close-interval must be refused before the service starts")
    monkeypatch.setattr(serve, "run", must_not_start)
    with pytest.raises(SystemExit) as exit_info:
        serve.main(["--data-dir", str(tmp_path), "--port", "0", f"--idle-close-interval={bad}"])
    assert exit_info.value.code == 2
    assert "--idle-close-interval" in capsys.readouterr().err
