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
    cfg.source_lane_enabled = lane_on      # 默认开启；关闭分支显式关
    if lane_on:
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
    cfg.source_lane_tau_source = 0.0         # 默认已标定为 0.56，这里显式清零
    import pytest
    with pytest.raises(RuntimeError, match="tau_source"):
        cfg.validate_source_lane()


def test_config_rejects_render_time_without_enabled():
    cfg = DashboardConfig()
    cfg.source_lane_enabled = False          # 默认开启，这里显式关
    cfg.source_lane_render_time = True
    import pytest
    with pytest.raises(RuntimeError, match="requires source_lane_enabled"):
        cfg.validate_source_lane()


def test_config_defaults_enable_calibrated_lane():
    """默认开启（用户 2026-10-23 裁定）：阈值、模型与 BEAM 验收时一致。

    钉住这些值，是因为它们一起构成「标定」——单改其中一个（例如换嵌入模型而
    不重标阈值）就让阈值失去依据。"""
    cfg = DashboardConfig()
    assert cfg.source_lane_enabled is True
    assert cfg.source_lane_render_time is False
    assert cfg.source_lane_tau_source == 0.56
    assert (cfg.source_lane_model, cfg.source_lane_dim) == ("text-embedding-v4", 1024)
    assert (cfg.source_lane_k_source, cfg.source_lane_chunk_byte_budget) == (30, 32000)
    cfg.validate_source_lane()   # 默认配置本身合法


def test_config_round_trips_source_lane_fields(tmp_path):
    p = tmp_path / "cfg.json"
    cfg = DashboardConfig(db_path=str(tmp_path / "x.db"), token="t")
    cfg.source_lane_enabled = False
    cfg.source_lane_k_source = 12
    cfg.save(str(p))
    back = DashboardConfig.load(str(p))
    assert back.source_lane_enabled is False
    assert back.source_lane_k_source == 12


def test_lane_inactive_when_embedder_differs_from_calibration(tmp_path):
    """stub embedder（无嵌入配置）≠ 标定模型 → lane 不生效：读路径不检索原文、
    worker 不嵌入原文。默认开启因此不改变没配嵌入的部署与既有测试。"""
    cfg = DashboardConfig(db_path=str(tmp_path / "x.db"), token="")
    eng = DashboardEngine(cfg)
    st = eng.source_lane_status()
    assert st["configured"] is True and st["active"] is False
    assert "stub/8" in st["inactive_reason"]
    assert eng._core.source_lane is None


def test_lane_active_when_embedder_matches_calibration(tmp_path):
    """embedder 与标定一致 → lane 生效：converse/plan_query 都带上 SourceLaneDeps，
    worker 带 source 分支（原文会被嵌入）。用 stub 的 model/dim 作「标定」，
    只验接线，不依赖网络。"""
    from starling._memory_core import MemoryCore  # noqa: F401  确认符号存在
    cfg = DashboardConfig(db_path=str(tmp_path / "x.db"), token="")
    cfg.source_lane_model, cfg.source_lane_dim = "stub", 8
    eng = DashboardEngine(cfg)
    st = eng.source_lane_status()
    assert st == {"configured": True, "active": True, "inactive_reason": ""}
    lane = eng._core.source_lane
    assert (lane.model, lane.dim, lane.tau_source) == ("stub", 8, 0.56)
    assert (lane.k_source, lane.chunk_byte_budget) == (30, 32000)

    # 空库：planner 收到了 lane 但没有可见原文——降级原因是「没东西」而非「没接线」。
    res = eng._core.plan_query("who owns auth?", intent="FACT_LOOKUP")
    assert res.receipt.source_degraded_reason == "no_visible_engrams"

    # 写→嵌入：原文进库后，worker 的 source 分支把它嵌入。
    spool = tmp_path / "spool"
    eng._ingest_spool = spool
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    eng.llm = fake
    _job(tmp_path, spool)
    assert eng._ingest_drain_once() == "done"
    eng._core.tick("2099-01-01T00:00:00Z")
    assert _count(eng._db_path,
                  "SELECT COUNT(*) FROM source_unit_vectors WHERE status='embedded'") == 2

    # 读：原文已嵌入后 planner 真的检索到了候选（关闭态恒为 0）。
    res = eng._core.plan_query("who owns auth?", intent="FACT_LOOKUP", now="2099-01-01T00:00:00Z")
    assert res.receipt.source_degraded_reason == ""
    assert res.receipt.source_candidates >= 1

    # intent 门控（spec §2）：社会推理类 intent 不走左脑，即便原文就在库里。
    res = eng._core.plan_query("what does Bob believe?", intent="BELIEF_OF_OTHER",
                               target="Bob", now="2099-01-01T00:00:00Z")
    assert res.receipt.source_candidates == 0
    assert not res.source_entries


def test_lane_off_converse_prompt_has_no_source_lines(tmp_path):
    """显式关闭时读路径与改动前一致：converse 提示里没有任何 [SOURCE] 行。"""
    cfg = DashboardConfig(db_path=str(tmp_path / "x.db"), token="")
    cfg.source_lane_enabled = False
    cfg.source_lane_model, cfg.source_lane_dim = "stub", 8
    eng = DashboardEngine(cfg)
    assert eng._core.source_lane is None
    assert eng.source_lane_status()["inactive_reason"] == "disabled"


def test_engine_refuses_to_start_with_uncalibrated_lane(tmp_path):
    """直接构造引擎（不经 create_app）同样受硬约束。"""
    import pytest
    cfg = DashboardConfig(db_path=str(tmp_path / "x.db"), token="")
    cfg.source_lane_enabled = True
    cfg.source_lane_tau_source = 0.0        # 开启但阈值未标定
    with pytest.raises(RuntimeError, match="tau_source"):
        DashboardEngine(cfg)
