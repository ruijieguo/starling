# 信号时间序列仪表化(dogfood 子项 B)— Design Spec

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
