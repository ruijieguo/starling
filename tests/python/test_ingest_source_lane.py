"""形态 S Task 10：transcript 作为左脑 lane 的真实消费者。

``clean_turns_ts`` 与 ``clean_turns`` 并存（后者不动，既有摄入链不变）；新版
带上事件时间与句序，摄入时按 ``(session_id, audience={user,assistant})`` 走
v3 契约写入原文，使 transcript 成为左脑的可召回语料。
"""
from __future__ import annotations

import inspect
import json

from starling.dashboard.ingest_filter import clean_turns, clean_turns_ts, chunk_dialogue


def _user(text, ts="2026-06-01T10:00:00.123Z"):
    return json.dumps({"type": "user", "timestamp": ts,
                       "message": {"role": "user", "content": text}})


def _assistant(text, ts="2026-06-01T10:00:05.987Z"):
    return json.dumps({"type": "assistant", "timestamp": ts,
                       "message": {"role": "assistant",
                                   "content": [{"type": "text", "text": text}]}})


def test_clean_turns_ts_carries_time_and_index():
    lines = [_user("hello there"), _assistant("hi, how can I help?")]
    out = clean_turns_ts(lines)
    assert len(out) == 2
    role, text, event_time, turn_index = out[0]
    assert role == "user" and text == "hello there"
    assert turn_index == 0
    # 毫秒必须截断到秒：observed_at 只到秒，保留毫秒会让同一秒的两句无法稳定排序。
    assert event_time == "2026-06-01T10:00:00Z"
    assert out[1][2] == "2026-06-01T10:00:05Z"
    assert out[1][3] == 1


def test_clean_turns_ts_drops_events_without_timestamp():
    lines = [json.dumps({"type": "user",
                         "message": {"role": "user", "content": "no ts"}}),
             _user("with ts")]
    out = clean_turns_ts(lines)
    # 没有事件时间的句子不进来源 lane：它既不能渲染日期也不能按 as-of 截断。
    assert [row[1] for row in out] == ["with ts"]


def test_clean_turns_ts_rejects_unparseable_timestamp():
    lines = [_user("bad time", ts="not-a-timestamp"), _user("good time")]
    out = clean_turns_ts(lines)
    assert [row[1] for row in out] == ["good time"]


def test_clean_turns_is_unchanged():
    """既有摄入链不受影响：clean_turns 仍返回 2 元组。"""
    lines = [_user("hello"), _assistant("hi")]
    out = clean_turns(lines)
    assert out == [("user", "hello"), ("assistant", "hi")]
    # 签名不变（仍是 list[str] -> list[tuple[str, str]]）。
    assert len(inspect.signature(clean_turns).parameters) == 1


def test_chunk_dialogue_still_takes_two_tuples():
    out = chunk_dialogue([("user", "hello"), ("assistant", "hi")])
    assert out and isinstance(out[0], str)


# ── 端到端：摄入点接线 ───────────────────────────────────────────────────────

import sqlite3

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _engine(tmp_path, spool, *, lane_on: bool):
    cfg = DashboardConfig(db_path=str(tmp_path / "ingest.db"), token="")
    if lane_on:
        cfg.source_lane_enabled = True
        cfg.source_lane_tau_source = 0.3
    eng = DashboardEngine(cfg)
    eng._ingest_spool = spool
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    eng.llm = fake
    return eng


def _job(tmp_path, spool, sid="s1", cwd="/proj/foo"):
    tp = tmp_path / f"{sid}.jsonl"
    tp.write_text("\n".join([_user("Bob owns auth"), _assistant("noted")]))
    spool.mkdir(parents=True, exist_ok=True)
    (spool / f"{sid}.json").write_text(json.dumps(
        {"session_id": sid, "transcript_path": str(tp), "cwd": cwd,
         "tenant": "default"}))


def _count(db_path, sql):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def test_lane_off_writes_no_source_tables(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, lane_on=False)
    _job(tmp_path, spool)
    assert eng._ingest_drain_once() == "done"
    # 关闭时完全走原有路径：右脑照常落语句，左脑表一行不写。
    assert _count(eng._db_path, "SELECT COUNT(*) FROM statements") >= 1
    assert _count(eng._db_path, "SELECT COUNT(*) FROM source_unit_meta") == 0
    assert _count(eng._db_path, "SELECT COUNT(*) FROM source_unit_vectors") == 0


def test_lane_on_writes_v3_turns_with_both_parties_present(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, lane_on=True)
    _job(tmp_path, spool)
    assert eng._ingest_drain_once() == "done"
    db = eng._db_path
    assert _count(db, "SELECT COUNT(*) FROM source_unit_meta") == 2
    # 场景 = job 的会话 id；时间截到秒。
    assert _count(db, "SELECT COUNT(*) FROM source_unit_meta WHERE session_id='s1'") == 2
    assert _count(db, "SELECT COUNT(*) FROM source_unit_meta "
                      "WHERE observed_at='2026-06-01T10:00:00Z'") == 1
    # 说话人映射与 remember 的 holder 约定一致：user→self，assistant→claude-code:<project>。
    assert _count(db, "SELECT COUNT(*) FROM source_unit_meta WHERE speaker='self'") == 1
    assert _count(db, "SELECT COUNT(*) FROM source_unit_meta "
                      "WHERE speaker='claude-code:foo'") == 1
    # 双方都在场——两人都能召回这段对话。
    assert _count(db, "SELECT COUNT(DISTINCT cognizer_id) FROM cognizer_presence_log") == 2
    # 待嵌入行已入队。
    assert _count(db, "SELECT COUNT(*) FROM source_unit_vectors WHERE status='pending'") == 2


