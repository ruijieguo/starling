"""三相绑定冒烟(MemoryCore 转发版 —— Task 3 落地后的正式版本):
MemoryCore.converse_prepare → generate_stream → converse_commit 组合的 dict
shape 须与单体 MemoryCore.converse 完全一致。经 `eng._core` 转发,不再直呼
`_core.memory_converse_prepare/...`(那是 Task 2 的绑定层过渡态,已被
_memory_core.py 的薄转发取代)。

夹具模式抄 tests/python/test_dashboard_commands.py / test_dashboard_converse.py
(FakeLLMAdapter + DashboardEngine)。
"""
from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _core_handles(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "b.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_JSON, True, "")
    eng.llm = fake                 # extraction adapter; chat falls back to it
    return eng._core, fake         # MemoryCore + 抽取/聊天两用 fake


def test_phased_binding_matches_monolith_shape(tmp_path):
    core, fake = _core_handles(tmp_path)
    now = "2026-07-05T10:00:00Z"
    message = "Bob owns auth"

    mono = core.converse(message, holder=None, interlocutor=None, k=6, now=now)

    prepared = core.converse_prepare(message, holder=None, interlocutor=None,
                                     k=6, now=now)
    assert prepared.prompt and "recalled_memory" in prepared.prompt

    gen = core.generate_stream(fake, prepared.prompt, None)
    assert gen.ok

    phased = core.converse_commit(message, prepared, gen, holder=None,
                                  interlocutor=None, k=6, now=now)

    assert set(phased) == set(mono)          # dict 键完全一致
    assert phased["ok"] and phased["reply"] == gen.raw_xml
    assert phased["remember_ok"] in (True, False)


def test_generate_stream_relays_tokens(tmp_path):
    core, fake = _core_handles(tmp_path)
    prepared = core.converse_prepare("hi", holder=None, interlocutor=None, k=6,
                                     now="2026-07-05T10:00:00Z")

    seen: list[str] = []
    gen = core.generate_stream(fake, prepared.prompt, seen.append)
    assert gen.ok and "".join(seen) == gen.raw_xml
