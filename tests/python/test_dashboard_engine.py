import pytest

from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine, _LLMNotConfigured

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
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
    fake.set_default_response(_STUB_JSON, True, "")
    engine.llm = fake
    r = engine.remember("Bob owns auth")
    assert r["outcome"] in ("accepted", "idempotent")
    st = engine.tick("2026-06-01T10:00:00Z")
    assert "embedded" in st


def test_working_set_renders(engine):
    ws = engine.working_set("Alice")
    assert "render" in ws and "blocks" in ws and "truncated" in ws


def test_working_set_includes_affect_section(engine):
    """Parity regression: the engine working set must carry the affect section
    (it drifted away from Memory.render_working_set before the MemoryCore
    consolidation)."""
    import sqlite3
    from starling import _core
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_JSON, True, "")
    engine.llm = fake
    engine.remember("Bob owns auth")
    # Stamp affect + consolidate the extracted statement (engine connection
    # idle): vector recall only surfaces consolidated/archived rows, and fresh
    # extractions are volatile.
    conn = sqlite3.connect(engine._db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("UPDATE statements SET affect_json='{\"valence\":0.8,\"arousal\":0.6}',"
                 " consolidation_state='consolidated'")
    conn.commit()
    conn.close()
    engine.tick("2026-06-10T10:00:00Z")          # embed via stub embedder
    ws = engine.working_set("Alice", goal="auth")
    labels = [b["label"] for b in ws["blocks"]]
    assert "relevant_memories" in labels
    assert "affect" in labels, "engine working set lost the affect section"
