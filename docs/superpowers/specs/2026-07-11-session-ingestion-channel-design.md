# 会话摄入通道(dogfood 子项 A)— Design Spec

**Date:** 2026-07-11
**Slice:** dogfood 驱动验证的第一子项——把真实 Claude Code 会话自动摄入 starling,产生真实记忆负载。
**Branch:** `feat/session-ingestion-channel`(off `main@e5ee177`)。

## Problem / Context

项目里一批决策卡在「gated-on-实测」死结:gist v2 是否 default-ON、P3.c 并发是否值得做、extraction 是否该出锁、query-embed 是否该缓存——全等真实使用信号,但 dashboard 至今空跑样例数据(43 statements 全是测试残留),没有真实负载产生信号。用户裁定下一阶段 = **真实 dogfood 驱动验证**,数据源 = **Claude Code AI 会话**(自给、真实、不依赖改习惯)。

整个 dogfood 阶段分三子项(依赖递进):**A 摄入通道**(本 spec)→ B 信号时间序列仪表化 → C 质量验证判据。A 是数据源头,B/C 都等它先攒数据。本 spec 只覆盖 A。

**关键查证(Claude Code hooks,2026-07-11 经 claude-code-guide 核官方文档):**
- **SessionEnd hook** 才是「会话彻底终止一次」触发(`Stop` 是 per-turn、一会话几十次,不用)。
- hook 执行**阻塞用户体验、无原生异步选项** → 摄入端点必须立即返回、后台消化。
- transcript `.jsonl`:`type:user`/`type:assistant`;assistant `message.content` 数组含 `thinking`/`text`/`tool_use`;tool_result 以 `type:user` + `<tool-result>` 包裹注入 → 过滤逻辑可精确实现。
- SessionStart hook 能注入 `additionalContext`(≤10k 字符)→ 下阶段「双向闭环」技术可达(本子项不做)。

## Goal / Non-Goals

**Goal:** SessionEnd 时自动把一段会话的**清洁对话**(剥离 thinking/工具/代码)喂进 starling,复用现有 `remember` 抽取,statements 落库可在 dashboard 检视。**纯 host 适配、零内核改动。**

**Non-Goals:**
- 召回**注入**新会话(SessionStart 双向闭环)—— dogfood 阶段 2。
- 信号时间序列仪表化 / 质量评估 harness —— 子项 B/C。
- 真正的「审过才可召回」前置门(`pending_review`)—— 见下「review 门校准」,列为 A 的 gated follow-up(碰内核)。
- extraction 出锁 / query-embed cache 等 gated 技术债 —— 本子项只**产生**其决策所需信号,不做优化。

## Design

### ① SessionEnd hook(`~/.claude/settings.json`)

全局(所有项目会话都摄入,用户裁定)。`command` 型 hook 调本地脚本,stdin 传 hook JSON。

```json
{ "hooks": { "SessionEnd": [ { "hooks": [
  { "type": "command",
    "command": "/Users/jaredguo-mini/.starling/bin/ingest-session.py",
    "timeout": 30 } ] } ] } }
```

〔SessionEnd 的精确输入字段(是否含 `transcript_path`)实现时按 hooks.md 再核一次;骨架假设含 `session_id`/`transcript_path`/`cwd`,与 Stop 同族。若 SessionEnd 不带 transcript_path,退化用 `~/.claude/projects/<slug>/<session_id>.jsonl` 按约定路径定位。〕

**自指趣点(可接受):** 全局摄入包含开发 starling 的会话本身;过滤掉代码/工具后剩的「用中文回复」「架构边界裁定」正是有价值的记忆,元 dogfood。

### ② 过滤脚本 `~/.starling/bin/ingest-session.py`(Claude-Code-specific)

