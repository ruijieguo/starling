<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 质量回归基线(dogfood 子项 C)— Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **JSON mode 请求实验（2026-09-12）**：C++ `OpenAIAdapter::Config::json_object_output` 默认关闭，仅约束抽取请求格式并保留响应原文，普通生成单独绕开。旧数组抽取使用默认实例；非法枚举继续严格拒绝。配置不代表服务器支持或 schema 保证，评测显式开启并归档参数；Python 仅绑定与编排。完整范围及待验证状态见 [中文优化设计](2026-09-12-socialmem-optimization-design.md)。

> **后续修复同步（2026-09-12）**：可空主题允许缺省或 null，无效类型统一在 C++ 预检；情绪校验不以“觉得/感觉”或整轮认知词直接拒绝。写入与检索共用原生契约。重复裁判一致率与有效分母单列，原严格门槛保持。实现范围及尚未完成的能力见 [中文优化设计](2026-09-12-socialmem-optimization-design.md)。

> **2026-09-11 契约补充**：P1 原标签保持，同时报告 base 与 combined，诊断与代表性结果分开。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


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


## 来源时间与独立扩展标签（2026-09-12）

按已批准优化范围执行 [中文来源话轮设计](2026-09-12-source-turn-evaluation-design.md)。C++ 生成并解析版本化话轮，保留原始消息时间与 UTF-8 来源位置，正文与元数据分开校验；Bus/检索重建 source_turn 防止篡改。Python 仅映射和统计，独立扩展标签不进入模型输入，不修改原 P1 金标。真实时间不推断为事件时间或 UTC；已完成 C++ 实现、全量测试、离线与真实核验；真实诊断为 verified / complete_with_errors，质量门槛未通过。普通正文冒号保留完整语义，直接写入/回读使用共享严格解析器拒绝嵌套重复键。详见 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 声明范围与覆盖诊断职责（2026-09-15）

后继 L/R0 先运行独立正负例和冻结原文派生解析，验收负例零新增误放及已确认句首误拒恢复。候选增长不等于质量提升；不生成新 F1，不替换旧基线。新核心与旧回执保持独立身份。

详见[声明范围定位与生成覆盖诊断设计](2026-09-15-claim-scope-localization-design.md)。
