"""质量回归基线 orchestrator 纯逻辑 + collect_scores 接线的 fixture 单测——零真
LLM(diff/容差/阈值/中位数/完整性/可比性/near-0 附注/接线)。真 LLM 手动跑不在此。"""
import json, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_quality_baseline as eqb  # noqa: E402
from eval_quality_baseline import (  # noqa: E402
    median, corpus_hash, diff_against_baseline, render_report, has_regression,
    exit_code, config_mismatch, save_baseline, load_baseline,
    EVAL_IDS, EVAL_THRESHOLDS,
)


def test_median():
    assert median([0.5]) == 0.5
    assert median([0.2, 0.8, 0.5]) == 0.5


def test_eval_ids_and_thresholds():
    assert EVAL_IDS == ("extract", "tom")
    assert EVAL_THRESHOLDS["tom"]["accuracy"] == 0.55
    assert "predicate" in EVAL_THRESHOLDS["extract"]
    assert "recall" not in EVAL_IDS   # recall 是 follow-up


def test_corpus_hash_stable_and_sensitive():
    a = [{"id": 1, "x": "a"}, {"id": 2}]
    assert corpus_hash(a) == corpus_hash(list(a))       # 稳定
    assert corpus_hash(a) != corpus_hash([{"id": 1, "x": "b"}, {"id": 2}])  # 内容变则变


def _baseline():
    return {
        "extract": {"predicate": {"median": 0.80, "threshold": 0.75}},
        "tom": {"accuracy": {"median": 0.65, "threshold": 0.55}},
    }


def test_diff_ok_within_tolerance():
    cur = {"extract": {"predicate": 0.78}, "tom": {"accuracy": 0.63}}
    f = diff_against_baseline(cur, _baseline(), tolerance=0.05)
    assert all(x["verdict"] == "OK" for x in f) and not has_regression(f) and exit_code(f) == 0


def test_diff_relative_regression():
    # 本测试要验证"仍达标、但相对基线中位数降超 tolerance"这条独立判据,故用局部 baseline
    # 把 predicate 阈值调低到 0.60(而非共享 _baseline() 的 0.75)。原因:共享 _baseline() 里
    # threshold(0.75) 恰好 == median(0.80)-tolerance(0.05),两条判据对任意 cur 恒同真同假,
    # REGRESSION 永远无法脱离 BELOW_THRESHOLD 单独触发(与 near-0 测试要求的
    # BELOW_THRESHOLD-优先 语义矛盾)——这是 fixture 数值巧合,不是 diff_against_baseline 的 bug。
    base = {"extract": {"predicate": {"median": 0.80, "threshold": 0.60}},
            "tom": {"accuracy": {"median": 0.65, "threshold": 0.55}}}
    cur = {"extract": {"predicate": 0.72}, "tom": {"accuracy": 0.65}}  # predicate 降 0.08>0.05,仍达标(0.72≥0.60)
    f = diff_against_baseline(cur, base, tolerance=0.05)
    r = [x for x in f if x["metric"] == "predicate"][0]
    assert r["verdict"] == "REGRESSION" and has_regression(f) and exit_code(f) == 1


def test_diff_below_threshold():
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.50}}  # tom 破 0.55 地板
    f = diff_against_baseline(cur, _baseline(), tolerance=0.20)
    assert [x for x in f if x["eval_id"] == "tom"][0]["verdict"] == "BELOW_THRESHOLD"
    assert exit_code(f) == 1


def test_diff_errored_dim_is_exit_2_not_regression():
    cur = {"extract": {"predicate": 0.80}, "tom": None}   # tom 采分失败(None)
    f = diff_against_baseline(cur, _baseline(), tolerance=0.05)
    assert [x for x in f if x["eval_id"] == "tom"][0]["verdict"] == "ERRORED"
    assert not has_regression(f) and exit_code(f) == 2


def test_diff_missing_dim_when_baseline_lacks_it():
    # 基线只有 extract(缺 tom)→ tom 报 MISSING(非静默 exit 0)——codex #1
    base = {"extract": {"predicate": {"median": 0.80, "threshold": 0.75}}}
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.65}}
    f = diff_against_baseline(cur, base, tolerance=0.05)
    assert [x for x in f if x["eval_id"] == "tom"][0]["verdict"] == "MISSING"
    assert exit_code(f) == 2


def test_report_near_zero_network_annotation():
    # 某维全指标近 0 → 报告附注疑似网络(但仍 BELOW_THRESHOLD 不隐藏)——codex #4
    cur = {"extract": {"predicate": 0.0}, "tom": {"accuracy": 0.65}}
    f = diff_against_baseline(cur, _baseline(), tolerance=0.05)
    rep = render_report(f, {"model": "m"}, cur)
    assert "BELOW_THRESHOLD" in rep and "疑似网络" in rep


def test_config_mismatch_model_and_hash():
    meta = {"model": "m1", "corpus_hash": {"extract": "h1", "tom": "h2"}}
    assert config_mismatch(meta, "m1", {"extract": "h1", "tom": "h2"}) == []       # 全一致
    assert "model" in " ".join(config_mismatch(meta, "m2", {"extract": "h1", "tom": "h2"}))
    assert "extract" in " ".join(config_mismatch(meta, "m1", {"extract": "hX", "tom": "h2"}))


def test_save_baseline_requires_all_dims(tmp_path):
    # 任一配置维 None → 拒写(raise),保护旧基线——codex #1/#12
    with pytest.raises(ValueError):
        save_baseline(tmp_path / "b.json", {"extract": {"predicate": 0.8}, "tom": None},
                      {"model": "m"})
    assert not (tmp_path / "b.json").exists()


def test_baseline_roundtrip(tmp_path):
    p = tmp_path / "eval_baseline.json"
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.65}}
    save_baseline(p, cur, {"model": "m", "rounds": 3, "max_items": None, "tolerance": 0.05,
                           "corpus_hash": {"extract": "h1", "tom": "h2"}})
    loaded = load_baseline(p)
    assert loaded["evals"]["extract"]["predicate"]["median"] == 0.80
    assert loaded["evals"]["extract"]["predicate"]["threshold"] == EVAL_THRESHOLDS["extract"]["predicate"]
    assert loaded["evals"]["tom"]["accuracy"]["threshold"] == 0.55
    assert load_baseline(tmp_path / "nope.json") is None
