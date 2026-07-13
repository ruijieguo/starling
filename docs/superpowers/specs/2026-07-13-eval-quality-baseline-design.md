# 质量回归基线(dogfood 子项 C)— Design Spec

**Date:** 2026-07-13
**Slice:** 把既有成熟 benchmark eval harness 从「手动跑一次」变成「可重复的质量基线 + 回归信号」——让 prompt/gist/extractor 改动造成的质量退化被抓到。dogfood 弧线第三步(A 摄入 PR #52 / B 信号 PR #53 / 方案2 出锁 PR #54 之后)。

## Problem / Context

Starling 有一套**成熟的 benchmark eval**(`scripts/eval_*.py` + `tests/data/`):抽取 F1(`eval_p1_extractor`)、长期记忆多选准确率(`eval_longmemeval`)、ToM 准确率(`eval_tom2_starling`/`eval_tom_bench`、`eval_tombench_full`、`eval_fantom` 等)。每个都是「合成 corpus + ground-truth + 阈值 + 报告」的完整 harness。

**但真正带 LLM 的质量 eval 只手动跑**(`test_eval_*_harness.py` 全是 fixture-mode 自测,验 harness 代码、零真 LLM)。⇒ **质量没有连续信号**:一次 prompt 改、gist v2 default-flip、extractor 调整,若悄悄让抽取 F1 / ToM 准确率 / 召回率退化,没人会发现(手动 eval 不常跑、不 gated)。

**为何不评真实摄入数据**:真实摄入数据稀疏(52 statements)且无 ground truth,LLM-judge 信号噪。既有 benchmark corpus 有 ground truth、成熟可靠——**复用它们做连续基线**杠杆最大、避开稀疏数据问题(用户裁定 A)。

## Goal / Non-Goals

**Goal:** 一个 orchestrator,**复用**既有 harness 的打分函数,在**全量小 corpus** 上真 LLM 跑、取 N 轮中位数,写/diff 一个 git-committed 基线 JSON,判回归。让质量退化在改动前后一跑就现形。

**范围裁定(plan-eng-review codex 12 findings 后收窄):首 slice = 2 维(extract F1 + ToM accuracy)。** recall(longmemeval)拿掉作 follow-up——codex 核实其 real-mode 基本坏:chat `max_tokens=512` 用 reasoning 模型会截断崩(#7)、env 处理不安全(#8)、且计划把「每 subset >0.55」塌成加权 overall 毁了验收规则(#2),加上从未真跑过 + 每 record 建整条重 pipeline。先做 extract+ToM(都是干净 base_url HTTP + 可工作 run_one_round);recall 等 longmemeval real-mode 修好再加。

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

| eval_id | harness(import,不重写) | corpus(**全量**,非 first-N) | 指标 |
|---|---|---|---|
| `extract` | `eval_p1_extractor.run_one_round(corpus, base_url, api_key, model)` + `P1_THRESHOLDS` | `tests/data/eval_p1_corpus.jsonl`(50 全量) | 5 个 per-field F1 |
| `tom` | `eval_tom_bench.run_one_round(corpus, *, fixture_mode, base_url, api_key, model, abilities)` + `ACCURACY_THRESHOLD`=0.55 | `tests/data/eval_tom_bench/first_order.jsonl`(24 全量,4 ability 各 6) | accuracy |
| ~~recall~~ | ~~eval_longmemeval~~ | follow-up(见范围裁定) | — |

- **用全量小 corpus,不用 first-N 子集**(codex #3:`corpus[:15]` 漏掉整个 ability、偏 subset,非代表)。corpus 本就小(extract 50 / ToM 24 balanced),全量跑 = 每维 corpus×rounds(2 维×3 轮 ≈ (50+24)×3=222 次/`--check`,~15-30 min 手动可接受)。可选 `--max-items` 默认 None=全量;若限量,基线元数据记 corpus 内容 hash 供 `--check` 比对(#10)。
- orchestrator 只调 `run_one_round`、读回指标 dict,不碰内部;签名已核实(extract→dict[field,f1]、tom→float)。

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
- 报告(文本/markdown):逐维列 `baseline.median → current_median`、阈值、判定(`OK`/`REGRESSION`/`BELOW_THRESHOLD`/`ERRORED`/`INCOMPLETE`/`MISSING`)+ 近 0 附注(见 ⑤);末尾总判定。
- **基线完整性(codex #1/#12)**:`--update` 要求**所有配置维**(extract+tom)都成功采到分才写基线——任一维 None/INCOMPLETE 则**拒绝写、保留旧基线**、退出 2(不静默漏维)。`--check` 若基线缺某配置维 → 该维 `MISSING` verdict(而非静默 exit 0)。
- **配置可比性(codex #10)**:基线元数据记 model + rounds + max_items + 每维 corpus 内容 hash;`--check` 比对当前 args/corpus hash 与基线——model 或 corpus 内容不匹配 → 拒绝 diff(不可比)、提示 `--update`、退出 2。
- 退出码:全 OK=0;真回归(REGRESSION/BELOW_THRESHOLD)=1;无回归但有 ERRORED/INCOMPLETE/MISSING/配置不匹配=2(需重跑/重建)。基线缺失时 `--check` 提示先 `--update`。

### ⑤ LLM 噪声处理

- 每维 `--rounds`(默认 3)次,每指标取**中位数**(非均值,抗离群)。容差带(默认 5 分)吸收残余轮间抖动;超容差或破阈值才判回归。
- **min 成功轮数(codex #6)**:某维成功轮 < `--min-ok`(默认 2)→ 该维记 `INCOMPLETE`(不从 1 样本出判定)。
- **网络故障 vs 质量崩:诚实报不隐藏(codex #4/#5)**。根因:`eval_p1_extractor`/`eval_tom_bench` 的 `run_one_round` **内部吞** per-record 网络异常当答错(→低分,轮不抛),故 orchestrator 无法在分数层区分「网络全崩→0」与「质量全崩→0」。**不再用 `_flag_network` 把近 0 分藏成 ERRORED**(那会对真回归假阴性)——0/低分照实报 `BELOW_THRESHOLD`(退出 1),但当某维全指标近 0 时报告**附注**「⚠ 疑似网络黑洞,查 stderr 的 transport WARN;非质量则换时刻重跑」。人看报告 + stderr 判网络 vs 质量。抓回归优先,附注给提示。

## Testing

- **fixture 自测(进 pytest 门,零真 LLM)** `tests/python/test_eval_quality_baseline.py`:
  - `diff_against_baseline`:构造 current/baseline dict,断言相对退化(超容差)、破阈值、容差内不误报、指标缺失处理。
  - `render_report` + `has_regression`:断言报告文本含各维判定 + 总判定;回归时 `has_regression` 真。
  - 中位数/子集切片:`collect_scores` 的纯部分(中位数计算、first-N 切片)可注入 mock `run_one_round`(返回固定分数)单测,不触真 LLM。
  - 基线读写:`--update` 写出的 JSON 结构 + `--check` 读回 diff round-trip;基线缺失时的提示。
- **真 LLM 跑 = 手动验证(不进 CI/pytest 门)**:`python scripts/eval_quality_baseline.py --update` 建首个基线 → 记录三维中位数;再 `--check` 一次证 diff=0(同基线);(可选)故意改 belief_prompt 一版 `--check` 证能抓到回归。结果进 PR body。Clash 黑洞则换时刻重跑。
- **门**:`.venv/bin/python -m pytest tests/python` 绿(新 fixture 测试 + 零回归);无 C++/绑定改动 → 无需 configure_build。

## Out of Scope(重申)

- **recall(longmemeval)维 = follow-up**:先修 longmemeval real-mode(codex #7 chat 512→32768、#8 env 异常安全 + DASHSCOPE 校验、#2 per-subset 阈值不塌 overall),再作为第 3 维加进基线。本 slice 只 extract+ToM。
- 新 eval 逻辑;dashboard 端点;真实摄入数据 / 端到端有用性 eval;CI 集成(真 LLM 不可靠);FANToM(无 corpus);commitment/perception 等第 4+ 维。
