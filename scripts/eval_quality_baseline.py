#!/usr/bin/env python3
"""质量回归基线 orchestrator(dogfood 子项 C)。复用既有 2 维 benchmark harness
(extract F1 / ToM accuracy)的 run_one_round,全量小 corpus 真 LLM 跑 N 轮取中位数,
写/diff 一个 git-committed 基线 JSON,判质量回归。非 CI(真 LLM/Clash 不可靠)。

  python scripts/eval_quality_baseline.py --update   # 有意质量变更后建/更新基线
  python scripts/eval_quality_baseline.py --check     # 改 prompt/extractor 前后查回归
"""
from __future__ import annotations
import argparse, hashlib, json, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_p1_extractor import P1_THRESHOLDS               # noqa: E402
from eval_tom_bench import ACCURACY_THRESHOLD as TOM_THRESHOLD  # noqa: E402

EVAL_IDS = ("extract", "tom")   # recall(longmemeval)= follow-up
EVAL_THRESHOLDS: dict[str, dict[str, float]] = {
    "extract": dict(P1_THRESHOLDS),
    "tom": {"accuracy": TOM_THRESHOLD},
}
DEFAULT_BASELINE = Path(__file__).resolve().parents[1] / "tests" / "data" / "eval_baseline.json"
NETWORK_FLOOR = 0.05   # 某维全指标 < 此值 = 报告附注疑似网络(不隐藏,仍报 BELOW_THRESHOLD)


def median(values: list[float]) -> float:
    return float(statistics.median(values))


def corpus_hash(records: list[dict]) -> str:
    """corpus 内容确定性 hash(可比性 codex #10):同内容同 hash,内容变则变。"""
    blob = "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def diff_against_baseline(current: dict[str, dict[str, float] | None],
                          baseline_evals: dict, tolerance: float) -> list[dict]:
    """遍历**配置维**(EVAL_IDS,非仅基线维——故基线缺维 → MISSING,codex #1)。
    current[eval_id] 为 None = 该维采分失败/不完整 → ERRORED。"""
    findings: list[dict] = []
    for eval_id in EVAL_IDS:
        cur_eval = current.get(eval_id)
        base_eval = baseline_evals.get(eval_id)
        if base_eval is None:
            findings.append({"eval_id": eval_id, "metric": "*", "baseline": None,
                             "current": None, "threshold": None, "verdict": "MISSING"})
            continue
        if cur_eval is None:
            findings.append({"eval_id": eval_id, "metric": "*", "baseline": None,
                             "current": None, "threshold": None, "verdict": "ERRORED"})
            continue
        for metric, spec in base_eval.items():
            base, thr = spec["median"], spec["threshold"]
            cur = cur_eval.get(metric)
            if cur is None:
                verdict = "ERRORED"
            elif cur < thr:
                verdict = "BELOW_THRESHOLD"
            elif cur < base - tolerance:
                verdict = "REGRESSION"
            else:
                verdict = "OK"
            findings.append({"eval_id": eval_id, "metric": metric, "baseline": base,
                             "current": cur, "threshold": thr, "verdict": verdict})
    return findings


def has_regression(findings: list[dict]) -> bool:
    return any(f["verdict"] in ("REGRESSION", "BELOW_THRESHOLD") for f in findings)


def exit_code(findings: list[dict]) -> int:
    if has_regression(findings):
        return 1
    if any(f["verdict"] in ("ERRORED", "INCOMPLETE", "MISSING") for f in findings):
        return 2
    return 0


def _dim_all_near_zero(current: dict, eval_id: str) -> bool:
    ce = current.get(eval_id)
    return bool(ce) and all(v < NETWORK_FLOOR for v in ce.values())


def render_report(findings: list[dict], meta: dict, current: dict) -> str:
    mark = {"OK": "✅ OK", "REGRESSION": "⚠ REGRESSION", "BELOW_THRESHOLD": "✗ BELOW_THRESHOLD",
            "ERRORED": "⁇ ERRORED", "INCOMPLETE": "⁇ INCOMPLETE", "MISSING": "· MISSING"}
    lines = ["# 质量回归基线报告",
             f"model={meta.get('model')} rounds={meta.get('rounds')} max_items={meta.get('max_items')}",
             "", "| eval | metric | baseline | current | threshold | verdict |",
             "|---|---|---|---|---|---|"]
    for f in findings:
        b = "—" if f["baseline"] is None else f"{f['baseline']:.3f}"
        c = "—" if f["current"] is None else f"{f['current']:.3f}"
        t = "—" if f["threshold"] is None else f"{f['threshold']:.2f}"
        lines.append(f"| {f['eval_id']} | {f['metric']} | {b} | {c} | {t} | {mark.get(f['verdict'], f['verdict'])} |")
    # near-0 附注:诚实报不隐藏(codex #4)——0 分仍 BELOW_THRESHOLD,只提示可能是网络。
    for eval_id in EVAL_IDS:
        if _dim_all_near_zero(current, eval_id):
            lines.append(f"\n> ⚠ `{eval_id}` 全指标近 0 —— 疑似网络黑洞(Clash),查 stderr 的 "
                         f"transport WARN;非质量则换时刻重跑(见 clash-tun 记忆)。仍按 BELOW_THRESHOLD 计。")
    verdict = ("✗ 有质量回归" if has_regression(findings)
               else ("⁇ 有维度不可测/缺失,需重跑或重建" if exit_code(findings) == 2 else "✅ 无回归"))
    lines += ["", f"**总判定:{verdict}**"]
    return "\n".join(lines) + "\n"


def config_mismatch(baseline_meta: dict, cur_model: str, cur_hashes: dict[str, str]) -> list[str]:
    """基线 vs 当前配置不可比项(codex #10):model 或某维 corpus 内容变 → 不可 diff。"""
    out = []
    if baseline_meta.get("model") != cur_model:
        out.append(f"model: baseline={baseline_meta.get('model')} current={cur_model}")
    base_h = baseline_meta.get("corpus_hash", {})
    for eval_id in EVAL_IDS:
        if base_h.get(eval_id) != cur_hashes.get(eval_id):
            out.append(f"corpus[{eval_id}]: 内容变(hash 不匹配)")
    return out


def save_baseline(path: Path, current: dict[str, dict[str, float] | None], meta: dict) -> None:
    """写基线。**要求所有配置维都成功采分**(codex #1/#12)——任一 None → raise,不写、保旧基线。"""
    missing = [e for e in EVAL_IDS if current.get(e) is None]
    if missing:
        raise ValueError(f"拒绝写基线:以下配置维采分失败 {missing};保留旧基线,先重跑")
    evals = {
        eval_id: {m: {"median": v, "threshold": EVAL_THRESHOLDS[eval_id][m]}
                  for m, v in current[eval_id].items()}
        for eval_id in EVAL_IDS
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"meta": meta, "evals": evals}, indent=2, ensure_ascii=False) + "\n")


def load_baseline(path: Path) -> dict | None:
    return json.loads(Path(path).read_text()) if Path(path).exists() else None
