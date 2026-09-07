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


# ---- per-subset 不可解读带(_subset_bands + classify 用 band 判据)----------

_MC_FREE_CORPUS = [
    {"item_id": "m0", "subset": "socialmem_mc", "options": ["x", "y"],
     "answer": 0, "answer_format": "multiple_choice"},
    {"item_id": "f0", "subset": "socialmem_free", "options": [],
     "answer": "some reference text", "answer_format": "long_form"},
]


def test_subset_bands_mc_uses_alpha_free_uses_alpha_when_no_audit():
    """无 judge 审计:MC 与自由文本都回退 alpha(诚实,不凭空抬带)。"""
    bands = ladder._subset_bands(_MC_FREE_CORPUS,
                                 ["socialmem_mc", "socialmem_free"],
                                 ladder.DEFAULT_ALPHA, None)
    assert bands["socialmem_mc"] == ladder.DEFAULT_ALPHA
    assert bands["socialmem_free"] == ladder.DEFAULT_ALPHA


def test_subset_bands_free_lifts_to_alpha_judge():
    """有 judge 审计且 α_judge>alpha:自由文本带抬到 α_judge;MC 不受影响
    (MC 是确定性 index 比对,与 judge 误接受率无关)。"""
    audit = {"subset_alpha": {"socialmem_free": 0.22, "socialmem_mc": 0.99}}
    bands = ladder._subset_bands(_MC_FREE_CORPUS,
                                 ["socialmem_mc", "socialmem_free"],
                                 ladder.DEFAULT_ALPHA, audit)
    assert bands["socialmem_free"] == pytest.approx(0.22)   # judge 打分 → 抬带
    assert bands["socialmem_mc"] == ladder.DEFAULT_ALPHA     # 确定性 → 不抬


def test_subset_bands_free_keeps_alpha_when_audit_below_alpha():
    """α_judge < alpha:带取 max → 仍是 alpha(带只会被抬高,不被 judge 压低)。"""
    audit = {"subset_alpha": {"socialmem_free": 0.01}}
    bands = ladder._subset_bands(_MC_FREE_CORPUS, ["socialmem_free"],
                                 ladder.DEFAULT_ALPHA, audit)
    assert bands["socialmem_free"] == ladder.DEFAULT_ALPHA


def test_classify_free_band_flips_verdict_to_ns():
    """同一个 Δ=0.12 的提升:MC 带(0.05)判 PASS+,自由文本带(0.20)判 n.s.。
    钉住"judge 噪声吃掉小提升"这条诚信脊柱——band 必须真正进判据。"""
    med = {
        "S_rag":  {"socialmem_mc": 0.60, "socialmem_free": 0.60},
        "S_star": {"socialmem_mc": 0.72, "socialmem_free": 0.72},  # 两者都 +0.12
    }
    agg = _agg(med)
    bands = {"socialmem_mc": 0.05, "socialmem_free": 0.20}
    rows = ladder.classify(agg, ["S_rag", "S_star"],
                           ["socialmem_mc", "socialmem_free"],
                           ladder.DEFAULT_ALPHA, bands)
    by_subset = {r["subset"]: r for r in rows}
    assert by_subset["socialmem_mc"]["band"] == 0.05
    assert by_subset["socialmem_free"]["band"] == 0.20
    # MC:Δ=0.12 > 0.05 → 提升(单模型 by_bb 空 → 待复现)
    assert by_subset["socialmem_mc"]["defense"]["verdict"].startswith("PASS+")
    # 自由文本:Δ=0.12 < 0.20 → 落在不可解读带内 → n.s.
    assert by_subset["socialmem_free"]["defense"]["verdict"].startswith("PASS (")


# ---- 断点续跑 journal(几十小时真跑的保命绳)-------------------------------
# 真跑一题 S_star ~26 分钟,50 题双 backbone 是几十小时连续 API 调用。中途一次
# Clash 抖动/限流若让整轮从头再来就是赌博。这几条钉住 journal 的三条纪律:
#   1. 成功判分落盘、重启跳过;2. error 行必须重试(不得永久钉成 miss);
#   3. 失败题排除出统计(绝不当 0 分,否则分数被静默污染)。


def test_journal_roundtrip_and_resume_skip(tmp_path):
    """写入的判分能读回,key 为 (stage,backbone,seed,item)。"""
    j = tmp_path / "j.jsonl"
    ladder.append_journal(j, {"key": "S_star|bbA|0|q1", "stage": "S_star",
                              "backbone": "bbA", "seed": 0, "item_id": "q1",
                              "ok": True})
    ladder.append_journal(j, {"key": "S_star|bbA|0|q2", "stage": "S_star",
                              "backbone": "bbA", "seed": 0, "item_id": "q2",
                              "ok": False})
    done = ladder.load_journal(j)
    assert done == {"S_star|bbA|0|q1": True, "S_star|bbA|0|q2": False}
    assert ladder._journal_key("S_star", "bbA", 0, "q1") == "S_star|bbA|0|q1"


def test_journal_error_rows_are_retried_not_scored_as_miss(tmp_path):
    """error 行不进 done → 重启会重试;一次网络抖动不得把该题永久钉成 miss。"""
    j = tmp_path / "j.jsonl"
    ladder.append_journal(j, {"key": "S_star|bbA|0|q1", "error": "TimeoutError: boom"})
    assert ladder.load_journal(j) == {}


def test_journal_half_written_line_is_discarded(tmp_path):
    """进程被 kill -9 写盘中途留下的半行 JSON → 丢弃该行,不炸、不误读。"""
    j = tmp_path / "j.jsonl"
    ladder.append_journal(j, {"key": "S_star|bbA|0|q1", "ok": True})
    with j.open("a", encoding="utf-8") as fh:
        fh.write('{"key": "S_star|bbA|0|q2", "ok": tr')      # 半行
    assert ladder.load_journal(j) == {"S_star|bbA|0|q1": True}


def test_run_cell_excludes_failed_items_from_stats(tmp_path):
    """抽错的题排除出统计(不计 0 分),scored_items 让 n 变小可见。"""
    corpus = [
        {"item_id": "ok1", "subset": "s", "question": "q", "options": ["a", "b"],
         "answer": 0, "answer_format": "multiple_choice"},
        {"item_id": "bad", "subset": "s", "question": "q", "options": ["a", "b"],
         "answer": 0, "answer_format": "multiple_choice"},
    ]

    def boom(stage, rec, seed, cfg):
        if rec["item_id"] == "bad":
            raise TimeoutError("network hiccup")
        return True

    j = tmp_path / "j.jsonl"
    orig = ladder._real_answer
    ladder._real_answer = boom
    try:
        cell = ladder.run_cell("S_star", "bbA", 0, corpus, False, {}, journal=j)
    finally:
        ladder._real_answer = orig

    # 1 题成功、1 题失败:正确率 1.0(而非 0.5),失败题不当 0 分
    assert cell["subset_scores"]["s"] == 1.0
    assert cell["scored_items"] == 1
    # 失败题以 error 行落盘 → 重启会重试
    assert ladder.load_journal(j) == {"S_star|bbA|0|ok1": True}
