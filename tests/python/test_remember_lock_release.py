"""锁纪律:remember 的 belief+gf extraction 段不得持有 DashboardEngine._lock。
计时法(照 test_converse_lock_release.py):extraction adapter set_delay_ms 拉长
extract 段;并发 tick 必须在 extract 段拿到锁(<0.4s),拆锁前必阻塞 ≥0.7s。"""
import threading
import time

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "rl.db"), token="")
    eng = DashboardEngine(cfg)
    extraction = _core.FakeLLMAdapter()
    extraction.set_default_response(_STUB_JSON, True, "")
    extraction.set_delay_ms(700)     # #4:extract 段 = C++ 内睡 700ms(belief+gf 各一次,锁外)
    eng.llm = extraction
    return eng


def test_tick_interleaves_during_extract(tmp_path):
    """#4:照 test_converse_lock_release 的计时法(非 instrumentation——那会假通过:
    若全程持锁,被起线程会在 remember 返回后拿锁并在断言前 set event)。
    belief extraction 睡 700ms(锁外);并发 tick 必须在 extract 段 <0.4s 拿到锁;
    拆锁前 remember 全程持锁 → tick 阻塞 ≥0.7s。"""
    eng = _engine(tmp_path)
    turn = threading.Thread(
        target=lambda: eng.remember("hello bob", holder="cog-self"))
    turn.start()
    time.sleep(0.15)                       # prepare 毫秒级 → 已进 belief extract(锁外)
    start = time.monotonic()
    eng.tick("2026-07-12T00:00:00Z")       # 拆锁后:extract 段中锁可得(tick 不用抽取 adapter)
    elapsed = time.monotonic() - start
    turn.join(timeout=10)
    assert elapsed < 0.4, f"tick 等锁 {elapsed:.2f}s —— extract 段仍持锁,未拆"


def test_resolve_extraction_local_reference(tmp_path):
    import pytest
    from starling.dashboard.engine import _LLMNotConfigured
    eng = _engine(tmp_path)
    assert eng._resolve_extraction(None) is eng._core.llm     # None → role-bound
    with pytest.raises(_LLMNotConfigured):
        eng._resolve_extraction("no-such-provider")           # 未配 provider → 抛


def test_remember_route_returns_503_when_draining(tmp_path):
    """#2:remember 路由的 WriteGateRejected→503 wiring。写门关闭(begin_drain,
    C++ 无 Python 侧 set_write_admit 绑定——全仓既有 WriteGateRejected 测试范式
    统一走 eng._rt.begin_drain())后 POST /api/remember 必须回 503 而非冒泡成 500。
    prepare 段的 require_write_admission 门前抛(门关在 remember 开始前),同一
    except 分支也覆盖 commit 段捕到的「锁外 extract 期间转 DRAINING」情形。"""
    from fastapi.testclient import TestClient
    from starling.dashboard import create_app

    cfg = DashboardConfig(db_path=str(tmp_path / "rl_drain.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_JSON, True, "")
    eng.llm = fake
    client = TestClient(create_app(cfg, engine=eng))

    eng.begin_drain()
    assert eng._rt.health() == _core.RuntimeHealth.DRAINING
    r = client.post("/api/remember", json={"text": "Bob owns auth"})
    assert r.status_code == 503 and r.json()["detail"] == "draining"
