import pytest

from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine, _LLMNotConfigured

_STUB_XML = (
    "<statements><statement><holder>self</holder>"
    "<holder_perspective>FIRST_PERSON</holder_perspective>"
    "<subject>Bob</subject><predicate>responsible_for</predicate>"
    "<object>auth</object><modality>BELIEVES</modality>"
    "<polarity>POS</polarity><nesting_depth>0</nesting_depth></statement></statements>"
)


@pytest.fixture
def engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "eng.db"), token="t")
    eng = DashboardEngine(cfg)   # llm unset, embedder -> stub8
    return eng


def test_unconfigured_llm_recall_tick_ok_but_remember_raises(engine):
    assert isinstance(engine.recall("auth"), list)
    st = engine.tick("2026-06-01T10:00:00Z")
    assert set(st) == {"embedded", "fired", "broken", "auto_withdrawn"}
    with pytest.raises(_LLMNotConfigured):
        engine.remember("Bob owns auth")


def test_set_llm_enables_remember_offline_stub(engine):
    from starling import _core
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_XML, True, "")
    engine.llm = fake
    r = engine.remember("Bob owns auth")
    assert r["outcome"] in ("accepted", "idempotent")
    st = engine.tick("2026-06-01T10:00:00Z")
    assert "embedded" in st


def test_working_set_renders(engine):
    ws = engine.working_set("Alice")
    assert "render" in ws and "blocks" in ws and "truncated" in ws