def test_lane_on_discards_job_when_cleared_after_claim(tmp_path):
    spool = tmp_path / "spool"
    eng = _engine(tmp_path, spool, lane_on=True)
    _job(tmp_path, spool)
    # 模拟 claim 之后发生 clear：代数前移。
    original = eng._retain_transcript_turns

    def bump_then_retain(lines, *, job, project, generation):
        eng._clear_generation += 1
        return original(lines, job=job, project=project, generation=generation)

    eng._retain_transcript_turns = bump_then_retain
    assert eng._ingest_drain_once() == "done"
    # 作废：不写来源表，job 进 discarded/。
    assert _count(eng._db_path, "SELECT COUNT(*) FROM source_unit_meta") == 0
    assert (spool / "discarded" / "s1.json").exists()


def test_config_rejects_enabled_without_calibrated_tau():
    cfg = DashboardConfig()
    cfg.source_lane_enabled = True
    import pytest
    with pytest.raises(RuntimeError, match="tau_source"):
        cfg.validate_source_lane()


def test_config_rejects_render_time_without_enabled():
    cfg = DashboardConfig()
    cfg.source_lane_render_time = True
    import pytest
    with pytest.raises(RuntimeError, match="requires source_lane_enabled"):
        cfg.validate_source_lane()


def test_config_defaults_are_all_off():
    cfg = DashboardConfig()
    assert cfg.source_lane_enabled is False
    assert cfg.source_lane_render_time is False
    assert cfg.source_lane_tau_source == 0.0
    cfg.validate_source_lane()   # 默认配置本身合法


def test_engine_refuses_to_start_with_uncalibrated_lane(tmp_path):
    """直接构造引擎（不经 create_app）同样受硬约束。"""
    import pytest
    cfg = DashboardConfig(db_path=str(tmp_path / "x.db"), token="")
    cfg.source_lane_enabled = True          # 开启但 tau_source 仍为 0
    with pytest.raises(RuntimeError, match="tau_source"):
        DashboardEngine(cfg)


def test_support_check_defaults_off_and_no_llm_call(monkeypatch):
    """前提核验默认关闭：不额外调用 LLM，作答提示与开启前逐字节一致。

    钉住两件容易回归的事：①开关默认 False（每轮不该凭空多一次 LLM 调用）；
    ②关闭时 apply_support_verdict 是恒等函数（提示不该被任何路径改写）。
    """
    from starling import _core

    cfg = DashboardConfig()
    assert cfg.support_check_enabled is False

    check_cfg = _core.SupportCheckConfig()
    assert check_cfg.enabled is False

    # 关闭时不发请求:FakeLLMAdapter 若被调用会返回一条会被解析成
    # "unsupported" 的响应;verdict.checked 仍是 False 就证明它没被碰过。
    fake = _core.FakeLLMAdapter()
    fake.set_default_response('{"verdict":"unsupported","reason":"x"}', True)
    verdict = _core.memory_check_support(fake, "q", "e", check_cfg)
    assert verdict.checked is False
    assert verdict.supported is False

    prompt = "HEAD\n\n<recalled_memory>\n[SOURCE] x\n</recalled_memory>\n\nUser: q\nAssistant:"
    assert _core.memory_apply_support_verdict(prompt, "q", verdict, check_cfg) == prompt


def test_support_check_enabled_rewrites_only_when_unsupported():
    """上一条的对照:同一个假适配器,开启后**确实**会判、会改写。

    没有这一条,上一条的「没改写」可能只是因为假适配器从没生效过。
    """
    from starling import _core

    check_cfg = _core.SupportCheckConfig()
    check_cfg.enabled = True
    check_cfg.unsupported_instruction = "NOT STATED MARKER"
    prompt = "HEAD\n\n<recalled_memory>\n[SOURCE] x\n</recalled_memory>\n\nUser: q\nAssistant:"

    unsupported = _core.FakeLLMAdapter()
    unsupported.set_default_response('{"verdict":"unsupported","reason":"x"}', True)
    v_un = _core.memory_check_support(unsupported, "q", "e", check_cfg)
    assert v_un.checked and v_un.ok and not v_un.supported
    rewritten = _core.memory_apply_support_verdict(prompt, "q", v_un, check_cfg)
    assert "NOT STATED MARKER" in rewritten
    assert rewritten.index("NOT STATED MARKER") < rewritten.index("User: q")

    supported = _core.FakeLLMAdapter()
    supported.set_default_response('{"verdict":"supported","reason":"y"}', True)
    v_ok = _core.memory_check_support(supported, "q", "e", check_cfg)
    assert v_ok.checked and v_ok.ok and v_ok.supported
    assert _core.memory_apply_support_verdict(prompt, "q", v_ok, check_cfg) == prompt
