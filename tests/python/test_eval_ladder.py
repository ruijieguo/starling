"""PR-1: 归因阶梯 runner(scripts/eval_ladder.py)的纯逻辑测试。

只测 fixture-mode 骨架的确定性与判据正确性(离线、无 `_core`、无网络):
  - 六台阶笛卡尔展开的 cell 数与确定性
  - aggregate 跨 backbone×seed 取中位数
  - defense / attack / extraction_tax 判据分类
real-mode(接 S_rag/S_star 真跑)是 PR-3 的 gated 真跑,不在此测。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# scripts/ 不是包,用 spec 从文件路径加载 runner 模块。
_LADDER = Path(__file__).resolve().parents[2] / "scripts" / "eval_ladder.py"
_spec = importlib.util.spec_from_file_location("eval_ladder", _LADDER)
ladder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ladder)


# ---- 一个最小合成语料:两个 subset,便于逐 subset 断言 ----
CORPUS = [
    {"item_id": "a0", "subset": "alpha", "options": ["x", "y"], "answer": 0},
    {"item_id": "a1", "subset": "alpha", "options": ["x", "y"], "answer": 1},
    {"item_id": "b0", "subset": "beta", "options": ["x", "y", "z"], "answer": 2},
]


def _run(stages, backbones, seeds):
    """跑一次完整 fixture 阶梯,返回 build_report 的产物。"""
    config = {"embedder": "fixture", "k": 10, "judge": "fixture",
              "router_gate": "off", "mode": "fixture", "seeds": seeds}
    cells = [ladder.run_cell(stage, bb, seed, CORPUS, True, config)
             for stage in stages for bb in backbones for seed in seeds]
    subsets = sorted({r["subset"] for r in CORPUS})
    return ladder.build_report("synthetic", CORPUS, cells, stages, backbones,
                               subsets, ladder.DEFAULT_ALPHA, config)


def test_cell_count_is_cartesian_product():
    stages = list(ladder.ALL_STAGES)          # 6
    rep = _run(stages, ["fixtureA", "fixtureB"], [0, 1, 2])   # 2×3
    assert len(rep["cells"]) == 6 * 2 * 3


def test_fixture_is_deterministic():
    """同 (stage,backbone,seed) 两次跑必须逐 cell 相同——归因阶梯要可复现。"""
    r1 = _run(list(ladder.ALL_STAGES), ["fixtureA"], [0, 1])
    r2 = _run(list(ladder.ALL_STAGES), ["fixtureA"], [0, 1])
    assert r1["cells"] == r2["cells"]
    assert r1["aggregate"] == r2["aggregate"]


def test_corpus_hash_changes_with_content():
    h_same = ladder.corpus_hash(CORPUS)
    assert h_same == ladder.corpus_hash(CORPUS)          # 稳定
    mutated = CORPUS + [{"item_id": "c0", "subset": "alpha",
                         "options": ["x", "y"], "answer": 0}]
    assert ladder.corpus_hash(mutated) != h_same         # 内容变则 hash 变


def test_aggregate_takes_median_over_backbones_and_seeds():
    rep = _run(list(ladder.ALL_STAGES), ["fixtureA", "fixtureB"], [0, 1, 2])
    agg = rep["aggregate"]
    # 每个 stage 都有 per-subset + overall 的中位数
    for stage in ladder.ALL_STAGES:
        assert set(agg[stage]) == {"alpha", "beta", "overall"}
        for v in agg[stage].values():
            assert 0.0 <= v <= 1.0


def _agg(median_map: dict, by_bb: dict | None = None) -> dict:
    """把手写的 stage→subset→值 包成 classify 期望的 {median, by_backbone}。
    by_backbone 缺省为空 → 同号计数为 0(单模型/待复现路径)。"""
    return {"median": median_map, "by_backbone": by_bb or {}}


def test_defense_verdict_flags_regression():
    """人造 aggregate:S_star ≪ S_rag → 防守判据必须报 FAIL(回归)。"""
    agg = _agg({
        "S_rag":         {"alpha": 0.80},
        "S_star":        {"alpha": 0.50},   # 远低于 S_rag → 回归
        "S_full":        {"alpha": 0.82},
        "S_star_oracle": {"alpha": 0.85},
    })
    rows = ladder.classify(agg, ["S_rag", "S_star", "S_full", "S_star_oracle"],
                           ["alpha"], ladder.DEFAULT_ALPHA)
    d = rows[0]["defense"]
    assert d["verdict"].startswith("FAIL")
    assert d["delta"] == pytest.approx(-0.30)


def test_attack_verdict_requires_exceeding_both_ceilings():
    """S_star 仅略高于 S_rag 但未超 max(S_full,S_rag)+α → attack=none。"""
    agg = _agg({
        "S_rag":  {"alpha": 0.60},
        "S_full": {"alpha": 0.75},        # 上限 = 0.75
        "S_star": {"alpha": 0.70},        # 未超上限 → 不算进攻成功
    })
    rows = ladder.classify(agg, ["S_rag", "S_full", "S_star"],
                           ["alpha"], ladder.DEFAULT_ALPHA)
    a = rows[0]["attack"]
    assert a["ceiling"] == pytest.approx(0.75)
    assert a["verdict"].startswith("none")


def test_extraction_tax_is_oracle_minus_star():
    agg = _agg({
        "S_star_oracle": {"alpha": 0.90},
        "S_star":        {"alpha": 0.78},
        "S_rag":         {"alpha": 0.75},
    })
    rows = ladder.classify(agg, ["S_star_oracle", "S_star", "S_rag"],
                           ["alpha"], ladder.DEFAULT_ALPHA)
    tax = rows[0]["extraction_tax"]
    assert tax["tax"] == pytest.approx(0.12)


def test_unknown_stage_rejected_by_main():
    """main 对未知 stage 名 fail-loud(stage 名是判据契约,不是自由字符串)。"""
    rc = ladder.main(["--benchmark", "x", "--corpus", str(_LADDER),
                      "--stages", "S0,BOGUS", "--fixture-mode"])
    assert rc == 1
