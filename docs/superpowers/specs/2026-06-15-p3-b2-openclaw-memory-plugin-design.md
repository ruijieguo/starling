<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

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

# P3.b2 OpenClaw memory 插件 设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**日期:** 2026-06-15
**状态:** 设计批准,待写实现计划(writing-plans)
**前置:** P3.b1 存储抽象已收官(phase 1-6);本文是 P3.b 的第二部分。

## Goal

让 Starling 成为 OpenClaw 的 memory 插件——占据 `plugins.slots.memory = "starling"`,
用 Starling 的结构化认知记忆(statement/engram/working_set + 巩固/冲突)替代 OpenClaw
默认的 Markdown memory(memory-core)。插件是**瘦 TypeScript HTTP 客户端**,把 OpenClaw 的
memory 操作路由到 Starling dashboard FastAPI;不引入 NAPI/原生绑定,核心语义仍在 Starling
的 C++/Python 后端。开发在 docker 镜像内隔离进行,不污染本机已装的 OpenClaw。

## 背景(已探查的现状)

**OpenClaw memory 架构**(`/opt/homebrew/lib/node_modules/openclaw`,v2026.x):
- memory 默认是 agent workspace 的 **Markdown 文件**(`memory/YYYY-MM-DD.md` + `MEMORY.md`),
  文件是 source of truth。
- **`plugins.slots.memory`** 是 memory 插件槽:默认 `memory-core`,可设第三方插件 id(如
  `memory-lancedb`),或 `"none"` 禁用。**第三方插件可完全占据该槽**(docs/tools/plugin.md
  确认 memory-lancedb 即这样工作)。
- memory 插件向 agent 暴露 `memory_search`(语义检索)+ `memory_get`(读)两个工具,并提供
  pre-compaction 自动 flush(写 durable memory)。
- 插件用 `plugin-sdk`:`definePluginEntry({ id, name, register(api){...} })` + `openclaw.plugin.json`
  manifest(`{id, kind:"memory", configSchema, uiHints}`)。memory 插件专属注册 API(sdk-overview.md):
  `api.registerMemoryRuntime(runtime)`、`api.registerMemoryFlushPlan(resolver)`、
  `api.registerMemoryPromptSection(builder)`、`api.registerMemoryEmbeddingProvider(adapter)`;
  memory-lancedb 实测还用了 `registerTool`/`registerService`/`registerCli`。
- **直接模板:** `dist/extensions/memory-lancedb/`(完整包:`openclaw.plugin.json`/`index.js`/
  `lancedb-runtime.js`/`api.js`/`config.js`)——"long-term memory with **auto-recall/capture**",
  正是 Starling 要做的形态。

