"""自动清理的绑定（C++ cleanup.hpp，第 6 期 Task 6.1）：只做类型归一与转发，规则全在 C++。"""
import os
import threading
import time

import pytest

from starling import _core

NOW = "2026-11-20T00:00:00Z"
STALE = "2026-11-01T00:00:00Z"
FRESH = "2026-11-19T00:00:00Z"


def _code(exc) -> str:
    return _core.world_store_error_code(exc)


def _open(tmp_path):
    return _core.WorldRegistry.open(str(tmp_path), str(tmp_path / "dashboard.db"), "default")


def _rollout(reg, name, group, created_at):
    """rise 的用法：从部署世界分叉一个可回收世界（分组 = run_id）。部署世界第一次用时建。"""
    try:
        reg.get("deploy")
    except _core.WorldStoreError:
        reg.create("deploy", "", {}, None, STALE)
    return _core.world_fork(reg, "deploy", name,
                            {"reclaimable": True, "retention_group": group, "now": created_at})["world"]


def test_plan_execute_and_log_roundtrip(tmp_path):
    reg = _open(tmp_path)
    old = _rollout(reg, "rollout-old", "run1", STALE)
    _rollout(reg, "rollout-open", "run1", STALE)
    _rollout(reg, "rollout-new", "run1", FRESH)
    home = os.path.join(str(tmp_path), "worlds", old["dir_id"])
    assert os.path.isdir(home)

    plan = _core.world_cleanup_plan(reg, NOW, ["rollout-open"])
    assert set(plan) == {"remove", "skip", "archives"}
    assert plan["remove"] == [{"world": "rollout-old", "group": "run1", "reason": "over_age",
                               "dir_id": old["dir_id"]}]
    assert plan["skip"] == [{"world": "rollout-open", "reason": "open", "group": "run1", "detail": ""}]
    assert plan["archives"] == []

    removed = _core.world_cleanup_execute(reg, plan, NOW)
    assert [item["world"] for item in removed] == ["rollout-old"]
    assert not os.path.exists(home)
    with pytest.raises(_core.WorldStoreError) as err:
        reg.get("rollout-old")
    assert _code(err.value) == "world_not_found"

    log = _core.world_cleanup_log(reg, 50)
    assert [(e["world"], e["action"], e["reason"]) for e in log] == [
        ("rollout-open", "skipped", "open"), ("rollout-old", "removed", "over_age")]
    assert log[0]["at"] == NOW and log[1]["group"] == "run1"
    assert set(log[0]) == {"id", "at", "world", "group", "action", "reason", "detail"}
    assert log[0]["id"] > log[1]["id"]


def test_config_keys_and_defaults(tmp_path):
    reg = _open(tmp_path)
    for index in range(3):
        _rollout(reg, f"w{index}", "g", f"2026-11-19T00:00:0{index}Z")
    assert _core.world_cleanup_plan(reg, NOW, [])["remove"] == []   # 默认 200 份、14 天
    plan = _core.world_cleanup_plan(reg, NOW, [], keep_per_group=2)
    assert [(i["world"], i["reason"]) for i in plan["remove"]] == [("w0", "over_count")]
    plan = _core.world_cleanup_plan(reg, NOW, [], keep_per_group=2, max_age_days=1,
                                    archive_max_age_days=30)
    assert [i["world"] for i in plan["remove"]] == ["w0"]


@pytest.mark.parametrize("call, code", [
    (lambda reg: _core.world_cleanup_plan(reg, "2026-11-20", []), "invalid_settings"),
    (lambda reg: _core.world_cleanup_plan(reg, NOW, [], keep_per_group=0), "invalid_settings"),
    (lambda reg: _core.world_cleanup_plan(reg, NOW, [], max_age_days=-1), "invalid_settings"),
    (lambda reg: _core.world_cleanup_execute(reg, {"remove": [], "skip": [], "archives": []}, "x"),
     "invalid_settings"),
    (lambda reg: _core.world_cleanup_log(reg, 0), "invalid_world_query"),
    (lambda reg: _core.world_cleanup_log(reg, 501), "invalid_world_query"),
])
def test_errors_come_from_cpp(tmp_path, call, code):
    reg = _open(tmp_path)
    with pytest.raises(_core.WorldStoreError) as err:
        call(reg)
    assert _code(err.value) == code


def test_plan_dict_shape_is_validated(tmp_path):
    reg = _open(tmp_path)
    with pytest.raises(_core.WorldStoreError) as err:
        _core.world_cleanup_execute(reg, {"remove": [], "bogus": []}, NOW)
    assert _code(err.value) == "invalid_settings"
    with pytest.raises(_core.WorldStoreError) as err:
        _core.world_cleanup_execute(reg, {"remove": [{"world": "x", "group": "", "reason": "over_age"}]}, NOW)
    assert _code(err.value) == "invalid_settings"   # 缺 dir_id
    # 缺的顶层键按空列表。
    assert _core.world_cleanup_execute(reg, {}, NOW) == []


def test_open_worlds_accepts_any_collection_of_names(tmp_path):
    reg = _open(tmp_path)
    _rollout(reg, "a", "g", STALE)
    _rollout(reg, "b", "g", STALE)
    for open_worlds in (["a"], {"a"}, ("a",), (name for name in ["a"])):
        plan = _core.world_cleanup_plan(reg, NOW, open_worlds)
        assert [s["world"] for s in plan["skip"]] == ["a"]
        assert [r["world"] for r in plan["remove"]] == ["b"]
    for bad in ("a", ["a", 1]):
        with pytest.raises(_core.WorldStoreError) as err:
            _core.world_cleanup_plan(reg, NOW, bad)
        assert _code(err.value) == "invalid_settings"


def test_bool_is_not_an_int_for_config(tmp_path):
    reg = _open(tmp_path)
    with pytest.raises(_core.WorldStoreError) as err:
        _core.world_cleanup_plan(reg, NOW, [], keep_per_group=True)
    assert _code(err.value) == "invalid_settings"


def _progress_while(blocking_call) -> int:
    """blocking_call 在另一个线程里跑期间，主线程每 2ms 推进一步；GIL 没放开时几乎不动。"""
    started, done = threading.Event(), threading.Event()

    def runner():
        started.set()
        try:
            blocking_call()
        finally:
            done.set()

    thread = threading.Thread(target=runner)
    thread.start()
    started.wait()
    progress = 0
    while not done.is_set():
        time.sleep(0.002)
        progress += 1
    thread.join()
    return progress


def test_cleanup_calls_release_the_gil(tmp_path):
    """plan 与 execute 在 C++ 里放开 GIL（列归档、删目录、写注册表）。测试钩子在 C++ 里睡 300ms，窗口确定。"""
    reg = _open(tmp_path)
    _rollout(reg, "old", "g", STALE)
    plan = _core.world_cleanup_plan(reg, NOW, [])
    progress = _progress_while(lambda: _core.world_cleanup_plan(reg, NOW, [], _test_sleep_ms=300))
    assert progress >= 20, f"plan_cleanup 期间主线程仅推进 {progress} 步——GIL 未释放"
    progress = _progress_while(lambda: _core.world_cleanup_execute(reg, plan, NOW, _test_sleep_ms=300))
    assert progress >= 20, f"execute_cleanup 期间主线程仅推进 {progress} 步——GIL 未释放"
    assert _core.world_cleanup_log(reg, 1)[0]["action"] == "removed"
