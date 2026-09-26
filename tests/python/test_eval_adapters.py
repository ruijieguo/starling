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


# --- SocialMemBench 真实 schema(下载 4 parquet 后 profile 得,2026-07 校验)---
# JSON 列在真实 parquet 里以**字符串**落地,fixture 也用字符串以走 _parse_json。
_SM_CONV = [
    {"network_id": "n1", "session_index": 1, "turn_id": "n1_s01_t001",
     "speaker_display_name": "Bob", "message": "I own X.", "message_index": 1,
     "timestamp": "2025-04-01T10:00:00"},
    {"network_id": "n1", "session_index": 3, "turn_id": "n1_s03_t000",
     "speaker_display_name": "Carol", "message": "I took over X.", "message_index": 0,
     "timestamp": "2025-05-01T10:00:00"},
]


def test_socialmembench_mc_normalizes_options_and_gold():
    qa = [{
        "qa_id": "q0", "network_id": "n1", "query_type": "Q4",
        "question": "who owns X?", "answer": "Carol took over X after Bob.",
        "answer_format": "multiple_choice",
        "options_json": '{"A": "Bob", "B": "Carol", "C": "Dan"}',
        "correct_option": "B",
        "evidence_anchors_json": (
            '[{"session_index": 1, "turn_id": "n1_s01_t001", '
            '"speaker_display_name": "Bob", "message_excerpt": "I own X.", '
            '"relevance": "high"}]'),
    }]
    out = ad.adapt_socialmembench(qa, _SM_CONV)
    assert len(out) == 1
    rec = out[0]
    # history 排序键 (session_index, message_index):Bob(1,1) 在 Carol(3,0) 之前
    assert [h["speaker"] for h in rec["history"]] == ["Bob", "Carol"]
    # options_json dict → 按字母排序成 list;correct_option 'B' → 下标 1
    assert rec["options"] == ["Bob", "Carol", "Dan"]
    assert rec["answer"] == 1
    assert rec["answer_format"] == "multiple_choice"
    # subset 是打分/归因轴:MC → socialmem_mc(band=0.05 确定性);
    # 基准原生认知分类 query_type 保留在独立字段(报告二次细分,不参与打分)。
    assert rec["subset"] == "socialmem_mc"
    assert rec["query_type"] == "Q4"
    # gold 检索级:holder=alice,subject=说话人,observed_at 按 turn_id 查真时戳
    g = rec["gold_statements"][0]
    assert g["holder"] == "alice"
    assert g["subject"] == "Bob"
    assert g["object"] == "I own X."
    assert g["observed_at"] == "2025-04-01T10:00:00"
    assert g["_gold_level"] == "retrieval"
    assert g["turn_id"] == "n1_s01_t001"
    assert g["session_index"] == 1
    assert rec["history"][0]["turn_id"] == "n1_s01_t001"
    assert rec["history"][0]["session_index"] == 1
    assert rec["history"][0]["message_index"] == 1
    assert rec["source"]["network_id"] == "n1"
    assert rec["source"]["reference_answer"] == qa[0]["answer"]
    rec["evaluation_protocol"] = {"status": "include", "sessions": [1, 3]}
    assert ad.adapt_passthrough([rec], benchmark="socialmem")[0] == rec


def test_socialmem_anchor_timestamp_is_network_scoped():
    qa = [{"qa_id": "q", "network_id": "n1", "query_type": "Q1",
           "question": "what?", "answer": "owned", "answer_format": "long_form",
           "options_json": "[]", "correct_option": "", "evidence_anchors_json": [
               {"turn_id": "n1_s01_t001", "speaker_display_name": "Bob",
                "message_excerpt": "I own X.", "session_index": 1}]}]
    conversations = [*_SM_CONV, {**_SM_CONV[0], "network_id": "other",
                                "timestamp": "2099-01-01T00:00:00"}]
    rec = ad.adapt_socialmembench(qa, conversations)[0]
    assert rec["gold_statements"][0]["observed_at"] == _SM_CONV[0]["timestamp"]


