"""remember 三相绑定冒烟(MemoryCore 转发):remember_prepare → remember_extract
→ remember_commit 组合的 dict shape 须与单体 MemoryCore.remember 一致。
夹具抄 tests/python/test_converse_phases_binding.py(FakeLLMAdapter + DashboardEngine)。"""
from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _core_handles(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "rb.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB_JSON, True, "")
    eng.llm = fake
    return eng._core, fake


def test_phased_binding_matches_monolith_shape(tmp_path):
    core, _fake = _core_handles(tmp_path)
    now = "2026-07-12T10:00:00Z"

    mono = core.remember("Bob owns auth", holder=None, interlocutor=None, now=now)

    bundle = core.remember_prepare("Alice owns web", holder=None,
                                   interlocutor=None, now=now)
    extracted = core.remember_extract(bundle)
    phased = core.remember_commit(bundle, extracted)

    assert set(phased) == set(mono)            # dict 键一致
    assert mono["outcome"] == "accepted"
    assert phased["outcome"] == "accepted"     # 不同文本 → 都是首入 accepted
    assert phased["engram_ref"]


def test_no_store_re_remember_is_idempotent(tmp_path):
    # 同文本二次 remember(三相)→ idempotent,零新 engram。
    core, _fake = _core_handles(tmp_path)
    now = "2026-07-12T10:00:00Z"
    first = core.remember("Carol owns db", holder=None, interlocutor=None, now=now)
    assert first["outcome"] == "accepted"

    bundle = core.remember_prepare("Carol owns db", holder=None,
                                   interlocutor=None, now=now)
    assert bundle["prepared"].outcome == "idempotent"
    assert bundle["prepared"].should_extract is True
    extracted = core.remember_extract(bundle)
    second = core.remember_commit(bundle, extracted)
    assert second["outcome"] == "idempotent"


def test_engine_split_matches_core_inline(tmp_path):
    """#5(review 加固):三管线 host 编排 parity。engine.remember(真三相 split,
    带锁编排 + provider 局部解析 + bundle/llm 线程化)与 MemoryCore.remember(单体
    内联)在同一输入、独立库下产出相同 statement_ids 数量 + outcome——证 belief+
    episodic+gf 三条在 split 路径不丢不乱。非恒真:split 走 engine 分相调用,inline
    走 MemoryCore 顺序内联,二者编排代码不同。"""
    cfg_a = DashboardConfig(db_path=str(tmp_path / "split.db"), token="")
    eng_a = DashboardEngine(cfg_a)
    fa = _core.FakeLLMAdapter(); fa.set_default_response(_STUB_JSON, True, "")
    eng_a.llm = fa
    cfg_b = DashboardConfig(db_path=str(tmp_path / "inline.db"), token="")
    eng_b = DashboardEngine(cfg_b)
    fb = _core.FakeLLMAdapter(); fb.set_default_response(_STUB_JSON, True, "")
    eng_b.llm = fb

    text = "Bob owns auth and went to Paris"
    split = eng_a.remember(text, holder="cog-self")            # 三相 split(engine)
    inline = eng_b._core.remember(text, holder="cog-self")     # 单体内联(MemoryCore)
    assert split["outcome"] == inline["outcome"] == "accepted"
    assert len(split["statement_ids"]) == len(inline["statement_ids"])
    assert len(split["statement_ids"]) >= 1                     # belief(+gf)至少 1 条
