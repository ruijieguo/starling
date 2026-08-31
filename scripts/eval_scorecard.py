#!/usr/bin/env python3
"""评测组合记分卡 reporter(评测组合方案 §7 / impl-spec §5)。

吃一组 `build/ladder_*.json`(可选 `build/judge_audit_*.json`),出一张两段式
md 记分卡:防守层(证明不下降)+ 进攻层(证明大幅提升)。核心纪律:

  - **judge band 门**:每个基准的 α_judge(judge 对抗审计产物)注入为该基准的
    不可解读带;所有 |Δ| < α_judge 的一律标 `n.s.`,不得作"提升/不降"证据。
  - **可比性门**:并列展示的 ladder 报告必须 embedder 一致(MemDelta:换 embedder
    能逆转结论)。config.embedder 不一致 → 拒绝并列,报告显式列不可比项。
  - **绝不输出掩盖子集结构的聚合 SOTA 数字**——逐子集/逐基准出行,不合并成单分。

  python scripts/eval_scorecard.py \
      --ladder build/ladder_longmemeval.json build/ladder_socialmem.json \
      --judge-audit build/judge_audit_longmemeval.json \
      --out build/scorecard.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _band_for(benchmark: str, audits: dict[str, dict], fallback: float) -> float:
    """该基准的不可解读带:优先用 judge 审计的 α_judge,否则回退到 ladder 的 alpha。"""
    a = audits.get(benchmark)
    return a["alpha_judge"] if a else fallback


def _defense_rows(rep: dict, band: float) -> list[dict]:
    """防守层逐子集行:S_rag / S_star / Δ / band / 多模型 / 判定。
    band 内的 Δ 一律降级为 n.s.(不可解读),不吹"持平/提升"。"""
    rows = []
    for v in rep.get("verdicts", []):
        d = v.get("defense")
        if not d:
            continue
        delta = d["delta"]
        n_same = d.get("backbones_same_sign", 0)
        if abs(delta) < band:
            verdict = "不降 (n.s.)"          # band 内:无法区分,不解读
        elif delta > 0:
            verdict = "提升" if n_same >= 2 else "提升 (单模型待复现)"
        else:
            verdict = "**FAIL (回归)**"
        rows.append({
            "row": f"{rep['benchmark']} {v['subset']}",
            "s_rag": d["s_rag"], "s_star": d["s_star"], "delta": delta,
            "band": band, "same": n_same, "verdict": verdict,
        })
    return rows


def _attack_rows(rep: dict, band: float) -> list[dict]:
    """进攻层逐基准行:max(full,rag) / S_star / Δ vs 上限 / 多模型 / 判定。
    band 内的提升不算数(降级 none);CONFIRMED 需超上限+band 且 ≥2 backbone 同号。"""
    rows = []
    for v in rep.get("verdicts", []):
        a = v.get("attack")
        if not a:
            continue
        delta = a["delta_vs_ceiling"]
        n_same = a.get("backbones_same_sign", 0)
        floor = max(band, 0.05)
        if delta > floor and n_same >= 2:
            verdict = "CONFIRMED"
        elif delta > floor:
            verdict = "PLAUSIBLE (单模型待复现)"
        else:
            verdict = "none (未超上限/带内)"
        rows.append({
            "row": f"{rep['benchmark']} {v['subset']}",
            "ceiling": a["ceiling"], "s_star": a["s_star"], "delta": delta,
            "band": band, "same": n_same, "verdict": verdict,
            "tax": v.get("extraction_tax", {}).get("tax"),
        })
    return rows


def _comparability(reps: list[dict]) -> list[str]:
    """并列展示前的可比性检查:embedder 必须一致(MemDelta 警示)。"""
    problems = []
    embedders = {r["benchmark"]: r.get("config", {}).get("embedder") for r in reps}
    distinct = set(embedders.values())
    if len(distinct) > 1:
        problems.append(f"embedder 不一致 → 不可并列比较:{embedders}")
    return problems


def render(reps: list[dict], audits: dict[str, dict]) -> str:
    lines = ["## Starling 评测组合记分卡", ""]

    # 可比性门(不阻断渲染,但显式告警,读者自行判断跨基准可比性)。
    problems = _comparability(reps)
    if problems:
        lines.append("> ⚠ **可比性告警**(MemDelta:换 embedder 可逆转结论):")
        for p in problems:
            lines.append(f"> - {p}")
        lines.append("")

    # 防守层
    lines += ["### 防守层(证明不下降)", "",
              "| 基准 / 子集 | S_rag | S_star | Δ | judge band | 多模型 | 判定 |",
              "|---|---|---|---|---|---|---|"]
    any_fail = False
    for rep in reps:
        band = _band_for(rep["benchmark"], audits, rep.get("alpha", 0.05))
        for r in _defense_rows(rep, band):
            if "FAIL" in r["verdict"]:
                any_fail = True
            same = "—" if r["same"] == 0 else f"{r['same']} ✓"
            lines.append(f"| {r['row']} | {r['s_rag']:.3f} | {r['s_star']:.3f} | "
                         f"{r['delta']:+.3f} | ±{r['band']:.3f} | {same} | {r['verdict']} |")

    # 进攻层
    lines += ["", "### 进攻层(证明大幅提升)", "",
              "| 基准 / 子集 | max(full,rag) | S_star | Δ vs 上限 | judge band | 多模型 | 抽取税 | 判定 |",
              "|---|---|---|---|---|---|---|---|"]
    n_confirmed = 0
    confirmed_non_hitom = 0
    for rep in reps:
        band = _band_for(rep["benchmark"], audits, rep.get("alpha", 0.05))
        for r in _attack_rows(rep, band):
            if r["verdict"] == "CONFIRMED":
                n_confirmed += 1
                if "hitom" not in rep["benchmark"].lower():
                    confirmed_non_hitom += 1
            same = "—" if r["same"] == 0 else f"{r['same']} ✓"
            tax = "—" if r["tax"] is None else f"{r['tax']:+.3f}"
            lines.append(f"| {r['row']} | {r['ceiling']:.3f} | {r['s_star']:.3f} | "
                         f"{r['delta']:+.3f} | ±{r['band']:.3f} | {same} | {tax} | {r['verdict']} |")

    # judge 审计脚注 + unusable 告警
    lines += ["", "### judge 对抗审计(不可解读带)", ""]
    if audits:
        lines += ["| 基准 | α_judge | 判定 |", "|---|---|---|"]
        for bm, a in audits.items():
            warn = " ⚠ JUDGE UNUSABLE" if a.get("unusable") else ""
            lines.append(f"| {bm} | {a['alpha_judge']:.4f} | "
                         f"{'不可用' + warn if a.get('unusable') else 'ok'} |")
    else:
        lines.append("> (无 judge 审计产物;band 回退到各 ladder 的 alpha 常量)")

    # 组合级成功标准(可证伪,§4.3)
    lines += ["", "### 组合级判定", "",
              f"- 防守层 FAIL 子集:{'**有(需先修回归)**' if any_fail else '无 ✓'}",
              f"- 进攻层 CONFIRMED 基准数:{n_confirmed}(非 HiToM:{confirmed_non_hitom})",
              "- 成功标准:防守无 FAIL **且** 进攻 ≥3 CONFIRMED(含 ≥1 非 HiToM)。"]
    success = (not any_fail) and n_confirmed >= 3 and confirmed_non_hitom >= 1
    lines.append(f"- **组合判定:{'✅ 成功' if success else '⚠ 未达成(如实降级主张,不修辞化)'}**")

    # 脚注:配置指纹(可比性依据)
    lines += ["", "---", "脚注(可比性指纹):"]
    for rep in reps:
        cfg = rep.get("config", {})
        lines.append(f"- {rep['benchmark']}: embedder={cfg.get('embedder')} "
                     f"corpus_hash={rep.get('corpus_hash')} "
                     f"backbones={rep.get('backbones')}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="评测组合记分卡 reporter。")
    p.add_argument("--ladder", type=Path, nargs="+", required=True,
                   help="一组 ladder JSON(eval_ladder.py 产物)。")
    p.add_argument("--judge-audit", type=Path, nargs="*", default=[],
                   help="一组 judge 审计 JSON(eval_judge_audit.py 产物;可选)。")
    p.add_argument("--out", type=Path, default=Path("build/scorecard.md"))
    args = p.parse_args(argv)

    reps = []
    for lp in args.ladder:
        if not lp.exists():
            print(f"ERROR: ladder report not found: {lp}", file=sys.stderr)
            return 1
        reps.append(_load(lp))

    audits: dict[str, dict] = {}
    for ap in args.judge_audit:
        if not ap.exists():
            print(f"ERROR: judge audit not found: {ap}", file=sys.stderr)
            return 1
        a = _load(ap)
        audits[a["benchmark"]] = a

    md = render(reps, audits)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md)
    print(f"Scorecard written to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
