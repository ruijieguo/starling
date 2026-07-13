# 质量回归基线(dogfood 子项 C)— Design Spec

**Date:** 2026-07-13
**Slice:** 把既有成熟 benchmark eval harness 从「手动跑一次」变成「可重复的质量基线 + 回归信号」——让 prompt/gist/extractor 改动造成的质量退化被抓到。dogfood 弧线第三步(A 摄入 PR #52 / B 信号 PR #53 / 方案2 出锁 PR #54 之后)。

## Problem / Context

Starling 有一套**成熟的 benchmark eval**(`scripts/eval_*.py` + `tests/data/`):抽取 F1(`eval_p1_extractor`)、长期记忆多选准确率(`eval_longmemeval`)、ToM 准确率(`eval_tom2_starling`/`eval_tom_bench`、`eval_tombench_full`、`eval_fantom` 等)。每个都是「合成 corpus + ground-truth + 阈值 + 报告」的完整 harness。

**但真正带 LLM 的质量 eval 只手动跑**(`test_eval_*_harness.py` 全是 fixture-mode 自测,验 harness 代码、零真 LLM)。⇒ **质量没有连续信号**:一次 prompt 改、gist v2 default-flip、extractor 调整,若悄悄让抽取 F1 / ToM 准确率 / 召回率退化,没人会发现(手动 eval 不常跑、不 gated)。

**为何不评真实摄入数据**:真实摄入数据稀疏(52 statements)且无 ground truth,LLM-judge 信号噪。既有 benchmark corpus 有 ground truth、成熟可靠——**复用它们做连续基线**杠杆最大、避开稀疏数据问题(用户裁定 A)。

## Goal / Non-Goals

**Goal:** 一个 orchestrator,**复用**既有 3 个 harness 的打分函数,在**小固定 corpus 子集**上真 LLM 跑、取 N 轮中位数,写/diff 一个 git-committed 基线 JSON,判回归。让质量退化在改动前后一跑就现形。

**Non-Goals:**
- 新写 eval 逻辑 —— 复用既有 `run_one_round`/aggregate,不重造。
- dashboard 端点 —— git 基线 JSON 的历史即趋势(用户裁定 git-baseline-diff,非 B 风格端点)。
- 真实摄入数据 eval / 端到端记忆有用性 —— 数据稀疏、无 ground truth,不做。
- CI 集成 —— 真 LLM + Clash TUN 不可靠([[clash-tun-owns-all-network-flakiness]]),eval 跑在本地手动/定时,**不进 CI**。
- FANToM 维 —— 仓库无 `tests/data/eval_fantom/` corpus 数据,不纳入。
- 第 4+ 维(commitment/perception)—— measure-first,先在核心三维证明机制,后续再扩。

## Design

### ① Orchestrator:`scripts/eval_quality_baseline.py`

单文件 orchestrator,两模式(argparse):
- `--check`(默认):跑三维 → 算当前中位数 → diff git-committed 基线 → 打回归报告 → **回归时非零退出**。
- `--update`:跑三维 → **覆写**基线 JSON(仅在有意质量变更后手动跑)。
- 通用参数:`--rounds N`(默认 3,降噪)、`--tolerance T`(默认 0.05,吸收 LLM 噪声)、`--baseline PATH`(默认 `tests/data/eval_baseline.json`)、`--model`、`--max-items N`(每维子集大小,默认见 §②)。真 LLM 端点/key 从环境读(照既有 eval 脚本,`DASHSCOPE_API_KEY` 等;不打印 key)。

**关键结构(为可测)**:把「跑分」与「判/报」解耦:
- `collect_scores(rounds, max_items, model, base_url, api_key) → dict[eval_id → dict[metric → median]]`:真 LLM 段,调三维 harness 的 `run_one_round` 各 rounds 次、每指标取中位数。
- `diff_against_baseline(current, baseline, tolerance) → list[Finding]` + `render_report(findings) → str` + `has_regression(findings) → bool`:**纯逻辑、零 LLM**,fixture 单测覆盖。

### ② 三维 + 复用的 harness 函数 + corpus 子集(都在仓库)

| eval_id | harness(import,不重写) | corpus(取 first-N 确定子集) | 指标 |
|---|---|---|---|
| `extract_f1` | `eval_p1_extractor.run_one_round(corpus, base_url, api_key, model)` + `P1_THRESHOLDS`/`f1_score` | `tests/data/eval_p1_corpus.jsonl`(50) | f1(+ precision/recall) |
| `recall_accuracy` | `eval_longmemeval.run_one_round(corpus, subsets, fixture_mode=False)` + `ACCURACY_THRESHOLD`/`SUBSETS` | `tests/data/eval_longmemeval/sessions.jsonl`(24) | 多选准确率 |
| `tom_accuracy` | `eval_tom_bench.run_one_round(...)` + `ACCURACY_THRESHOLD`(=0.55)——与另两维同 `run_one_round` 形态、最干净(`eval_tom2_starling` 是 per-case、`eval_tombench_full` 是 run+aggregate,均不如它齐整) | `tests/data/eval_tom_bench/first_order.jsonl`(24) | 准确率 |

- **小固定子集**:各取前 `--max-items`(默认 15)条(确定性:同一 corpus 前 N 条,每次同样本→可比)。corpus 本就小(24-50),15 条把每维 LLM 调用 = 15×rounds 控住(三维×3 轮×15 ≈ 135 次/`--check`,~10-20 min,含 Clash 抖动可接受)。
- 三个 harness 的真实 import 名/签名以实现时核对为准(fixture 自测已 import 过它们,签名可查);orchestrator 只调其 `run_one_round`、读回它已算好的指标 dict,不碰内部。

### ③ 基线 JSON(git-committed)

`tests/data/eval_baseline.json`:
```json
{
  "meta": {"model": "deepseek-v4-pro", "updated_at": "2026-07-13T10:00:00Z", "rounds": 3, "max_items": 15},
  "evals": {
    "extract_f1":      {"median": 0.82, "threshold": 0.75, "corpus": "eval_p1_corpus[:15]"},
    "recall_accuracy": {"median": 0.70, "threshold": 0.60, "corpus": "longmemeval_sessions[:15]"},
    "tom_accuracy":    {"median": 0.65, "threshold": 0.50, "corpus": "tombench_first_order[:15]"}
  }
}
```
- `median` = `--update` 那次跑出的 N 轮中位数;`threshold` = 对应 harness 自带阈值(绝对地板)。
- **只在有意质量变更后 `--update`**(不是每次重写)——避免 LLM 噪声制造无意义 git diff。基线的 git 历史 = 质量趋势记录。

### ④ 回归判据 + 报告

对每个 eval_id,`--check` 判:
- **回归** ⟺ `current_median < baseline.median - tolerance`(相对退化,容差吸收噪声)**或** `current_median < baseline.threshold`(跌破绝对地板)。
- 报告(文本/markdown):逐维列 `baseline.median → current_median`、阈值、判定(`OK` / `⚠ REGRESSION: 相对退化 X` / `✗ BELOW THRESHOLD`);末尾总判定。
- 退出码:任一维回归 → 非零(便于 `--check` 当门用,虽非 CI)。基线文件缺失时 `--check` 提示先 `--update`。

### ⑤ LLM 噪声处理

- 每维 `--rounds`(默认 3)次,每指标取**中位数**(非均值,抗离群)。`eval_longmemeval`/`eval_fantom` 本就多轮,范式一致。
- 容差带(默认 5 分)吸收残余轮间抖动;真正的持续下滑(超容差或破阈值)才判回归。
- Clash TUN 黑洞([[clash-tun-owns-all-network-flakiness]])导致某轮整轮超时 → 该轮分数异常低会被中位数稀释;若多轮皆黑洞则 orchestrator 应能识别「疑似网络非质量」(如整轮 0 分/大量 transport_error)并提示重跑,而非误报质量回归。

## Testing

- **fixture 自测(进 pytest 门,零真 LLM)** `tests/python/test_eval_quality_baseline.py`:
  - `diff_against_baseline`:构造 current/baseline dict,断言相对退化(超容差)、破阈值、容差内不误报、指标缺失处理。
  - `render_report` + `has_regression`:断言报告文本含各维判定 + 总判定;回归时 `has_regression` 真。
  - 中位数/子集切片:`collect_scores` 的纯部分(中位数计算、first-N 切片)可注入 mock `run_one_round`(返回固定分数)单测,不触真 LLM。
  - 基线读写:`--update` 写出的 JSON 结构 + `--check` 读回 diff round-trip;基线缺失时的提示。
- **真 LLM 跑 = 手动验证(不进 CI/pytest 门)**:`python scripts/eval_quality_baseline.py --update` 建首个基线 → 记录三维中位数;再 `--check` 一次证 diff=0(同基线);(可选)故意改 belief_prompt 一版 `--check` 证能抓到回归。结果进 PR body。Clash 黑洞则换时刻重跑。
- **门**:`.venv/bin/python -m pytest tests/python` 绿(新 fixture 测试 + 零回归);无 C++/绑定改动 → 无需 configure_build。

## Out of Scope(重申)

新 eval 逻辑;dashboard 端点;真实摄入数据 / 端到端有用性 eval;CI 集成(真 LLM 不可靠);FANToM(无 corpus);commitment/perception 等第 4+ 维。
