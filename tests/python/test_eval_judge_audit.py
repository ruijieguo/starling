"""PR-2: judge 对抗审计(scripts/eval_judge_audit.py)的纯逻辑测试。

只测 fixture-mode 骨架(离线、无网络、确定性):
  - 对抗答案生成 + mock judge 评判 + α_judge 聚合的确定性/可复现
  - α_judge 超阈值 → unusable 告警(Penfield: LoCoMo 62.81% 那种情形)
real-mode(真干扰器 + 真 judge LLM)是 gated 真跑,不在此测。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_AUDIT = Path(__file__).resolve().parents[2] / "scripts" / "eval_judge_audit.py"
_spec = importlib.util.spec_from_file_location("eval_judge_audit", _AUDIT)
audit_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_mod)


CORPUS = [
    {"item_id": "a0", "subset": "alpha", "question": "Who owns auth?",
     "options": ["Bob", "Carol", "Dana"], "answer": 1},
    {"item_id": "a1", "subset": "alpha", "question": "Where is the office?",
     "options": ["Berlin", "Munich"], "answer": 0},
    {"item_id": "b0", "subset": "beta", "question": "Who is on-call?",
     "options": ["Erin", "Frank", "Grace", "Heidi"], "answer": 2},
]


def test_distractors_are_deterministic_and_k_count():
    d1 = audit_mod._fixture_distractors(CORPUS[0], 3)
    d2 = audit_mod._fixture_distractors(CORPUS[0], 3)
    assert d1 == d2                       # 可复现
    assert len(d1) == 3                   # 恰好 k 个
    # 正确选项("Carol", idx 1)不应作为干扰答案出现在挑出的错误选项里
    assert "Carol" not in d1[:2]


def test_audit_is_deterministic():
    r1 = audit_mod.audit(CORPUS, k=3, fixture_mode=True)
    r2 = audit_mod.audit(CORPUS, k=3, fixture_mode=True)
    assert r1 == r2
    assert r1["total"] == len(CORPUS) * 3


def test_alpha_judge_is_accept_ratio():
    r = audit_mod.audit(CORPUS, k=3, fixture_mode=True)
    assert r["alpha_judge"] == r["accepted"] / r["total"]
    assert 0.0 <= r["alpha_judge"] <= 1.0


def test_unusable_flag_tracks_threshold():
    r = audit_mod.audit(CORPUS, k=3, fixture_mode=True)
    assert r["unusable"] == (r["alpha_judge"] > audit_mod.JUDGE_UNUSABLE_THRESHOLD)


def test_real_mode_is_gated_not_silently_run():
    """real-mode 必须 fail-loud(NotImplementedError),绝不静默跑空/网络。"""
    try:
        audit_mod.audit(CORPUS, k=3, fixture_mode=False)
    except NotImplementedError:
        return
    raise AssertionError("real-mode 应 raise NotImplementedError,不得静默执行")


# ---- T5b real-mode 接线点:纯函数 + 工厂注入(离线,无网络)----------------

_FREE_REC = {"item_id": "f0", "subset": "socialmem_free", "answer_format": "long_form",
             "question": "谁现在负责 auth 服务?", "answer": "Carol 负责 auth 服务。"}
_MC_REC = {"item_id": "m0", "subset": "socialmem_mc", "answer_format": "multiple_choice",
           "question": "Who owns auth?", "options": ["Bob", "Carol", "Dana"], "answer": 1}


def test_reference_answer_mc_vs_free():
    """参考答案:MC 取 options[answer],自由文本取 answer 原文。"""
    assert audit_mod._reference_answer(_MC_REC) == "Carol"
    assert audit_mod._reference_answer(_FREE_REC) == "Carol 负责 auth 服务。"


def test_reference_answer_mc_out_of_range_is_empty():
    """MC answer 越界不炸,回空串(诚实缺省,不误当 0)。"""
    bad = {"answer_format": "multiple_choice", "options": ["x"], "answer": 5}
    assert audit_mod._reference_answer(bad) == ""


def test_distractor_prompt_carries_question_and_correct_answer():
    """干扰器 prompt 必须带上问题 + 正确答案 + k(才能造"话题相邻但错")。"""
    p = audit_mod._distractor_prompt(_FREE_REC, 3)
    assert _FREE_REC["question"] in p
    assert "Carol 负责 auth 服务。" in p
    assert "exactly 3" in p
    assert "FACTUALLY WRONG" in p


def test_parse_distractors_strips_prefixes_dedups_caps_k():
    """解析:剥项目符号/序号、去重保序、至多 k 个。"""
    text = "- Bob owns it\n1) Dana owns it\n* Bob owns it\nErin owns it\n"
    out = audit_mod._parse_distractors(text, 3)
    assert out == ["Bob owns it", "Dana owns it", "Erin owns it"]  # 去重 + 截到 k


def test_parse_distractors_no_synthetic_padding_when_short():
    """产出不足 k 时**不**补齐合成串(补齐会低估 α_judge=不安全方向)。"""
    out = audit_mod._parse_distractors("only one wrong answer\n", 3)
    assert out == ["only one wrong answer"]  # 只有 1 个,绝不凑到 3


def test_parse_judge_verdict_yes_no_and_ambiguous():
    """judge 解析:首个 yes/no 词;缺失或歧义→False(保守,不误接受)。"""
    assert audit_mod._parse_judge_verdict("YES") is True
    assert audit_mod._parse_judge_verdict("no, it's wrong") is False
    assert audit_mod._parse_judge_verdict("maybe, hard to say") is False  # 无判词→False
    assert audit_mod._parse_judge_verdict("") is False


def test_real_mode_runs_with_injected_factories_no_network():
    """注入 mock distractor+judge:real-mode(fixture_mode=False)不再 raise,
    且 α_judge 由注入的 judge 决定(网络零发生)。"""
    calls = {"distract": 0, "judge": 0}

    def fake_distract(rec, k):
        calls["distract"] += 1
        return [f"wrong-{i}" for i in range(k)]

    def fake_judge(rec, distractor, idx):
        calls["judge"] += 1
        return distractor == "wrong-0"  # 每题恰好 1/k 被误接受

    r = audit_mod.audit(CORPUS, k=3, fixture_mode=False,
                        distractor_fn=fake_distract, judge_fn=fake_judge)
    assert calls["distract"] == len(CORPUS)         # 每题调一次干扰器
    assert calls["judge"] == len(CORPUS) * 3        # 每个探针调一次 judge
    assert r["accepted"] == len(CORPUS)             # 每题 1 个 wrong-0 被接受
    assert r["total"] == len(CORPUS) * 3
    assert abs(r["alpha_judge"] - 1 / 3) < 1e-9      # 每题 1/3 探针被误接受


def test_real_mode_raises_when_only_one_factory_injected():
    """只注入一个工厂仍是 real-mode 缺件 → fail-loud(不半吊子跑)。"""
    for kw in ({"distractor_fn": lambda r, k: ["x"]}, {"judge_fn": lambda r, d, i: True}):
        try:
            audit_mod.audit(CORPUS, k=3, fixture_mode=False, **kw)
        except NotImplementedError:
            continue
        raise AssertionError("只注入一个工厂应仍 raise NotImplementedError")


def test_real_judge_and_ladder_judge_share_prompt_contract():
    """审计内部 judge 与 ladder canonical judge 同源:两者都经 _judge_prompt。
    钉住"除记忆块外全部锁死"——审计与打分必须是同一个 judge。"""
    seen = {}

    def spy_chat(prompt, backbone, max_tokens):
        seen["prompt"] = prompt
        return "NO"

    orig = audit_mod._chat_completion
    audit_mod._chat_completion = spy_chat
    try:
        ladder_judge = audit_mod.make_real_ladder_judge_fn()
        ladder_judge("Q?", "ref", "cand", "gpt-5.5")
        p_ladder = seen["prompt"]
        inner = audit_mod.make_real_judge_fn("gpt-5.5")
        inner(_MC_REC, "some wrong answer", 0)
        p_inner = seen["prompt"]
    finally:
        audit_mod._chat_completion = orig
    # 两者都用 canonical _judge_prompt 的骨架(strict grader + YES/NO 契约)
    assert "strict grader" in p_ladder and "YES or NO" in p_ladder
    assert "strict grader" in p_inner and "YES or NO" in p_inner
    # 审计内部 judge 把干扰答案当 candidate、参考答案当 reference
    assert "some wrong answer" in p_inner
    assert "Carol" in p_inner  # _MC_REC 的参考答案
