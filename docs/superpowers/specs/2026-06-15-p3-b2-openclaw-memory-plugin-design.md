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