- 读 `transcript_path` 的 `.jsonl`,逐行解析。
- **保留**:`type:user` 且 content 是纯字符串(非 `<tool-result>` 包裹)的文本;`type:assistant` 的 `message.content[]` 里 `type:text` 的块。
- **剔除**:`thinking` 块、`tool_use`、`tool_result`(user 里的 `<tool-result>`)、大代码块(```围栏内容 + 超长单行启发式)、命令 stdout。
- 输出:按时序拼成 `User: …\nAssistant: …` 交替的清洁对话文本。
- **分块**:长会话按 ~2000 token 切块(每块一条摄入 → 多次 extraction = 更多真实负载信号;避免单条 prompt 超限、抽取质量下降)。
- POST 每块给摄入端点。**同一脚本接受任意 transcript 路径参数** → 可批量喂 `~/.claude/projects/**/*.jsonl` 做历史 bootstrap 起量(与实时 hook 复用同一解析)。
- 脚本失败**绝不非零退出阻塞会话**(SessionEnd hook 若 block 会拖住退出):任何异常吞掉 + 记本地日志 `~/.starling/ingest.log`,exit 0。

### ③ 异步摄入端点 `POST /api/ingest`(dashboard,通用不耦合 Claude 格式)

- Body:`{ session_id, source, text, cwd, chunk_index }`(`source` 如 `"claude-code"`,`text` = 清洁对话块)。
- 幂等去重 by `(session_id, chunk_index)`:已入队/已处理的块直接 200 跳过(SessionEnd 理论一会话一次,但重跑/崩溃/bootstrap 重放要防重)。
- 入 **host 队列表 `ingest_queue`**(dashboard 侧 `CREATE TABLE IF NOT EXISTS`,**不进 C++ MigrationRunner**——它是摄入基础设施、非记忆 schema,零内核改动;持久化 → 崩溃不丢待摄入)→ **立即 200**。写经引擎门面走单写者。绝不在请求内跑 extraction。
- 挨着现有 `commands.py` 路由加(`/api/remember` 等同层),经引擎门面。

### ④ 后台摄入 worker(专用单线程)

- 复用 `DashboardEngine` 的后台线程模式(engine.py:565 `start_background_tick` 同款 `threading.Thread`+`Event` stop);新增一个 `start_ingest_worker()`,与 tick 线程并列。
- 串行消化 `ingest_queue`:每块调**现有 `engine.remember`**(`text`=清洁对话块,`holder="self"`,`interlocutor="claude-code:<cwd basename>"`,`now`=会话时刻)→ 处理完标记该块 done。
- 限流:一次一块、块间小睡(避免摄入风暴打满 LLM 配额 + 给 dashboard 交互让路)。
- remember 走 engine `_lock`(单写者)——摄入 extraction 会与 tick/converse 抢锁,**这是设计接受的**(见 §自闭环)。
- 失败(LLM 黑洞/超时)：重试有限次,超限标 `failed` + 记 `last_error`,不卡住队列头(dead-letter 语义,对齐现有 outbox 纪律)。

### ⑤ review 门校准(诚实反映勘察)

**勘察发现(2026-07-11):** recall 可见性过滤是 `review_status NOT IN ('rejected','pending_review')`(`basic_retriever.cpp:77` / `retrieval_planner.cpp:69` / `pattern_completor.cpp` / `semantic_retriever.cpp`)。remember 抽取产物默认落 `inferred_unreviewed`(`statement_validator.cpp:74` 正常路径),**此状态照样可被 recall**。真正「审过才可召回」的 `pending_review` 是 consolidation 专用(`sqlite_statement_store.cpp:165`),新摄入无落它的现成路径。

**决策(A-lite,measure-first):** 摄入 statements 落默认 `inferred_unreviewed`(即摄即可召回)。隐私门 = dashboard `/statements` **事后**人工检视 + `forget`。**真 `pending_review` 前置门列为 A 的 gated follow-up**(碰内核:新增「摄入源 → pending_review」落库路径,等实测发现摄入了不该召回的敏感内容再做)。这保持 A 纯 host、快启动。**取舍写明**:dogfood 是自己机器/自己会话,「即摄即可召回」的隐私风险可接受;敏感会话可事后 forget。

### ⑥ 一个漂亮的自闭环(信号,非负担)

摄入 worker 每块过 engine `_lock` 跑 extraction(实测单条 ~44s),会与 tick/converse 抢锁。这**恰好实测出「extraction 出锁」那个 gated 项该不该做**(#51 只修了 converse 生成段,remember 的 extraction 仍持锁)。dogfood 负载自然检验技术债,不预支——摄入卡顿的严重度 = extraction-出锁的优先级证据。

## 架构边界(硬规则自检)

hook 脚本 + 过滤 + 摄入端点 + `ingest_queue` + worker 全是 **host 应用适配**:把外部会话流转成对内核 `remember` 的调用序列;`remember`/extraction/幂等/`review_status`/recall 语义全在 C++,零改动。判据「换 Node dashboard 要重写吗」→ 要,但重写的是**喂养管道**不是记忆语义 → 偏 host。

**Borderline(用户裁定走 `/plan-eng-review`):** 摄入的**去重键、分块策略、review 落库策略、限流/dead-letter** 若被判定为「预算/裁剪策略」则属核心须归 C++;另 **host 在共享 `dashboard.db` 建 `ingest_queue` 表是否越界**(vs 独立 sqlite 文件)一并定谳。plan 阶段过一次 eng-review,再进实现。

## Testing

- **过滤脚本**(pytest 或脚本自带):喂一段真实结构的 `.jsonl`(含 thinking/tool_use/tool_result/代码块)→ 断言输出只含 user/assistant 对话文本、无被剔除内容;分块边界正确;异常输入 exit 0 不抛。
- **摄入端点**(tests/python):`POST /api/ingest` 立即 200;`(session_id, chunk_index)` 幂等去重(重放同块不重复入队);入 `ingest_queue`。
- **worker**(tests/python):FakeLLMAdapter 驱动,队列块被串行消化 → statements 落库、`interlocutor="claude-code:…"`、幂等 done 标记;失败块进 dead-letter 不卡队头。
- **端到端**(tests/python):样例 transcript → 脚本 → 端点 → worker → statements 出现在 `/api/statements`。
- **门**:全量 ctest(应无变化,零内核改动)+ `.venv/bin/python -m pytest tests/python` 绿。`ingest_queue` 是 host 建表(非 C++ migration)→ 无需重装 `_core`;若 eng-review 判定该表须归内核 migration 则另计。

## Out of Scope（重申）

召回注入新会话(阶段 2）；信号仪表化 / 质量 harness（子项 B/C）；真 `pending_review` 前置门（gated follow-up，碰内核）；extraction 出锁 / query-embed cache（本子项只产信号）。