**Starling dashboard HTTP API**(`python/starling/dashboard/routes/`,FastAPI,#token 登录):
- `POST /api/remember`(body: `text`/`holder`/`interlocutor`/`now`)→ `{statement_ids}`
- `POST /api/recall`(body: `query`/`intent`/`target`/`k`/`perspective`/`mode`)→
  `{results:[{subject,predicate,object,score}]}`
- `GET /api/working_set`(query: `interlocutor`/`goal`/`token_budget`)→ working set
- `POST /api/tick`(后台维护:嵌入/巩固/投影/出箱)
- `GET /api/statements`(inspect,列表 + 过滤)
- 缺:删除/forget 端点(本设计新增)。

## 架构

```
┌─────────────────── OpenClaw 进程(docker: openclaw 容器) ──────────────────┐
│ agent ── memory_search/get tools ── plugins.slots.memory="starling"        │
│                                          │                                  │
│              StarlingMemoryPlugin(integrations/openclaw/, TypeScript)       │
│              ├─ register: MemoryRuntime 七能力 + FlushPlan                  │
│              ├─ client: 瘦 HTTP(fetch + #token + 写重试队列)               │
│              └─ config: dashboardUrl / token / tenant / autoCapture/Recall  │
└──────────────────────│ HTTP(host.docker.internal:<port>)───────────────────┘
                       ▼
┌─────────────── Starling(本机 host,非容器)────────────────────────────────┐
│ dashboard FastAPI ── MemoryCore(Python)── _core(C++ pybind,本机 _core.so) │
│ /api/remember /recall /working_set /tick /statements /forget(新增)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **拓扑说明(Task 7 实测修正):** Starling dashboard 跑在 **本机 host**,**不进容器**。
> Starling 引擎是 **macOS Mach-O(arm64)** `_core.so`,**无法在 Linux 容器加载**。所以
> dashboard 用本机 venv + 已编译 `_core.so`(`scripts/run_dashboard.py`,bind `0.0.0.0`),
> OpenClaw 跑隔离容器,经 `host.docker.internal:<port>` 连本机。compose 只含 `openclaw`
> 一个服务。详见 `integrations/openclaw/docker/README.md`。

插件是**适配层**:只做 OpenClaw 概念 ↔ Starling dashboard API 的翻译 + 传输 + 容错;
不重写认知记忆语义(对齐仓库 C++/Python 边界规则)。

## 组件

### 1. 插件包 `integrations/openclaw/`(repo 内,对照 memory-lancedb)
```
integrations/openclaw/
  openclaw.plugin.json      # {id:"starling", kind:"memory", configSchema, uiHints}
  package.json              # {openclaw:{extensions:["./dist/index.js"]}}, deps: openclaw(peer)
  tsconfig.json
  src/
    index.ts                # definePluginEntry + register(注册 memory 能力)
    runtime.ts              # StarlingMemoryRuntime:七能力实现,调 client
    client.ts               # StarlingClient:fetch dashboard + token + 写重试队列
    config.ts               # 解析/校验 config(dashboardUrl/token/tenant/...)
    map.ts                  # OpenClaw schema ↔ dashboard schema 纯函数映射
  test/                     # 单元测试(映射/client mock)
  docker/
    docker-compose.yml      # 仅 openclaw 服务(starling 跑本机 host)
    openclaw.Dockerfile     # 镜像:node + 装 openclaw + 镜像内 build 本插件
    entrypoint.sh           # 运行时按 env 渲染 openclaw.json(token 不入镜像)
    integration-test.sh     # host 端编排端到端测试
    roundtrip.mjs / downgrade.mjs  # 容器内 e2e 探针(写回环 / 降级)
    README.md               # 起停 + 集成测试步骤 + 实测观察
```

### 2. OpenClaw 注册机制(Task 3 探查已确定 → hybrid runtime 路线)
契约详见 [`2026-06-15-p3-b2-openclaw-contract.md`](2026-06-15-p3-b2-openclaw-contract.md)。占槽靠
manifest `kind:"memory"` + `definePluginEntry`;注册是 composite(非单一 god-object)。Starling 用
**hybrid runtime 路线**(用户 2026-06-15 裁定):`registerMemoryRuntime`(search/get/index 经
`MemorySearchManager`)作骨架 → 白盒复用 builtin memory_search/get 工具 + `memory` CLI + status +
embedding 接线;`registerTool`(memory_store/memory_forget)补 runtime 缺的写/删;
`registerMemoryFlushPlan` + `api.on` hooks 补 flush/auto-recall/auto-capture。**关键鸿沟:**
`MemorySearchManager` 是**文件/行读模型**(`search→{path,startLine,endLine,snippet,score}`、
`get=readFile(relPath)`,无 write/delete),Starling statement 须造稳定 synthetic path
`statement://<tenant>/<id>`(get/remove 反解依赖)。

### 3. 七能力 → OpenClaw 落点 + dashboard API(契约文档有确切签名)
| Starling 能力 | OpenClaw 落点 | dashboard API | 适配 |
|---|---|---|---|
| search | `MemorySearchManager.search()` | `POST /api/recall` | recall results → `MemorySearchResult[]`(path=`statement://<tenant>/<id>`、snippet=subj+pred+obj、score、citation=id) |
| get | `MemorySearchManager.readFile()` | `GET /api/statement/{id}` | relPath 反解 id → statement → `{text,path}`;ENOENT 降级 `{text:"",path}` |
| index | `MemorySearchManager.sync()` | `POST /api/tick` | 触发维护(或 no-op,Starling 后台自管) |
| recall(auto) | `api.on("before_agent_start")→{prependContext}` | `GET /api/working_set` | working_set.render → prependContext |
| capture | `registerTool(memory_store{text})` | `POST /api/remember` | text→remember,holder=agent |
| flush | `registerMemoryFlushPlan` + `api.on("before_compaction")` | `POST /api/remember` | hook 读 `sessionFile` transcript→remember |
| remove | `registerTool(memory_forget{memoryId})` | `POST /api/forget` | memoryId(=statement id)→forget(→forgotten) |

### 4. 数据映射:agent ↔ tenant/holder
- 插件 config 指定**一个 Starling tenant**(默认 `"openclaw"`)。
- OpenClaw **agent id → Starling `holder`/`interlocutor`** 维度。
- 效果:同 tenant 内记忆按 holder 区分,可跨 agent 检索(符合 Starling ToM/多 holder 设计);
  不为每 agent 开独立 tenant(避免多租户管理复杂 + 保留跨 holder 社会认知)。

### 5. 错误处理:读降级 + 写重试
- **读**(`search`/`recall`/`get`):dashboard 不可达 → 返回空结果 + 结构化 warn 日志,
  **不抛错**(OpenClaw agent 无记忆但不中断)。
- **写**(`capture`/`flush`/`remove`):失败 → 入**本地重试队列**(内存 + 可选磁盘持久化于
  插件数据目录),指数退避重试(上限可配),队列满或超重试上限才 warn。写**不静默丢失**。
- 超时/认证失败(401)单独分类(认证失败不重试,明确报配置错误)。

### 6. Starling 端改动(最小)
- **新增 `POST /api/forget`**:body `{ids, tenant}`,新增 `StatementStore.forget`(六态机
  →forgotten,幂等守卫 `state != 'forgotten'`)+ `memoryops::forget` facade + `memory_forget`
  绑定 + engine/core 转发。返回 forgotten 计数。纳入 `commands.py` router,#token 守卫,
  广播 `statement_forgotten` WS 事件。**注:** forgotten 立即移出检索(recall SQL 仅取
  `consolidated/archived`);向量物理清理 + 投影撤回由 tick 的 embedding_worker/projection
  最终一致跟进。
- **新增 `GET /api/statement/{id}`**:点读单条(新增 `queries.statement_by_id`,纯 read-only
  SQL,照 inspect.py/queries.py 模式),tenant 守卫,供 `get` 能力用。
- C++ 改动最小且守边界:forget 转换入核(`StatementStore.forget` + `memoryops::forget`
  facade),binding/engine/dashboard 仅转发;get 是纯 read-only SQL(queries 层,无 C++)。

### 7. docker 开发环境(Task 7 实测拓扑 — 已修正)
**关键约束:** Starling `_core.so` 是 **macOS Mach-O(arm64)**,**不能在 Linux 容器加载**。
故 dashboard 跑**本机 host**(非容器),OpenClaw 跑容器经 `host.docker.internal` 连本机。
`docker-compose.yml` 因此**只含 `openclaw` 一个服务**(无 `starling` 服务、无本机挂载)。

- **本机起 Starling**(repo 根):
  ```bash
  STARLING_DASH_HOST=0.0.0.0 .venv/bin/python scripts/run_dashboard.py --no-build
  ```
  必须 bind `0.0.0.0`(默认 `127.0.0.1` 容器够不着);token 在 `~/.starling/starling.json`。
- **openclaw 容器**(`openclaw.Dockerfile`,node:22-slim):`npm i -g openclaw@2026.6.6`(pin)
  + 镜像内 `tsc` build 本插件到 `/opt/starling-plugin`;`entrypoint.sh` 运行时按 env 渲染
  `openclaw.json`:`plugins.load.paths=["/opt/starling-plugin"]` + `plugins.slots.memory="starling"`
  + `plugins.entries.starling.config={dashboardUrl:"http://host.docker.internal:<port>", token, tenant}`。
  - **config 解析坑(2026.6.6 实测):** OpenClaw 用 **`OPENCLAW_CONFIG_PATH`** 定位 config;
    **切勿设 `OPENCLAW_HOME`**(它会被当作自身 base dir 追加 `/.openclaw`,把 config 静默移位)。
  - **token 绝不入镜像/git**:仅运行时经 env 注入,`entrypoint.sh` 写进容器临时 fs。
- compose `extra_hosts: ["host.docker.internal:host-gateway"]`,`environment` 透传
  `STARLING_TOKEN`(host env,缺则 fail-fast)/`STARLING_PORT`/`STARLING_TENANT`。
- 不污染本机:OpenClaw 只在容器内(系统 `/opt/homebrew/lib/node_modules/openclaw` 只读不碰);
  本机仅多跑一个 dashboard 进程(可用独立端口 + 临时 DB 隔离测试数据)。

### 8. 测试
- **单元**(`integrations/openclaw/test/`,vitest):`map.ts` 纯函数映射(OpenClaw↔dashboard
  schema)、`client.ts`(mock fetch:重试队列、读降级、401 分类)。
- **集成**(docker):`docker compose up` → 在 `openclaw` 容器跑 OpenClaw CLI/脚本发
  `capture`→验证 Starling 有新 statement;`search`→验证返回 Starling recall 结果;
  `auto-recall`→验证 working_set 注入。降级:`docker stop starling` → 读返回空、写入队列;
  恢复 starling → 队列 flush 成功。
- 不破坏:Starling 现有 ctest 587 / pytest(新增 `/forget` 端点配 pytest 钉测)。

## 非目标(YAGNI / 后续)
- 不做 OpenClaw embedding provider 适配(Starling 自带 embedder;`registerMemoryEmbeddingProvider`
  不用)。
- 不做 Markdown 双写/共存(Starling 完全接管 slot;OpenClaw Markdown memory 在该 agent 停用)。
- 不发布到 ClawHub/npm(本阶段 repo 内开发 + docker 集成测试;发布后续)。
- 不做硬删除(remove=forgotten=六态机逻辑删除终态,SQLite 行保留作审计;物理 purge /
  crypto_erasure 属 P3+)。
- crypto_erasure(P3.b1 Phase 7)已 defer P3+,与本插件无关。

## 实现顺序(交 writing-plans 细化)
1. 精确确认 OpenClaw memory 注册机制 + 能力签名(读 plugin-sdk types + memory-lancedb 源码),
   产出最小「hello memory」插件(注册成功 + 一个能力打通 dashboard)。
2. Starling 端 `StatementStore.forget`→`memoryops::forget`→`memory_forget` 绑定→
   `POST /api/forget` + `GET /api/statement/{id}`(`queries.statement_by_id`)+ ctest/pytest 钉测。
3. `map.ts` 七能力映射 + 单元测试。
4. `client.ts` HTTP + 读降级 + 写重试队列 + 单元测试。
5. `runtime.ts` 组装七能力 + config。
6. docker compose + Dockerfile + 集成测试。
7. README + 端到端验证(OpenClaw CLI → Starling)。
