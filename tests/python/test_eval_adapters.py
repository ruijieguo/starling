"""PR-4: 进攻层基准适配器(scripts/eval_adapters.py)的离线归一测试。

用匹配各基准文档 schema 的合成 fixture(无需下载真实数据、无网络):
  - passthrough 轻校验 + fail-loud 缺字段
  - SocialMemBench:conversations 按 network_id 聚成 history 附到每道 qa
  - MemSyco:valid_memory→gold_statements,is_unanswerable→is_abstain
真实数据下载后须按实际列名再校验(见 eval_adapters docstring)。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_AD = Path(__file__).resolve().parents[2] / "scripts" / "eval_adapters.py"
_spec = importlib.util.spec_from_file_location("eval_adapters", _AD)
ad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ad)


def test_passthrough_normalizes_and_validates():
    rows = [{"item_id": "x0", "subset": "s", "question": "q?",
             "options": ["a", "b"], "answer": 1}]
    out = ad.adapt_passthrough(rows, benchmark="longmemeval")
    assert out[0]["item_id"] == "x0"
    assert out[0]["answer"] == 1


def test_passthrough_fail_loud_on_missing_field():
    with pytest.raises(ad.AdapterError):
        ad.adapt_passthrough([{"item_id": "x", "question": "q?"}],
                             benchmark="longmemeval")  # 缺 options/answer


def test_answer_index_out_of_range_rejected():
    with pytest.raises(ad.AdapterError):
        ad.adapt_passthrough([{"item_id": "x", "question": "q?",
                               "options": ["a", "b"], "answer": 5}],
                             benchmark="longmemeval")


def test_socialmembench_joins_conversations_by_network():
    qa = [{"qa_id": "q0", "network_id": "n1", "question": "who owns X?",
           "choices": ["Bob", "Carol"], "answer_idx": 1, "category": "attribution"}]
    conv = [
        {"network_id": "n1", "turn_idx": 1, "speaker": "carol", "text": "I took over X.",
         "timestamp": "2026-05-01T10:00:00Z"},
        {"network_id": "n1", "turn_idx": 0, "speaker": "bob", "text": "I own X.",
         "timestamp": "2026-04-01T10:00:00Z"},
    ]
    out = ad.adapt_socialmembench(qa, conv)
    assert len(out) == 1
    hist = out[0]["history"]
    # 按 turn_idx 排序:bob(0) 在 carol(1) 之前
    assert [h["speaker"] for h in hist] == ["bob", "carol"]
    assert out[0]["subset"] == "attribution"
    assert out[0]["answer"] == 1


def test_socialmembench_orphan_qa_fail_loud():
    qa = [{"qa_id": "q0", "network_id": "MISSING", "question": "?",
           "choices": ["a", "b"], "answer_idx": 0}]
    with pytest.raises(ad.AdapterError):
        ad.adapt_socialmembench(qa, [])  # network 无对应会话


def test_memsyco_maps_gold_and_abstain():
    rows = [{
        "task_id": "t0", "task_type": "memory-evidence-conflict",
        "dialogue": [{"speaker": "user", "text": "X is red.", "ts": "2026-01-01T00:00:00Z"}],
        "question": "color of X?", "options": ["red", "blue"], "answer_idx": 0,
        "valid_memory": [{"holder": "user", "subject": "X", "predicate": "has_color",
                          "object": "red", "observed_at": "2026-01-01T00:00:00Z"}],
    }, {
        "task_id": "t1", "task_type": "objective-fact", "question": "unknowable?",
        "options": ["a", "b"], "is_unanswerable": True,
    }]
    out = ad.adapt_memsyco(rows)
    assert out[0]["gold_statements"][0]["object"] == "red"
    assert out[1].get("is_abstain") is True


def test_registry_covers_passthrough_and_memsyco():
    assert set(ad.ADAPTERS) >= {"longmemeval", "locomo", "beam", "memsyco"}
