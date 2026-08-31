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
