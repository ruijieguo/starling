#!/usr/bin/env python3
"""judge 对抗审计(评测组合方案 §3.1 / impl-spec §3.1;照搬 Penfield Labs 方法)。

**目的**:测出被测 judge 会把多少"话题相邻但事实错误"的答案误判为对。这个
接受率 = 分数的**不可解读带 α_judge**——记分卡里所有 Δ < α_judge 的一律标
`n.s.`,不得作为"提升/不降"证据。Penfield 在 LoCoMo 上实测 62.81%:α 高得
离谱就说明该基准默认 judge 不可用,须换更强 judge 或换结构化评分。

方法:
  对每道题,由"干扰器"LM 生成 K 个话题相邻但事实错误的答案,用被测 judge
  (同配置)去评;被判"正确"的比例 = α_judge。

本文件是 **PR-2**:fixture-mode(离线、确定性、CI 可跑)用一个确定性 mock 干扰器
+ mock judge 算出 α_judge,把整条审计管线(生成→评判→聚合→按基准出带)打通;
**real-mode(真干扰器 + 真 judge LLM)是 gated 真跑**,只留 sound 接线点,不行使网络。

  python scripts/eval_judge_audit.py --benchmark longmemeval \
      --corpus tests/data/eval_longmemeval/sessions.jsonl \
      --k 3 --fixture-mode --report build/judge_audit_longmemeval.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# α_judge 高于此阈值 → 该基准默认 judge 不可信,报告显式告警(Penfield: LoCoMo 62.81%)。
JUDGE_UNUSABLE_THRESHOLD = 0.40

# fixture 干扰器每题生成的对抗答案数(与 --k 一致时用 --k)。
DEFAULT_K = 3


def load_corpus(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _fixture_distractors(rec: dict, k: int) -> list[str]:
    """确定性 mock 干扰器:为一题造 k 个"话题相邻但事实错误"的答案。

    real-mode 由真 LM 生成(prompt:"给出与问题相关、听起来合理、但事实错误的答案")。
    fixture 里从选项中挑非正确项 + 合成变体,保证确定性与可复现。"""
    opts = rec.get("options")
    out: list[str] = []
    if opts:
        answer_idx = int(rec.get("answer", 0))
        wrong = [o for i, o in enumerate(opts) if i != answer_idx]
        out.extend(wrong[:k])
    # 不足 k 个则用确定性合成串补齐(话题词 + 错误后缀)。
    q = rec.get("question", "")
    topic = q.split()[0] if q else "it"
    while len(out) < k:
        h = hashlib.sha256(f"{rec.get('item_id','')}|{len(out)}".encode()).hexdigest()[:6]
        out.append(f"{topic} is actually {h}")
    return out[:k]


def _fixture_judge_accepts(rec: dict, distractor: str, idx: int) -> bool:
    """确定性 mock judge:是否把这个故意错误答案误判为对。

    用 (item_id, distractor, idx) 的哈希决定,使审计可复现。刻意让一部分
    "话题相邻"的错误答案蒙混过关(≈ 真 judge 对模糊答案的宽松),好让 α_judge
    非平凡。real-mode 下由真 judge(同评测配置)取代。"""
    # 完全字面等于某个正确选项才"显然对";否则按话题相邻度的哈希量决定。
    h = hashlib.sha256(f"{rec.get('item_id','')}|{distractor}|{idx}".encode()).hexdigest()
    frac = int(h[:4], 16) / 0xFFFF
    # ≈ 1/3 的话题相邻错误答案被误判为对(骨架自测量级,非真实声明)。
    return frac < 0.33


def audit(corpus: list[dict], k: int, fixture_mode: bool) -> dict:
    """跑一遍对抗审计,返回 α_judge + 分子分母 + 逐 subset 明细。"""
    if not fixture_mode:
        raise NotImplementedError(
            "real-mode judge 审计是 gated 真跑;PR-2 只打通 fixture 骨架。"
            "接线点:干扰器→真 LM chat completion(prompt 见 docstring),"
            "judge→与评测同配置的 LLM-judge(同 eval_longmemeval 的 answer/judge 路径)。")
    accepted = 0
    total = 0
    per_subset: dict[str, list[int]] = {}
    for rec in corpus:
        s = rec.get("subset", "default")
        per_subset.setdefault(s, [])
        for i, d in enumerate(_fixture_distractors(rec, k)):
            total += 1
            hit = int(_fixture_judge_accepts(rec, d, i))
            accepted += hit
            per_subset[s].append(hit)
    alpha_judge = (accepted / total) if total else 0.0
    subset_alpha = {
        s: (sum(v) / len(v) if v else 0.0) for s, v in per_subset.items()
    }
    return {
        "alpha_judge": alpha_judge,
        "accepted": accepted,
        "total": total,
        "subset_alpha": subset_alpha,
        "unusable": alpha_judge > JUDGE_UNUSABLE_THRESHOLD,
    }


def build_report(benchmark: str, corpus: list[dict], result: dict,
                 k: int, config: dict) -> dict:
    return {
        "benchmark": benchmark,
        "corpus_hash": _corpus_hash(corpus),
        "k": k,
        "config": config,
        "alpha_judge": result["alpha_judge"],
        "accepted": result["accepted"],
        "total": result["total"],
        "subset_alpha": result["subset_alpha"],
        "unusable": result["unusable"],
    }


def _corpus_hash(records: list[dict]) -> str:
    blob = "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="judge 对抗审计(fixture-mode 骨架)。")
    p.add_argument("--benchmark", required=True)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--fixture-mode", action="store_true",
                   help="离线确定性 mock 干扰器+judge(CI)。省略=real-mode(gated)。")
    p.add_argument("--report", type=Path, default=Path("build/judge_audit.json"))
    args = p.parse_args(argv)

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 1
    corpus = load_corpus(args.corpus)
    if not corpus:
        print(f"ERROR: empty corpus: {args.corpus}", file=sys.stderr)
        return 1
    if not args.fixture_mode:
        print("ERROR: real-mode judge 审计是 gated 真跑,尚未行使;请加 --fixture-mode。",
              file=sys.stderr)
        return 1

    config = {"judge": "fixture", "distractor": "fixture", "mode": "fixture"}
    result = audit(corpus, args.k, args.fixture_mode)
    report = build_report(args.benchmark, corpus, result, args.k, config)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Report written to {args.report}", file=sys.stderr)
    print(f"[{args.benchmark}] α_judge = {result['alpha_judge']:.4f} "
          f"({result['accepted']}/{result['total']})"
          + ("  ⚠ JUDGE UNUSABLE (换更强 judge 或结构化评分)" if result["unusable"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
