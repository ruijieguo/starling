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

# 信号时间序列仪表化(dogfood 子项 B)— Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**Date:** 2026-07-12
**Slice:** dogfood 驱动验证的第二子项——把瞬时观测变成随时间累积的信号,让一批 gated-on-实测 决策有据可依。
**Branch:** `feat/metrics-timeseries`(off `main@50922af`)。

## Problem / Context

子项 A(会话摄入通道)已合并 `main@50922af`,SessionEnd hook 全局装机,真实记忆负载开始流入。但项目里一批决策仍卡在「gated-on-实测」:它们需要**随时间累积的趋势**,而现有观测全是**点态快照**(`/api/vitals` 的累计 extraction_cost、`/api/queues` 的点态 embedding_backlog、`/api/ingest_status`)。B 把这些变成可读的时序信号。

**关键洞察(勘察 2026-07-12):大部分原始时序数据已存在**,B 主要是**只读派生** + **一个需采样的指标**,不是从零建 metrics 平台(YAGNI)。

**B 服务的 gated 决策(用户裁定,3 选 2):**
- **P3.c 并发(#2)** — gated-on「pending-embed 队列是否随真实 ingest 增长」→ 需 embed 队列深度 over time。
- **gist v2 default-flip** — gated-on gist 质量 → 需 gist 质量**可观测代理**(非真 eval,那是子项 C)。
- (extraction 出锁/方案2 已被 A 实测答了[摄入持锁 37.8s],B 只做延迟趋势顺带确认,不重复。查询重复率/query-embed cache 未选:需新采且个人查询量稀疏。)

## Goal / Non-Goals

**Goal:** 3 个只读 API 端点,把 embed 队列深度、extraction/embed 延迟、gist 质量代理呈现为时间分桶序列,能回答上述 gated 问题。**纯 host 仪表化、零 C++ 内核改动。**

**Non-Goals:**
- 真 precision/recall gist eval(需人工标注基线)—— 子项 C。
- 查询重复率采集(query-embed cache)—— 未选,gated-on 更高查询量。
- dashboard 趋势图表前端 —— 用户裁定 API/JSON 足矣(measure-first;信号有用再美化)。
- 扩展 C++ HealthSampler / 通用 metrics 平台 —— 过度工程,违反 YAGNI。

## Design(host-only)

### ① 三族信号 + 来源

| 信号 | 服务 | 机制 | 源 |
|---|---|---|---|
| embed 队列深度 over time | P3.c 并发 | **采样** | tick 回调每 ~30s 采 `embedding_backlog` → `metrics.db` |
| extraction 延迟趋势(p50/p95/count 分桶) | 方案2 确认 | **派生**(只读) | `extraction_attempt`(`created_at`+`latency_ms`+tokens) |
| gist 质量代理:promotion funnel(candidates→abstracted/gated/failed)+ confidence 分布 + member 数/summary 长度分布 | gist v2 | **派生**(只读) | `replay_ledger`(`ops_applied_json`+`started_at`);`statements` where `provenance='consolidation_abstract'`(confidence/derived_from_json/summary) |

### ② 存储 —— host 自持 `~/.starling/metrics.db`

只为那**一个需采样的序列**建一个 host 独立 sqlite(不进 core 的 `dashboard.db`、不进 C++ MigrationRunner):
```sql
CREATE TABLE IF NOT EXISTS embed_depth_samples (
    ts        TEXT NOT NULL,   -- ISO8601 采样时刻
    backlog   INTEGER NOT NULL, -- 未 embed 的 statement 数(embedding_backlog)
    embedded  INTEGER NOT NULL  -- 已 embed 数(趋势对照)
);
CREATE INDEX IF NOT EXISTS idx_embed_depth_ts ON embed_depth_samples(ts);
```
**单写者**:仅采样器(后台 tick 线程)写 `metrics.db`——天然单写者(唯一写者);API 端点只读打开(`mode=ro`)。**与 core 的 `dashboard.db` 无任何共享写连接**(A 的教训:host 存储独立于 core,不涉单写者)。其余信号零新存储(只读派生)。

### ③ 采样器(host,复用后台 tick)

现有后台 tick 每 `tick_interval_s`(~30s)跑一次,`app.py` 已接 `on_tick(stats)` 回调(:59)。采样器挂在**同一 tick 节奏**:每 tick 读 `embedding_backlog`(复用 `queries.py` 的 `statement_vectors` 计数逻辑,只读)+ 追加一行 `{ts, backlog, embedded}` 到 `metrics.db`。低频、append-only、失败吞掉记日志不杀 tick(保活,对齐现有 tick 异常处理)。
- **落点选择(实现时定,二选一,均 host)**:(a) 扩 `engine` 加 `sample_embed_depth()` 由 tick 循环或 `_on_tick` 每轮调用;(b) 独立 host 采样函数由 lifespan 与 tick 并列启动。倾向 (a)——蹭现有 tick 节奏,零新线程。
- **retention**:append-only 会无限增长。加一个轻裁剪(保留最近 N 天/M 行,采样时顺带 `DELETE WHERE ts < cutoff`)——个人 dogfood 30 天足够,避免文件无限涨。

### ④ API(3 个只读端点,挨着 `inspect.py` 现有只读路由加)

- `GET /api/metrics/embed_depth?since=<iso>&bucket=<s>` → 读 `metrics.db`,时间分桶返回 `[{bucket_ts, backlog_avg/max, embedded}]`。
- `GET /api/metrics/latency?since=<iso>&bucket=<s>` → 派生 `extraction_attempt`:每桶 `count`、`p50_ms`、`p95_ms`、`total_tokens`(SQL 分桶聚合;p95 用近似或窗口)。
- `GET /api/metrics/gist_quality?since=<iso>` → 派生:(a) funnel = 按 `started_at` 桶聚合 `replay_ledger.ops_applied_json` 解出的 `gist_candidates/abstracted/gist_gated/gist_failed`(实现对真 gist 运行核实精确键名;当前 idle 样例见 `compress`/`gist_candidates`);(b) confidence 分布 = `consolidation_abstract` statements 按 confidence 分桶;(c) member 数 = `derived_from_json` 数组长度分布;summary 长度 = `consolidation_summary` 字符长度分布。
- 都经现有 `_cfg`/`open_ro` 只读模式;`since`/`bucket` 有合理默认(如 since=7d 前、bucket=3600s)。

### ⑤ 架构边界(硬规则自检)

全 **host 应用适配**:只读派生查询(dashboard 检视本就走只读 SQL)+ host 自持采样表 + host tick 回调。**零 C++ 内核改动**;不碰 C++ HealthSampler(它驱动健康门 READY/DEGRADED——观测趋势混进健康门是边界污染,且记忆警告其 wiring 风险);不动 `TickOutcome`(加 dict 字段=已知地雷,撞 `TickStats(**dict)`)。`metrics.db` 是 host 基础设施非记忆 schema、不进 MigrationRunner。判据「换 Node dashboard 要重写这些查询/采样器吗」→ 要,但重写的是**观测派生**不是记忆语义 → host。

### ⑥ Testing

- **采样器**:FakeLLM 驱动一次 tick(或直调 `sample_embed_depth`)→ `metrics.db` 出现一行 `{ts, backlog, embedded}`,值与 `queries.py` 的 backlog 一致;retention 裁剪删旧行。
- **latency 端点**:种子 `extraction_attempt` 若干行(不同 created_at/latency_ms)→ 断言分桶 count/p50/p95。
- **gist_quality 端点**:种子 `replay_ledger`(ops_applied_json 带 gist 计数)+ `consolidation_abstract` statements(不同 confidence/derived_from/summary)→ 断言 funnel 桶 + confidence/member/summary 分布。
- **embed_depth 端点**:种子 `metrics.db` 序列 → 断言分桶返回。
- **只读安全**:3 端点无 token → 401(经 require_token);读 `mode=ro` 不改库。
- **门**:全量 ctest(零内核改动应无变化)+ `.venv/bin/python -m pytest tests/python` 绿。`metrics.db` 是 host 建表、无 migration、无 `_core` 重装。

### ⑦ 成功判据

真实 ingest 攒够数据后,3 端点能回答 gated 问题:(1) `embed_depth` 序列是否随 ingest 负载**上升**(P3.c 并发该不该做);(2) `latency` 显示 extraction 是否是**主导成本**(确认方案2 优先级);(3) `gist_quality` 的 promotion 率/confidence 分布是否**够格** default-flip(gist v2)。**判据是「能读出趋势做决策」,不是某个阈值**——B 是仪表,不是决策本身。

## Out of Scope(重申)

真 gist eval(子项 C);查询重复率采集;dashboard 图表前端;C++ HealthSampler 扩展 / 通用 metrics 平台;gated 决策本身(B 只供信号,决策等信号读出后另议)。
