# P3.b2 OpenClaw memory 插件 设计

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
└──────────────────────────────│ HTTP(docker network)────────────────────────┘
                               ▼
┌─────────────── Starling(docker: starling 容器,挂载本机 repo+venv)─────────┐
│ dashboard FastAPI ── MemoryCore(Python)── _core(C++ pybind,复用本机 _core.so)│
│ /api/remember /recall /working_set /tick /statements /forget(新增)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

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
    docker-compose.yml      # starling(挂载本机)+ openclaw(镜像内装)
    openclaw.Dockerfile     # 镜像:node + 装 openclaw + 装本插件
    README.md               # 起停 + 集成测试步骤
```

### 2. OpenClaw 注册机制(实现第一步精确确认)
设计层确定用 plugin-sdk 的 memory 插件 API 占据 `plugins.slots.memory`。具体是
`registerMemoryRuntime(runtime)`(单一 runtime 对象,七能力作其方法)还是
`registerTool`+`registerService`(像 memory-lancedb 拆成 memory_search/get 工具 +
auto-capture/recall 后台 service),**实现 Task 1 第一步**精确读
`dist/plugin-sdk/memory-core*.d.ts` + `dist/extensions/memory-lancedb/{index,lancedb-runtime,api}.js`
源码确定,并以 memory-lancedb 为可运行参照。本设计的七能力映射与此选择无关。

### 3. 七能力 → dashboard API 映射(完整对等)
| OpenClaw memory 能力 | dashboard API | 数据映射 / 备注 |
|---|---|---|
| `search(query, k)` | `POST /api/recall` | `{results}` → memory snippets(subject/predicate/object 拼文本 + score) |
| `recall`(auto-recall 注入) | `GET /api/working_set` | working_set → 注入上下文块 |
| `capture(text)` | `POST /api/remember` | `holder` = agent 映射;返回 statement_ids |
| `flush`(pre-compaction) | `POST /api/remember` | 把待存 durable memory 作 remember 写入 |
| `get(id)` | **新增 `GET /api/statement/{id}`** | 点读单条(薄包已有 `MetaStore.get_statement`)+ tenant 守卫 |
| `index` | no-op(Starling 自管) | `tick_interval_s` 后台已周期嵌入/巩固/投影;agent 不强制触发 |
| `remove(id)` | **新增 `POST /api/forget`** | **archive**(六态机 archived 态,可恢复),非硬删除 |

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
- **新增 `POST /api/forget`**:body `{id, tenant}`(或 `{ids}`),复用 P3.b1 phase 2
  `StatementStore.archive`(六态机合法转换到 archived,带守卫),返回 archived 计数。
  纳入 dashboard `commands.py` router,#token 守卫,广播 `statement_archived` WS 事件。
- **新增 `GET /api/statement/{id}`**:点读单条(薄包已有 `MetaStore.get_statement`,
  tenant 守卫),供 `get` 能力用。
- 不改 C++ 核心(archive/get 语义已在 store 层;仅加 HTTP 端点转发,守 C++/Python 边界)。

### 7. docker 开发环境
- `docker-compose.yml` 两服务:
  - `starling`:基础 Python 镜像,**挂载本机 starling repo(只读)+ venv**,启动
    `dashboard serve`(复用本机已 build 的 `_core.so`,免镜像内编译 C++);暴露 dashboard 端口。
  - `openclaw`:`openclaw.Dockerfile` 基于 node 镜像,`npm i -g openclaw` + 装本插件,
    配 `plugins.slots.memory="starling"` + `dashboardUrl=http://starling:<port>` + token/tenant。
  - docker network 连;`openclaw depends_on starling`。
- 不污染本机:OpenClaw 只在 `openclaw` 容器内;本机 starling repo 只读挂载(非污染源)。

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
- 不做硬删除(remove=archive,可恢复)。
- crypto_erasure(P3.b1 Phase 7)已 defer P3+,与本插件无关。

## 实现顺序(交 writing-plans 细化)
1. 精确确认 OpenClaw memory 注册机制 + 能力签名(读 plugin-sdk types + memory-lancedb 源码),
   产出最小「hello memory」插件(注册成功 + 一个能力打通 dashboard)。
2. Starling 端 `POST /api/forget`(+ 可选 `/statement/{id}`)+ pytest 钉测。
3. `map.ts` 七能力映射 + 单元测试。
4. `client.ts` HTTP + 读降级 + 写重试队列 + 单元测试。
5. `runtime.ts` 组装七能力 + config。
6. docker compose + Dockerfile + 集成测试。
7. README + 端到端验证(OpenClaw CLI → Starling)。
