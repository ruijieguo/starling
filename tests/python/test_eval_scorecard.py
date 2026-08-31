"""PR-2: 记分卡 reporter(scripts/eval_scorecard.py)的纯逻辑测试。

只测离线渲染逻辑(无 `_core`、无网络):
  - judge band 门:|Δ| < α_judge 一律降级 n.s.,不吹"提升/不降"
  - 可比性门:embedder 不一致 → 报告显式列不可比项
  - 防守 FAIL / 进攻 CONFIRMED 的分类与组合级判定
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SC = Path(__file__).resolve().parents[2] / "scripts" / "eval_scorecard.py"
_spec = importlib.util.spec_from_file_location("eval_scorecard", _SC)
scorecard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorecard)


def _ladder(benchmark, embedder, verdicts):
    return {"benchmark": benchmark, "corpus_hash": "sha256:deadbeef",
            "config": {"embedder": embedder}, "alpha": 0.05,
            "backbones": ["a", "b"], "verdicts": verdicts}


def test_band_downgrades_small_delta_to_ns():
    """Δ=+0.08 但 α_judge=0.43 → band 内 → 防守判定必须是 n.s.,不吹提升。"""
    rep = _ladder("lme", "text-embedding-v3", [
        {"subset": "s1", "defense": {"s_rag": 0.75, "s_star": 0.83,
                                     "delta": 0.08, "backbones_same_sign": 2}},
    ])
    audits = {"lme": {"benchmark": "lme", "alpha_judge": 0.43, "unusable": True}}
    md = scorecard.render([rep], audits)
    assert "不降 (n.s.)" in md
    assert "提升" not in md.split("### 进攻层")[0]  # 防守段不得出现"提升"


def test_defense_fail_flagged_and_blocks_success():
    """S_star ≪ S_rag(超出 band)→ FAIL,且组合级判定不成功。"""
    rep = _ladder("lme", "e", [
        {"subset": "s1", "defense": {"s_rag": 0.80, "s_star": 0.50,
                                     "delta": -0.30, "backbones_same_sign": 0}},
    ])
    md = scorecard.render([rep], {})
    assert "FAIL (回归)" in md
    assert "未达成" in md


def test_attack_confirmed_requires_two_backbones():
    """Δ vs 上限 > band 且 ≥2 backbone 同号 → CONFIRMED;否则 PLAUSIBLE。"""
    rep = _ladder("memsyco", "e", [
        {"subset": "conflict",
         "attack": {"ceiling": 0.41, "s_star": 0.63, "delta_vs_ceiling": 0.22,
                    "backbones_same_sign": 2},
         "extraction_tax": {"tax": 0.05}},
    ])
    md = scorecard.render([rep], {})
    assert "CONFIRMED" in md

    rep_single = _ladder("memsyco", "e", [
        {"subset": "conflict",
         "attack": {"ceiling": 0.41, "s_star": 0.63, "delta_vs_ceiling": 0.22,
                    "backbones_same_sign": 1}},
    ])
    assert "PLAUSIBLE" in scorecard.render([rep_single], {})


def test_comparability_warns_on_mixed_embedders():
    """两份报告 embedder 不同 → 可比性告警(MemDelta:换 embedder 逆转结论)。"""
    r1 = _ladder("a", "emb-X", [])
    r2 = _ladder("b", "emb-Y", [])
    md = scorecard.render([r1, r2], {})
    assert "可比性告警" in md


def test_success_needs_three_confirmed_incl_non_hitom():
    """组合级成功:≥3 CONFIRMED 且含 ≥1 非 HiToM。全 HiToM 不算成功。"""
    def _attack(sub):
        return {"subset": sub, "attack": {"ceiling": 0.4, "s_star": 0.7,
                "delta_vs_ceiling": 0.3, "backbones_same_sign": 2}}
    all_hitom = _ladder("hitom", "e", [_attack("o2"), _attack("o3"), _attack("o4")])
    md = scorecard.render([all_hitom], {})
    assert "未达成" in md  # 3 CONFIRMED 但全 HiToM → 不成功

    mixed = [
        _ladder("hitom", "e", [_attack("o3")]),
        _ladder("memsyco", "e", [_attack("conflict")]),
        _ladder("socialmem", "e", [_attack("attribution")]),
    ]
    assert "✅ 成功" in scorecard.render(mixed, {})