def test_socialmem_duplicate_source_ids_remain_distinct_across_networks():
    base = {"qa_id": "reused", "query_type": "Q1", "question": "what?", "answer": "owned",
            "answer_format": "long_form", "options_json": "[]", "correct_option": "",
            "evidence_anchors_json": "[]"}
    qa = [{**base, "network_id": n} for n in ("n1", "n2")]
    conversations = [*_SM_CONV, {**_SM_CONV[0], "network_id": "n2"}]
    rows = ad.adapt_socialmembench(qa, conversations)
    assert {r["item_id"] for r in rows} == {"n1/reused", "n2/reused"}
    assert all(r["source"]["qa_id"] == "reused" for r in rows)
    with pytest.raises(ad.AdapterError, match="duplicate"):
        ad.adapt_socialmembench([qa[0], qa[0]], conversations)


def test_socialmembench_mc_list_of_str_prefix_options():
    # options_json 编码二:带 'X) ' 前缀的 list-of-str(214 条 MC 中 12 条)
    qa = [{
        "qa_id": "q0b", "network_id": "n1", "query_type": "Q4",
        "question": "who owns X?", "answer": "Carol.",
        "answer_format": "multiple_choice",
        "options_json": '["A) Bob", "B) Carol", "C) Dan"]',
        "correct_option": "C",
        "evidence_anchors_json": "[]",
    }]
    rec = ad.adapt_socialmembench(qa, _SM_CONV)[0]
    assert rec["options"] == ["Bob", "Carol", "Dan"]
    assert rec["answer"] == 2  # 'C' → 下标 2


def test_socialmembench_mc_list_of_dict_options():
    # options_json 编码三:list-of-dict {"option": 字母, "name": 文本}(18 条)
    qa = [{
        "qa_id": "q0c", "network_id": "n1", "query_type": "Q4",
        "question": "who owns X?", "answer": "Bob.",
        "answer_format": "multiple_choice",
        "options_json": (
            '[{"option": "A", "name": "Bob"}, {"option": "B", "name": "Carol"}, '
            '{"option": "C", "name": "Dan"}]'),
        "correct_option": "A",
        "evidence_anchors_json": "[]",
    }]
    rec = ad.adapt_socialmembench(qa, _SM_CONV)[0]
    assert rec["options"] == ["Bob", "Carol", "Dan"]
    assert rec["answer"] == 0  # 'A' → 下标 0


def test_socialmembench_free_text_keeps_reference_answer():
    qa = [{
        "qa_id": "q1", "network_id": "n1", "query_type": "Q1",
        "question": "what does Bob's behavior suggest?",
        "answer": "Bob asserts ownership directly and does not deflect.",
        "answer_format": "long_form",
        "options_json": "[]", "correct_option": "",  # correct_option 截断不可用
        "evidence_anchors_json": (
            '[{"session_index": 3, "turn_id": "n1_s03_t000", '
            '"speaker_display_name": "Carol", "message_excerpt": "I took over X.", '
            '"relevance": "med"}]'),
    }]
    out = ad.adapt_socialmembench(qa, _SM_CONV)
    rec = out[0]
    assert rec["options"] == []
    assert rec["answer"] == "Bob asserts ownership directly and does not deflect."
    assert rec["answer_format"] == "long_form"
    assert rec["subset"] == "socialmem_free"    # 打分轴:judge 自由文本(band=α_judge)
    assert rec["query_type"] == "Q1"            # 原生认知分类保留(报告二次细分)
    # gold observed_at 从对应 turn_id 查得
    assert rec["gold_statements"][0]["observed_at"] == "2025-05-01T10:00:00"


def test_socialmembench_orphan_qa_fail_loud():
    qa = [{
        "qa_id": "q0", "network_id": "MISSING", "query_type": "Q4",
        "question": "?", "answer": "x", "answer_format": "multiple_choice",
        "options_json": '{"A": "a", "B": "b"}', "correct_option": "A",
        "evidence_anchors_json": "[]",
    }]
    with pytest.raises(ad.AdapterError):
        ad.adapt_socialmembench(qa, _SM_CONV)  # network 无对应会话


def test_socialmembench_unknown_answer_format_fail_loud():
    qa = [{
        "qa_id": "q0", "network_id": "n1", "query_type": "Q4",
        "question": "?", "answer": "x", "answer_format": "essay",
        "options_json": "[]", "correct_option": "",
        "evidence_anchors_json": "[]",
    }]
    with pytest.raises(ad.AdapterError):
        ad.adapt_socialmembench(qa, _SM_CONV)


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
