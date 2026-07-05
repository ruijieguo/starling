"""三相绑定冒烟(绑定层直呼版 —— Task 3 的 MemoryCore 转发落地前的过渡):
memory_converse_prepare → memory_generate_stream → memory_converse_commit 组合
的 dict shape 须与单体 memory_converse 完全一致。Task 3 落地 MemoryCore.
converse_prepare/generate_stream/converse_commit 转发后,本文件改为经
`eng._core` 转发的版本(见 task-2-brief.md Step 1 附注)。

夹具模式抄 tests/python/test_dashboard_commands.py / test_dashboard_converse.py
(FakeLLMAdapter + DashboardEngine);字段名(rt.adapter/semantic/tenant/agent/
adapter_name/source_prefix/_extraction.belief_prompt)抄 python/starling/
_memory_core.py 现有 converse() 的转发代码,以其为权威。
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


def _kwargs(core, message):
    """与 _memory_core.py MemoryCore.converse() 的 kwargs 组装同构(同字段名)。"""
    return dict(
        tenant_id=core.tenant, holder_id=core.agent, interlocutor="",
        adapter_name=core.adapter_name, source_prefix=core.source_prefix,
        created_at_iso8601="2026-07-05T10:00:00Z", message=message, recall_k=6,
    )


def test_phased_binding_matches_monolith_shape(tmp_path):
    core, fake = _core_handles(tmp_path)
    kwargs = _kwargs(core, "Bob owns auth")

    mono = _core.memory_converse(
        core.rt.adapter, fake, fake, core.semantic, core._extraction.belief_prompt,
        **kwargs)

    prepared = _core.memory_converse_prepare(core.rt.adapter, core.semantic, **kwargs)
    assert prepared.prompt and "recalled_memory" in prepared.prompt

    gen = _core.memory_generate_stream(fake, prepared.prompt, None)
    assert gen.ok

    phased = _core.memory_converse_commit(
        core.rt.adapter, fake, core._extraction.belief_prompt, **kwargs,
        prepared=prepared, gen_resp=gen)

    assert set(phased) == set(mono)          # dict 键完全一致
    assert phased["ok"] and phased["reply"] == gen.raw_xml
    assert phased["remember_ok"] in (True, False)


def test_generate_stream_relays_tokens(tmp_path):
    core, fake = _core_handles(tmp_path)
    kwargs = _kwargs(core, "hi")
    prepared = _core.memory_converse_prepare(core.rt.adapter, core.semantic, **kwargs)

    seen: list[str] = []
    gen = _core.memory_generate_stream(fake, prepared.prompt, seen.append)
    assert gen.ok and "".join(seen) == gen.raw_xml
