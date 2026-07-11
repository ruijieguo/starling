# 会话摄入通道(dogfood 子项 A)— Design Spec

**Date:** 2026-07-11(v2 — spool 架构,经 plan-eng-review + codex outside voice 重构)
**Slice:** dogfood 驱动验证的第一子项——把真实 Claude Code 会话自动摄入 starling,产生真实记忆负载。
**Branch:** `feat/session-ingestion-channel`(off `main@e5ee177`)。

## Problem / Context

项目里一批决策卡在「gated-on-实测」死结:gist v2 default-flip、P3.c 并发、extraction 出锁、query-embed cache——全等真实使用信号,但 dashboard 至今空跑样例数据(43 statements 全是测试残留)。用户裁定下一阶段 = **真实 dogfood 驱动验证**,数据源 = **Claude Code AI 会话**。

dogfood 阶段分三子项:**A 摄入通道**(本 spec)→ B 信号时间序列仪表化 → C 质量验证判据。A 是数据源头。

**v1→v2 重构(2026-07-11 plan-eng-review + codex):** v1 用「SessionEnd hook 同步 POST 每块给 /api/ingest 端点 → SQLite 队列表 → worker 外套 engine 锁跑 remember」。codex 指出两个核心承诺被破:(1) hook 同步 POST N 块(4 慢块 > 30s hook timeout)阻塞会话退出;(2) dashboard 挂/黑洞时脚本 exit 0 静默丢失该段记忆;(3) worker 外套 `_lock` 让所有请求等满 44s extraction,而 `remember()` 自身已持锁——外层锁零正确性收益。**v2 改用 spool-file 架构**:hook 只写一个 job 文件立即退出,worker 从 spool 目录异步消费。根除阻塞、静默丢失、锁争用,且更简单(无端点、无 SQLite 队列表)。

**关键查证(Claude Code hooks,2026-07-11 经 claude-code-guide 核官方文档):**
- **SessionEnd hook** = 会话彻底终止一次触发(`Stop` 是 per-turn,不用)。
- hook 执行阻塞用户体验、无原生异步 → hook 必须做近零工作(只写文件)。
- transcript `.jsonl`:`type:user`/`type:assistant`;assistant `content[]` 含 `thinking`/`text`/`tool_use`;tool_result 以 `type:user`+`<tool-result>` 注入。
- SessionStart 能注入 `additionalContext`(≤10k)→ 下阶段双向闭环可达(本子项不做)。

## Goal / Non-Goals

**Goal:** SessionEnd 时把一段会话的**清洁对话**(剥离 thinking/工具/tool_result/代码围栏/超长行)经 spool 文件异步喂进 starling,复用现有 `remember` 抽取,statements 落库可 dashboard 检视。**纯 host 适配、零内核改动。**

**Non-Goals:**
- 召回**注入**新会话(SessionStart 双向闭环)—— dogfood 阶段 2。
- 信号时间序列仪表化 / 质量评估 harness —— 子项 B/C。
- 真「审过才可召回」前置门(`pending_review`)—— gated follow-up(碰内核),见 §⑤。
- extraction 出锁 / query-embed cache 等 gated 技术债 —— 本子项只**产生**其决策所需信号(埋点测锁等待时间),不做优化。

## Design(spool 架构)

```
SessionEnd hook ──写 job 文件──► ~/.starling/ingest-spool/<uuid>.json  (hook 近零工作,exit 0)
                                        │  {session_id, transcript_path, cwd, tenant, enqueued_at}
                                        ▼
        background ingest worker (dashboard 进程内, 独立于 tick)
          扫 spool → claim(rename .processing)→ 读 transcript
            → clean_turns(剥 thinking/tool_use/tool_result/代码围栏/超长行)
            → chunk(~2000 token)
            → 逐块 engine.remember(holder="self", interlocutor="claude-code:<proj>", tenant)  ← 不外套 _lock
          全成 → 移 done/(或删);永久错 → 移 failed/;瞬态错 → 留 spool(下轮重扫=自动重试)
```

### ① SessionEnd hook(`~/.claude/settings.json`)

全局(所有项目会话都摄入,用户裁定)。`command` 型调 `scripts/ingest_session.py`,stdin 传 hook JSON。脚本**只**解析 payload + 写一个 job 文件到 spool + `exit 0`——无 transcript 解析、无 token、无网络。近零延迟,永不阻塞会话退出。

〔SessionEnd 精确输入字段(是否含 `transcript_path`)在 Task 1 前置核实;若不含,job 文件记 `session_id`+`cwd`,worker 按 `~/.claude/projects/<slug>/<session_id>.jsonl` 约定路径定位。〕

**自指趣点(可接受):** 全局摄入包含开发 starling 的会话本身;过滤后剩「用中文回复」「架构边界裁定」正是有价值的记忆。

### ② 过滤(`clean_turns` + `chunk`,`scripts/ingest_session.py` 纯函数,worker 与 bootstrap 共用)

- `clean_turns(lines)`:逐行 jsonl → 保留 `type:user` 纯文本(非 `<tool-result>` 包裹)+ `type:assistant` 的 `text` 块;**剔除** thinking / tool_use / tool_result / **代码围栏(```…``` 块)/ 超长单行**(>N 字符启发式,剥命令 stdout 残留)。坏行跳过不抛。
- `chunk(turns, max_chars≈8000)`:拼 `User:/Assistant:`,按 ~2000 token 分块(不切碎单轮)。

