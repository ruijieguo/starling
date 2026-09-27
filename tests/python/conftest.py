import gc

import pytest


def pytest_addoption(parser):
    parser.addoption("--run-historical", action="store_true", default=False,
                     help="执行依赖固定历史评测产物的用例；各历史文件须在独立进程运行")


def pytest_configure(config):
    config.addinivalue_line("markers", "historical_eval(reason): 依赖固定历史数据或原生构建的回放")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-historical"):
        return
    for item in items:
        marker = item.get_closest_marker("historical_eval")
        if marker is not None:
            reason = marker.kwargs.get("reason", "固定历史评测产物")
            item.add_marker(pytest.mark.skip(reason=f"历史回放需 --run-historical：{reason}"))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown():
    """fixture 释放后回收不可达连接环，避免长套件耗尽本机 HTTP 描述符。"""
    try:
        return (yield)
    finally:
        gc.collect()


@pytest.fixture(autouse=True)
def isolate_dashboard_ingest_spool(tmp_path, monkeypatch):
    """Dashboard tests must never inspect or mutate the user's live spool."""
    monkeypatch.setenv("STARLING_DASH_INGEST_SPOOL", str(tmp_path / "ingest-spool"))


@pytest.fixture
def core():
    from starling import _core
    return _core
