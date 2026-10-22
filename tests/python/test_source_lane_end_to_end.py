"""形态 S 端到端：retain（左脑写入）→ EmbeddingWorker（source 分支嵌入）→
RetrievalPlanner（感知过滤 + 召回 + 渲染）三段真实打通。

单测各自钉住了每一段；这里只验证它们**接得上**——字段名、clause_id 编号、
模型名、时间格式任一处两边不一致，单测全绿也召回不到东西。零网络
（StubEmbeddingAdapter 按文本 hash 生成确定性向量）。
"""
from __future__ import annotations

import json
import uuid

import pytest

from starling import _core

TENANT = "default"
OBSERVED = "2026-05-01T09:00:00Z"
AS_OF = "2026-12-31T00:00:00Z"


def _turn(speaker, text, index, audience, session="scene-1"):
    return {"speaker": speaker, "text": text, "session_id": session,
            "turn_index": index, "audience": audience,
            "provenance": "source_time", "turn_id": None,
            "observed_at": OBSERVED}


@pytest.fixture
def rig():
    adapter = _core.SqliteAdapter.open(":memory:")
    embedder = _core.StubEmbeddingAdapter(16)
    statement_index = _core.SqliteBlobVectorIndex()
    source_index = _core.SqliteSourceVectorIndex()
    worker = _core.EmbeddingWorker(adapter, embedder, statement_index, source_index)
    semantic = _core.SemanticRetriever(adapter, embedder, statement_index)
    planner = _core.RetrievalPlanner(adapter, semantic)
    # 返回所有对象：SourceLaneDeps 只存裸指针，调用方必须持有 index/embedder。
    return {"adapter": adapter, "embedder": embedder, "source_index": source_index,
            "worker": worker, "planner": planner}


def _query(rig, text, querier, tau=0.5):
    q = _core.PlannerQuery()
    q.tenant_id = TENANT
    q.querier = querier
    q.intent = _core.QueryIntent.FACT_LOOKUP
    q.text = text
    q.as_of_iso8601 = AS_OF
    q.k = 5
    q.trace_id = str(uuid.uuid4())
    q.query_id = str(uuid.uuid4())
    q.source_lane = _core.SourceLaneDeps(rig["source_index"], rig["embedder"], tau)
    return rig["planner"].run(q)


def _write_and_embed(rig, turns, holders):
    out = json.loads(_core.retain_source_turns(
        rig["adapter"], TENANT, holders, json.dumps(turns), OBSERVED))
    stats = rig["worker"].tick_one_batch("2026-06-01T00:00:00Z")
    return out, stats


def test_written_turn_is_embedded_then_recalled_verbatim(rig):
    secret = "the vault code is 4321"
    out, stats = _write_and_embed(
        rig, [_turn("alice", secret, 0, ["alice", "bob"])], ["alice", "bob"])
    assert out["documents"] == 1
    assert stats.source_embedded == 1 and stats.source_failed == 0

    # Stub 嵌入器按文本 hash 生成向量：查询与原话逐字相同 → 余弦 1.0。
    result = _query(rig, secret, querier="bob")
    assert not result.abstained
    assert len(result.source_entries) == 1
    entry = result.source_entries[0]
    assert entry.text == secret
    assert entry.speaker == "alice"
    assert entry.session_id == "scene-1"
    assert entry.observed_at == OBSERVED
    assert entry.score == pytest.approx(1.0, abs=1e-6)
    # 渲染：带日期与说话人，正文 JSON 转义。
    assert f'[SOURCE] [{OBSERVED}] alice: "{secret}"' in result.context_pack
    assert result.receipt.source_selected == 1


def test_absent_agent_cannot_recall_even_when_asking_about_itself(rig):
    """carol 不在场：即便 perspective==querier（自查），也召回不到。"""
    secret = "only alice and bob heard this"
    _write_and_embed(rig, [_turn("alice", secret, 0, ["alice", "bob"])],
                     ["alice", "bob", "carol"])
    result = _query(rig, secret, querier="carol")
    assert result.source_entries == []
    assert result.receipt.frontier_visible_engrams == 0
    assert "[SOURCE]" not in result.context_pack


def test_each_listener_set_is_isolated_within_one_scene(rig):
    """同一场景里两组听众 → 两个 engram，各自只有在场者可见。"""
    to_bob = "bob, the meeting moved to noon"
    to_carol = "carol, please bring the slides"
    _write_and_embed(rig, [_turn("alice", to_bob, 0, ["alice", "bob"]),
                           _turn("alice", to_carol, 1, ["alice", "carol"])],
                     ["alice", "bob", "carol"])
    bob_view = _query(rig, to_carol, querier="bob")
    assert all(e.text != to_carol for e in bob_view.source_entries)
    carol_view = _query(rig, to_carol, querier="carol")
    assert [e.text for e in carol_view.source_entries] == [to_carol]
    # 说话人两句都听得到。
    alice_view = _query(rig, to_bob, querier="alice")
    assert to_bob in [e.text for e in alice_view.source_entries]


def test_unrelated_query_abstains_below_tau(rig):
    _write_and_embed(rig, [_turn("alice", "the vault code is 4321", 0, ["alice"])],
                     ["alice"])
    result = _query(rig, "completely different topic about weather", querier="alice",
                    tau=0.95)
    assert result.abstained
    assert result.source_entries == []


def test_lane_closed_leaves_planner_untouched(rig):
    _write_and_embed(rig, [_turn("alice", "the vault code is 4321", 0, ["alice"])],
                     ["alice"])
    q = _core.PlannerQuery()
    q.tenant_id, q.querier = TENANT, "alice"
    q.intent = _core.QueryIntent.FACT_LOOKUP
    q.text = "the vault code is 4321"
    q.as_of_iso8601 = AS_OF
    q.k = 5
    q.trace_id, q.query_id = "t", "q"
    result = rig["planner"].run(q)          # 不设 source_lane
    assert result.source_entries == []
    assert "[SOURCE]" not in result.context_pack
    assert result.receipt.source_candidates == 0


def test_uncalibrated_tau_is_rejected_at_construction(rig):
    with pytest.raises(Exception, match="tau_source"):
        _core.SourceLaneDeps(rig["source_index"], rig["embedder"], 0.0)
