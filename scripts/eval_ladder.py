#!/usr/bin/env python3
"""归因阶梯统一 runner(评测组合方案 §2 的支点)。

一条固定的六台阶阶梯,在**除"记忆层"外全部锁死**(backbone/embedder/
answer-prompt/judge/种子/语料 hash 相同)的前提下度量"这个数字是谁的功劳":

  S0 → S_rand → S_full → S_rag → S_star_oracle → S_star
                       └ 防守对照     └ 抽取税上界   └ 被测系统

  - 防守:S_star ≥ S_rag − α(不删检索、只叠认知层,不该更差)
  - 进攻:S_star − max(S_full, S_rag) > α(超两个上限才排除"窗口够大/检索够用")
  - 抽取税:S_star_oracle − S_star(gold 喂入 vs 真实 Extractor,隔离抽取质量)

本文件是 **PR-1**:先只打通 fixture-mode(离线、确定性、CI 可跑)的 runner
骨架——笛卡尔展开 (stage×backbone×seed)、多轮取中位数、Δ 计算、verdict 判定、
单一 JSON 产物。**real-mode(接 S_rag=vector_recall / S_star=RetrievalPlanner)
是 PR-3 的 gated 真跑**,此处只留 sound 的接线点,不行使网络/`_core`。

  python scripts/eval_ladder.py --benchmark longmemeval \
      --corpus tests/data/eval_longmemeval/sessions.jsonl \
      --stages S0,S_rand,S_full,S_rag,S_star_oracle,S_star \
      --backbones fixtureA,fixtureB --seeds 0,1,2 --fixture-mode \
      --report build/ladder_longmemeval.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

# 六台阶的规范顺序(记忆层从少到多)。runner 只跑 --stages 选中的子集,
# 但判据引用固定语义角色(S_rag=防守对照,S_full=长上下文上限,
# S_star_oracle=抽取税上界,S_star=被测系统),故名字是契约不是自由字符串。
ALL_STAGES = ("S0", "S_rand", "S_full", "S_rag", "S_star_oracle", "S_star")

# 防守/进攻判据的容差带(fixture 用固定值;real-mode 由 judge 对抗审计
# 测出的"不可解读带"注入,见组合方案 §3 / impl-spec §3)。
DEFAULT_ALPHA = 0.05

# fixture-mode 的每台阶"技能率":一个确定性 mock answerer 的期望正确率,
# 刻意排成合理的阶梯形状,好让下游 Δ/verdict 逻辑有非平凡输入可咀嚼——
# 这是**骨架自测**,不是任何真实能力声明。real-mode 下这张表不被使用。
_FIXTURE_SKILL = {
    "S0": 0.30,            # 闭卷地板
    "S_rand": 0.35,        # 随机片段仅略高于地板
    "S_full": 0.82,        # 长上下文上限
    "S_rag": 0.80,         # 朴素 RAG(防守对照物)
    "S_star_oracle": 0.90, # gold 喂入 → 表征能力上界
    "S_star": 0.85,        # 被测系统(带抽取税,故 < oracle)
}


def median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def corpus_hash(records: list[dict]) -> str:
    """语料内容确定性 hash(可比性):同内容同 hash,内容变则变。

    与 eval_quality_baseline.corpus_hash 同构;此处独立实现以免 runner 被
    baseline 的阈值 import 链耦合(baseline 在 import 时读 P1/ToM 阈值常量)。
    real-mode 里抽取产物也要并入该 hash(见 impl-spec §2.3),防"换抽取模型偷偷刷分"。
    """
    blob = "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _fixture_correct(stage: str, item_id: str, seed: int) -> bool:
    """确定性 mock:是否答对,由 hash(stage,item,seed) 与台阶技能率比较决定。

    同 (stage,item,seed) 恒定 → 多轮可复现;跨 item 抖动 → 聚合出接近技能率
    的正确率。绝无网络/`_core`。"""
    skill = _FIXTURE_SKILL.get(stage, 0.5)
    h = hashlib.sha256(f"{stage}|{item_id}|{seed}".encode("utf-8")).hexdigest()
    draw = int(h[:8], 16) / 0xFFFFFFFF
    return draw < skill


def _real_answer(stage: str, record: dict, seed: int, config: dict) -> bool:
    """real-mode 一题一 cell:装配记忆块 → 问 backbone → 判分(PR-3)。

    每台阶只换"喂给 answerer 的记忆块"来源(impl-spec §2.1):
      S0            → 空块
      S_rand        → 全库随机 k 行(同一 seed)
      S_full        → 全 history 行拼接
      S_rag         → SemanticRetriever.vector_recall(k)  [防守对照物]
      S_star_oracle → RetrievalPlanner.run,库里 statement 由 gold 喂入(绕开 Extractor)
      S_star        → RetrievalPlanner.run,库里 statement 由真实 Extractor 抽出
    然后用**同一** answer-prompt + 同一 backbone 问 MC index,判分。

    **可测性接缝**:embedder 工厂与 answerer 都经 config 注入——
      - `config["core"]`:`_core` 模块(或离线测试的等价 stub)。
      - `config["make_pipeline"](db_path) -> (adapter, embedder, index)`:装配一个
        每题临时管线;real-mode 传 OpenAIEmbeddingAdapter,离线测试传 StubEmbeddingAdapter。
      - `config["extract"](adapter, item) -> None`:S_star 台阶把 raw_turns 经真
        Extractor 抽成带归属 statement;非 S_star 台阶不调用。
      - `config["answerer"](prompt, backbone) -> str`:问 MC index;real-mode 走
        eval_longmemeval 的 HTTP 路径,离线测试传确定性 mock。
    这样 `_real_answer` 的**装配逻辑**可离线测(见 test_eval_ladder_pipeline),
    真跑时未测的只剩 answerer/Extractor 的网络部分。
    """
    import tempfile

    from eval_longmemeval import _build_answer_prompt, _parse_option_index
    import eval_ladder_pipeline as pipe

    core = config["core"]
    make_pipeline = config["make_pipeline"]
    answerer = config["answerer"]
    k = config.get("k", 10)
    now_iso = config.get("now_iso", "2026-06-01T00:00:00Z")

    tmpdir = tempfile.mkdtemp(prefix=f"ladder_{stage}_")
    db_path = f"{tmpdir}/ladder.db"
    adapter, embedder, index = make_pipeline(db_path)

    # --- seed 库内容:S_star 走真 Extractor(带归属);oracle 用 gold;余用扁平 history ---
    if stage == "S_star":
        config["extract"](adapter, record)          # raw_turns → 带归属 statement
    elif stage == "S_star_oracle":
        gold = record.get("gold_statements") or []
        pipe.seed_gold_statements(db_path, record["item_id"], gold)
    else:
        pipe.seed_history_statements(db_path, record["item_id"], record.get("history", []))

    pipe.embed_seeded(core, adapter, embedder, index, now_iso)

    rb = pipe.recall_block(core, stage, adapter=adapter, embedder=embedder,
                           index=index, question=record["question"],
                           history=record.get("history", []), k=k, seed=seed)

    # 弃答题(is_abstain):planner 主动弃答且该题本无答案 → 记正确(认识论诚实)。
    if record.get("is_abstain"):
        return bool(rb["abstained"])

    recalled = [ln.lstrip("- ").strip() for ln in rb["block"].splitlines() if ln.strip()]
    prompt = _build_answer_prompt(record, recalled)
    resp = answerer(prompt, config.get("backbone", ""))
    try:
        pred = _parse_option_index(resp, len(record["options"]))
    except ValueError:
        return False
    return pred == int(record["answer"])


def run_cell(stage: str, backbone: str, seed: int, corpus: list[dict],
             fixture_mode: bool, config: dict) -> dict:
    """一个 (stage,backbone,seed) 单元:逐题判分,按 subset 聚合正确率。"""
    per_subset: dict[str, list[int]] = {}
    total_c = total_n = 0
    for rec in corpus:
        subset = rec.get("subset", "default")
        if fixture_mode:
            ok = _fixture_correct(stage, rec["item_id"], seed)
        else:
            # 注入当前 backbone,answerer 才知用哪个模型(多 backbone 同号归因命脉)。
            ok = _real_answer(stage, rec, seed, {**config, "backbone": backbone})
        per_subset.setdefault(subset, [0, 0])
        per_subset[subset][0] += int(ok)
        per_subset[subset][1] += 1
        total_c += int(ok)
        total_n += 1
    subset_scores = {s: (c / n if n else 0.0) for s, (c, n) in per_subset.items()}
    return {
        "stage": stage, "backbone": backbone, "seed": seed,
        "subset_scores": subset_scores,
        "overall": (total_c / total_n if total_n else 0.0),
        # 写入成本 real-mode 必填(MemDelta 警示);fixture 无成本。
        "ingest_cost": None,
    }


def aggregate(cells: list[dict], stages: list[str], backbones: list[str],
              subsets: list[str]) -> dict:
    """对每 (stage,backbone) 在 seeds 上取中位数;再对 backbones 取中位数。

    返回 agg[stage][subset] = 跨 backbone 的中位数,以及 agg[stage][subset+'_by_bb']
    = 每 backbone 的中位数(用于"≥2 backbone 同号"归因判定)。"""
    agg: dict[str, dict[str, float]] = {}
    by_bb: dict[str, dict[str, dict[str, float]]] = {}
    for stage in stages:
        agg[stage] = {}
        by_bb[stage] = {}
        for subset in subsets + ["overall"]:
            bb_medians = []
            for bb in backbones:
                seed_vals = [
                    (c["subset_scores"].get(subset) if subset != "overall" else c["overall"])
                    for c in cells if c["stage"] == stage and c["backbone"] == bb
                ]
                seed_vals = [v for v in seed_vals if v is not None]
                if seed_vals:
                    m = median(seed_vals)
                    bb_medians.append(m)
                    by_bb[stage].setdefault(subset, {})[bb] = m
            agg[stage][subset] = median(bb_medians) if bb_medians else None
    return {"median": agg, "by_backbone": by_bb}


def _same_sign_backbones(by_bb: dict, stage_hi: str, stage_lo: str,
                         subset: str, alpha: float) -> int:
    """有多少个 backbone 上 (stage_hi − stage_lo) > alpha(归因坐实用)。"""
    hi = by_bb.get(stage_hi, {}).get(subset, {})
    lo = by_bb.get(stage_lo, {}).get(subset, {})
    return sum(1 for bb in hi if bb in lo and (hi[bb] - lo[bb]) > alpha)


def classify(agg: dict, stages: list[str], subsets: list[str], alpha: float) -> list[dict]:
    """逐 subset 出防守/进攻判据(组合方案 §2 + impl-spec §4)。

    防守(需 S_rag & S_star):PASS+ / PASS(n.s.) / FAIL
    进攻(需 S_full/S_rag & S_star):CONFIRMED / PLAUSIBLE / none
    抽取税(需 S_star_oracle & S_star):S_star_oracle − S_star
    """
    med, by_bb = agg["median"], agg["by_backbone"]
    have = set(stages)
    out = []
    for subset in subsets:
        row: dict = {"subset": subset}
        s_rag = med.get("S_rag", {}).get(subset)
        s_star = med.get("S_star", {}).get(subset)
        s_full = med.get("S_full", {}).get(subset)
        s_oracle = med.get("S_star_oracle", {}).get(subset)

        # --- 防守判据 ---
        if {"S_rag", "S_star"} <= have and s_rag is not None and s_star is not None:
            d = s_star - s_rag
            n_same = _same_sign_backbones(by_bb, "S_star", "S_rag", subset, alpha)
            if d > alpha and n_same >= 2:
                verdict = "PASS+ (提升)"
            elif d > alpha:
                verdict = "PASS+ (提升, 单模型待复现)"
            elif d >= -alpha:
                verdict = "PASS (不降, n.s.)"
            else:
                verdict = "FAIL (回归)"
            row["defense"] = {"s_rag": s_rag, "s_star": s_star, "delta": d,
                              "backbones_same_sign": n_same, "verdict": verdict}

        # --- 进攻判据(超两个上限 + ≥2 backbone 同号)---
        if {"S_star"} <= have and s_star is not None and (s_full is not None or s_rag is not None):
            ceiling = max(x for x in (s_full, s_rag) if x is not None)
            d = s_star - ceiling
            # 同号计数针对"超过上限"的那个对照(取较高的 S_full/S_rag 作 lo 近似)
            lo_stage = "S_full" if (s_full is not None and (s_rag is None or s_full >= s_rag)) else "S_rag"
            n_same = _same_sign_backbones(by_bb, "S_star", lo_stage, subset, alpha)
            if d > max(alpha, 0.05) and n_same >= 2:
                verdict = "CONFIRMED"
            elif d > max(alpha, 0.05):
                verdict = "PLAUSIBLE (单模型待复现)"
            else:
                verdict = "none (未超上限)"
            row["attack"] = {"ceiling": ceiling, "s_star": s_star, "delta_vs_ceiling": d,
                             "ceiling_stage": lo_stage, "backbones_same_sign": n_same,
                             "verdict": verdict}

        # --- 抽取税 ---
        if {"S_star_oracle", "S_star"} <= have and s_oracle is not None and s_star is not None:
            row["extraction_tax"] = {"s_star_oracle": s_oracle, "s_star": s_star,
                                     "tax": s_oracle - s_star}
        out.append(row)
    return out


def build_report(benchmark: str, corpus: list[dict], cells: list[dict],
                 stages: list[str], backbones: list[str], subsets: list[str],
                 alpha: float, config: dict) -> dict:
    agg = aggregate(cells, stages, backbones, subsets)
    return {
        "benchmark": benchmark,
        "corpus_hash": corpus_hash(corpus),
        "config": config,
        "stages": stages,
        "backbones": backbones,
        "subsets": subsets,
        "alpha": alpha,
        "cells": cells,
        "aggregate": agg["median"],
        "verdicts": classify(agg, stages, subsets, alpha),
        # judge 对抗审计在 real-mode 由 eval_judge_audit 注入(impl-spec §3);
        # fixture 无 judge,band=alpha 常量。
        "judge_audit": None,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="归因阶梯统一 runner(fixture-mode 骨架)。")
    p.add_argument("--benchmark", required=True,
                   help="基准名(longmemeval/locomo/beam/socialmem/memsyco/...)")
    p.add_argument("--adapter", default="auto",
                   help="语料适配器(eval_adapters.ADAPTERS 的键);auto=按 benchmark 推断,"
                        "passthrough=仅轻校验。socialmembench 需两表,由调用方预归一。")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--stages", default=",".join(ALL_STAGES))
    p.add_argument("--backbones", default="fixtureA,fixtureB")
    p.add_argument("--seeds", default="0,1,2")
    p.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    p.add_argument("--fixture-mode", action="store_true",
                   help="离线确定性 mock answerer(CI)。省略 = real-mode(PR-3, gated)。")
    p.add_argument("--router-gate", choices=("on", "off"), default="off",
                   help="§4 进攻项的路由门控双版(fixture 仅记录,不改分)。")
    p.add_argument("--report", type=Path, default=Path("build/ladder.json"))
    args = p.parse_args(argv)

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stages if s not in ALL_STAGES]
    if unknown:
        print(f"ERROR: unknown stage(s): {unknown}; valid={ALL_STAGES}", file=sys.stderr)
        return 1
    backbones = [b.strip() for b in args.backbones.split(",") if b.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 1
    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    if not corpus:
        print(f"ERROR: empty corpus: {args.corpus}", file=sys.stderr)
        return 1

    # 语料归一:过一遍进攻层适配器(PR-4)。默认 passthrough(longmemeval 形状),
    # 也顺带校验规范字段;--adapter 选 memsyco 等把异构语料归一成规范 record。
    # socialmembench 需两张表(qa+conversations),不走单文件 corpus 路径,故不在此。
    import eval_adapters
    adapter_fn = eval_adapters.ADAPTERS.get(args.adapter)
    if adapter_fn is None:
        print(f"ERROR: unknown adapter: {args.adapter}; "
              f"valid={sorted(eval_adapters.ADAPTERS)}", file=sys.stderr)
        return 1
    try:
        corpus = adapter_fn(corpus)
    except eval_adapters.AdapterError as e:
        print(f"ERROR: adapter {args.adapter} 归一失败: {e}", file=sys.stderr)
        return 1

    subsets = sorted({r.get("subset", "default") for r in corpus})

    if not args.fixture_mode:
        print("ERROR: real-mode 是 PR-3 的 gated 真跑,尚未行使;请加 --fixture-mode "
              "跑骨架。", file=sys.stderr)
        return 1

    config = {"embedder": "fixture", "k": 10, "judge": "fixture",
              "router_gate": args.router_gate, "mode": "fixture",
              "seeds": seeds}
    cells = [run_cell(stage, bb, seed, corpus, args.fixture_mode, config)
             for stage in stages for bb in backbones for seed in seeds]

    report = build_report(args.benchmark, corpus, cells, stages, backbones,
                          subsets, args.alpha, config)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Report written to {args.report}", file=sys.stderr)

    # 骨架自检:fixture 阶梯必须产出 sane 结构(S_star>S_rag、oracle≥star)。
    any_fail = any(
        r.get("defense", {}).get("verdict", "").startswith("FAIL")
        for r in report["verdicts"]
    )
    for r in report["verdicts"]:
        d = r.get("defense", {})
        a = r.get("attack", {})
        print(f"[{r['subset']}] defense={d.get('verdict','—')} "
              f"(Δ={d.get('delta', 0):+.3f}) | attack={a.get('verdict','—')} "
              f"(Δ_ceil={a.get('delta_vs_ceiling', 0):+.3f})")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