### ③ spool 写入器 + bootstrap(`scripts/ingest_session.py` main)

- hook 模式:读 stdin JSON → 写 `~/.starling/ingest-spool/<uuid>.json` job → exit 0(任何异常 → 记 `~/.starling/ingest.log` + exit 0,绝不非零退出)。
- bootstrap 模式:`--bootstrap <transcript_path...>` 为历史会话批量写 job 文件(worker 同路径消费)。

### ④ 后台摄入 worker(dashboard 进程内,专用单线程)

- 复用 `start_background_tick` 的 `threading.Event`+daemon 线程范本;**独立于 `tick_interval_s`**(tick 关不等于摄入关)。
- 每轮:扫 `ingest-spool/*.json` → 逐个 **claim**(`rename` 到 `<uuid>.json.processing`,原子占用,防多消费者/重扫重复)→ 读 transcript → `clean_turns` → `chunk` → 逐块 `engine.remember(text, holder="self", interlocutor="claude-code:<cwd basename>", tenant=job.tenant)`。
- **锁纪律(codex 核心修正):worker 不外套 `engine._lock`**——`remember` 自身持锁写。摄入块之间其他请求(recall/tick/review)可插入,dashboard 保持可用。块间小睡限流。
- **结果处置**:全块成功 → job 移 `done/`(或删);**瞬态失败**(remember 抛 timeout/transport 类)→ 把 `.processing` rename 回 `.json` 留 spool,下轮重扫自动重试(对 Clash 黑洞友好);**永久失败**(parse/validation 类)→ 移 `failed/` + 写 `.error`。
- **崩溃恢复**:job 文件持久 = 崩溃不丢;重启时 `.processing` 残留视为未完成,重新处理(remember 幂等键 = source_prefix+payload hash,重抽不产重复 statement,只多一次 extraction 调用——可接受)。
- **关停时序(codex 修正)**:lifespan 关停顺序 = begin_drain(拒新写)→ **停 ingest worker** → stop core tick/drain。避免关停时正在跑的 ingest remember 被标 failed。

### ⑤ review 门校准(诚实,不变)

recall 可见性过滤 = `review_status NOT IN ('rejected','pending_review')`;remember 产物默认 `inferred_unreviewed`(可召回)。**A-lite**:摄入 statements 即摄即可召回,隐私靠 dashboard `/statements` 事后检视 + `forget`;真 `pending_review` 前置门 = gated follow-up(碰内核)。dogfood 是自己机器/会话,风险可接受。

### ⑥ 可观测(codex 修正:别让 spool 隐形)

worker 暴露 spool 状态计数供检视:`GET /api/ingest_status` → `{pending, processing, done, failed}`(读 spool 目录三个子目录 + 主目录文件数,只读、零 DB)。挨着现有检视路由。

### ⑦ 信号采集(dogfood 目的,替代 v1 的「制造争用」)

不再靠自造锁争用测 extraction 痛点(codex:坏测量)。改为**埋点**:worker 每块记 `remember` 前的**锁等待时间**(拿 `_lock` 耗时)+ extraction 耗时,累加供 §⑥ 或 B 子项读取。锁等待时间 = 「extraction 出锁」gated 项的干净证据(不退化 dashboard)。

## 架构边界(硬规则自检 + eng-review 定谳结果)

hook 脚本 + 过滤 + spool 写入/消费 + worker 全是 **host 应用适配**:把外部会话流转成对内核 `remember` 的调用序列;`remember`/extraction/幂等/`review_status`/recall 语义全在 C++,零改动。

**eng-review 定谳(2026-07-11):**
- **borderline #1(去重/分块/dead-letter 属核心?)→ 判 host。** spool 架构下这些几乎溶解:去重 = `remember` 自带幂等(核心);分块 = 传输适配(host);dead-letter = spool 目录机械(host)。无一是记忆语义。
- **borderline #2(队列放哪?)→ 判 spool 文件(不用 SQLite 表)。** 比 v1 的 ingest.db 更保守:无第二个 SQLite 写连接、无与 core `dashboard.db` 的任何耦合,job 文件即持久队列。彻底不涉及单写者。

## Testing

- **过滤纯函数**:喂含 thinking/tool_use/tool_result/**代码围栏/超长行**的样例 jsonl → 断言输出只含对话文本、代码/工具全剔除;分块边界;坏行跳过。
- **spool 写入器**:hook stdin JSON → job 文件写出且字段正确;异常输入 → exit 0 不抛;`--bootstrap` 写多 job。
- **worker**:FakeLLMAdapter → spool job 被消费 → statements 落库 + **断言 `interlocutor="claude-code:…"`(不只 provenance)** + job 移 `done/`;永久失败 → `failed/`;瞬态失败 → 留 spool 可重试;`.processing` 崩溃残留重启重处理;done 不重处理。
- **worker 不持外层锁**:慢 stub(`set_delay_ms`)消化一块期间,并发线程 `engine.tick` 在 <阈值 拿到锁完成(证明摄入不锁死 dashboard)。
- **可观测**:`GET /api/ingest_status` 返回四计数,与 spool 目录一致。
- **门**:全量 ctest(零内核改动应无变化)+ `.venv/bin/python -m pytest tests/python` 绿。spool 是文件系统,无 migration、无 `_core` 重装。

## Out of Scope(重申)

召回注入(阶段2);信号仪表化/质量 harness(子项 B/C);真 `pending_review` 前置门(gated,碰内核);extraction 出锁/query-embed cache(本子项只产信号)。
