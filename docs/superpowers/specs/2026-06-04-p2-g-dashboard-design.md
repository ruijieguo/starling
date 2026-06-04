# P2.g 可视化观测面（Dashboard）设计

**里程碑**：P2.g（P2 收尾追加里程碑，继 P2.e 应用接口层之后；见 [2026-05-31-p2-completion-scope.md](../plans/2026-05-31-p2-completion-scope.md)）
**日期**：2026-06-04
**状态**：设计已 user approved，待 writing-plans
**依赖**：P2.a–f 均已合并 main（HEAD b43b937，全绿 ctest 505 / pytest 505）；`starling.Memory` 门面（open/remember/recall/tick/render_working_set/close）、P2.e 的 3 个 C++ readers（Persona/CommonGround.read、CommitmentEngine.pending）、丰富 SQLite schema（statements / statement_edges / cognizers / cognizer_relations / commitments / replay_scheduler_state / reconsolidation_windows / bus_events 等）均已落地

---

## 0. 背景与目标

P2 = 「小规模应用」阶段。P2.e 已交付 `starling.Memory` 应用接口层，但全程**零 UI**——引擎的认知状态（Statement 图谱、Cognizer 社会图、Commitment 五态机、Replay/Reconsolidation 调度、ConflictProbe）只能靠脚本与测试观察。P2.g 补上一个**可视化观测面**：既给终端用户用记忆体（remember/recall、Working Set、承诺提醒），也给开发者调试内部状态。

**目标一句话**：用 TypeScript（SvelteKit）+ Python（FastAPI）建一个简洁有品位、支持远端访问、实时交互的 dashboard web 服务，覆盖四个面板 bundle（交互核心 / 认知检视 / 动力学·运维 / 总览·Eval），引擎逻辑全部经既有 C++/Python 走真路径，**不加 C++ 绑定、不加 migration**。

**本轮范围**：产出 spec + plan + roadmap 登记 P2.g 行。**是否执行（subagent-driven-development）另行决定**。

---

## 1. 范围与口径

**架构口径（user 选定）**：**FastAPI engine-API（Python，引擎唯一属主）+ SvelteKit 前端（TypeScript）+ WebSocket 实时**。命令经 `starling.Memory` 门面走真引擎；检视面板走**只读 SQL SELECT**（DB 即真相）。

**范围内（P2.g 交付，四 bundle 全交付）：**
- **后端**：`python/starling/dashboard/`（FastAPI app：command 路由 + 只读检视路由 + WebSocket + bearer-token 鉴权中间件）。
- **前端**：`dashboard/web/`（SvelteKit + Tailwind，左导航 + 卡片式面板 + 明暗主题 + 轻量内联 SVG 图谱）。
- **启动器**：`scripts/run_dashboard.py`。
- **面板**：A 交互核心（interact / working set / 承诺提醒）+ B 认知检视（statement explorer / cognizer 图 / commitment 五态机）+ C 动力学·运维（replay·reconsolidation / conflictprobe / 队列）+ D 总览 + Eval 快照。
- **测试**：pytest（FastAPI TestClient，离线确定性）+ vitest（组件单测）+ 1 条 Playwright e2e smoke。

**明确范围外（→P3 或后续）：**
- 多租户切换（P2.g 单 (agent, tenant) 配置；多租户 →P3）。
- 真实用户账户/登录会话（用共享令牌，不建完整鉴权系统）。
- 写路径侵入引擎（不改 `starling.Memory`、不加 C++ 绑定、不加 migration；检视只读 SQL）。
- 重型前端图库 / 复杂图布局算法（用克制的内联 SVG）。
- 规模化负载、SSR SEO 优化（dashboard 不需 SEO）。

---

## 2. 架构

```
[浏览器 / SvelteKit UI]
        │  REST（命令 + 检视查询）  +  WebSocket（实时推送）
        ▼
[FastAPI engine-API]   ← bearer-token 鉴权中间件 + 可配置 host/port + CORS 白名单
        │ 持有单个 starling.Memory（引擎唯一属主 / 单写者）
        ├─ 命令路由：remember / recall / tick / working_set → 经门面走真引擎
        └─ 检视路由：只读 SQL SELECT 丰富的表（独立只读连接，WAL 并发读）
        ▼
   C++ core + SQLite（单写者 / WAL；subscriber 用 SAVEPOINT，沿用既有不变）
```

**关键不变量**：
- **单写者**：FastAPI 进程是该 (agent, tenant) 库的唯一引擎属主；命令经门面，检视走只读连接，同进程无并发写冲突。
- **不绕过引擎**：任何状态变更（remember/recall/tick）都经 `starling.Memory`，不让 TS/HTTP 层直接写 SQLite。
- **零 C++ 改动**：检视面板的数据来自只读 SQL；命令复用既有门面 + P2.e 已绑定 readers → `ctest 505` 不动、无新 migration（最高仍 0021）。

---

## 3. 后端 FastAPI engine-API

**位置**：`python/starling/dashboard/`（`app.py` 工厂 `create_app(config)` + `routes/` + `auth.py` + `realtime.py` + `queries.py` 只读 SQL）。随包安装、可 pytest + TestClient 测。

**配置（env 注入，单 (agent,tenant)）**：`STARLING_DASH_DB`（库路径）、`STARLING_DASH_AGENT`、`STARLING_DASH_TENANT`、`STARLING_DASH_TOKEN`（鉴权令牌）、`STARLING_DASH_HOST`（默认 `127.0.0.1`）、`STARLING_DASH_PORT`、`STARLING_DASH_CORS_ORIGINS`；LLM/embedding 沿用 `OPENAI_*` 或离线 stub（`make_stub_llm` + StubEmbedding）。

**REST 端点（除 `/health` 外均需 `Authorization: Bearer <token>`）**：

| 类别 | 端点 | 数据来源 |
|---|---|---|
| 健康 | `GET /health` | 进程 + 版本，无需令牌 |
| 命令 | `POST /api/remember` `{text, holder?, observed_at?}` → 抽取出的 Statements | `Memory.remember` |
| 命令 | `POST /api/recall` `{query, perspective?, k?}` → 检索结果 | `Memory.recall` |
| 命令 | `POST /api/tick` `{now?}` → `TickStats` | `Memory.tick` |
| 命令 | `GET /api/working_set?interlocutor=&goal=&token_budget=` → ContextBlock 渲染 + sections | `Memory.render_working_set` |
| 检视 | `GET /api/overview` → 各表计数 + 承诺分态 + 队列深度 + 最近 tick | 只读 SQL |
| 检视 | `GET /api/statements?holder=&perspective=&predicate=&limit=&offset=` → 行 + edges | 只读 SQL（statements / statement_edges）|
| 检视 | `GET /api/cognizers` → 节点 + 关系 + presence | 只读 SQL（cognizers / cognizer_relations / cognizer_presence_log）|
| 检视 | `GET /api/commitments` → 行 + 五态 + 生命周期 | 只读 SQL（commitments / commitment_triggers / commitment_protection）或 `CommitmentEngine.pending` |
| 检视 | `GET /api/replay` → 调度状态 + 到期 + ledger + 再巩固窗口 | 只读 SQL（replay_scheduler_state / replay_ledger / reconsolidation_windows）|
| 检视 | `GET /api/conflicts` → CONFLICTS_WITH 边 + 冲突类型 | 只读 SQL（statement_edges + canonical_conflict_key）|
| 检视 | `GET /api/queues` → outbox 深度 / embedding 待办 / pipeline_run | 只读 SQL（outbox_sequence_counter / consumer_checkpoint / statement_vectors / pipeline_run）|
| 检视 | `GET /api/eval` → 渲染 `docs/eval/*.md`（C1/C2/C3/P1 快照） | 读 markdown |
| 实时 | `WS /ws` → 服务端推 `{type, payload}` | 见 §5 |

**错误口径**：缺/错令牌 → 401；缺参数 → 422（FastAPI 校验）；引擎异常 → 500 + 结构化 `{error}`，**绝不回显令牌/key**。

---

## 4. 前端 SvelteKit

**位置**：`dashboard/web/`（独立 Node 工程，`package.json` 锁版本、`.gitignore` 排除 `node_modules`/`build`）。

- **栈**：SvelteKit + Svelte 5 runes + Tailwind；TypeScript 全程；`fetch` 封装统一加 `Authorization` 头（token 来自用户输入 → `localStorage`）。
- **布局**：左侧导航（四 bundle）+ 顶栏（token 状态 / 明暗切换 / 目标 agent·tenant）+ 主区卡片式面板。
- **设计语言（简洁有品位）**：克制调色板、充裕留白、Inter/系统字体、明暗双主题；图谱（Cognizer/Statement 关系）用**轻量内联 SVG**，不上重型图库。
- **数据**：所有数据走 FastAPI（REST + WS）；前端不直连 SQLite、不内嵌任何密钥。
- **服务模型（主选）**：SvelteKit `adapter-node` 起 TS web 服务，**同源反代** `/api`、`/ws` 到 FastAPI——单源、免浏览器 CORS、令牌只在前端服务侧/用户侧流转。**备选**：纯静态构建 + 直连 FastAPI（此时启用 §6 的 CORS 白名单）。plan 以主选为准。

---

## 5. 实时（WebSocket）

- 单通道 `WS /ws`，鉴权同 REST（连接时校验令牌）。
- 服务端事件类型：`tick`（tick 产生的变化摘要）、`commitment_fired`（承诺触发/提醒）、`statement_added`（remember 抽取出新 Statement）、`recall`（一次检索完成）。
- 前端按事件类型增量刷新对应面板（总览计数、承诺提醒、statement explorer 等），不整页重载。
- 事件源：命令路由在引擎操作完成后向连接广播；MVP 可先在命令完成后推送（轮询/订阅引擎事件流的深度集成可后续增强）。

---

## 6. 安全 / 远端访问

- **共享 bearer token**：`STARLING_DASH_TOKEN` env 注入，FastAPI 中间件恒定时间比较校验；**绝不入库 / log / 前端硬编码 / 提交**。
- **可配置绑定**：默认 `127.0.0.1`；显式设 `0.0.0.0` 且令牌非空才允许对外（启动时校验，否则拒启）。
- **CORS**：`STARLING_DASH_CORS_ORIGINS` 白名单。
- **TLS**：建议置于 TLS 反代后；README 写明远端部署姿态（反代 + 令牌）。

---

## 7. 面板规格（四 bundle）

- **A 交互核心**：① Interact——输入文本 `remember` → 展示抽取出的 Statement；输入 query `recall` → 结果列表。② Working Set——给定 interlocutor/goal/token_budget 渲染 ContextBlock。③ 承诺提醒——pending/ACTIVE 承诺 + ⚠ 提醒。
- **B 认知检视**：① Statement explorer——表/图（holder/perspective/predicate/object/nesting + edges），可按 holder/perspective/predicate 筛。② Cognizer 社会图——cognizers + relations + presence 的内联 SVG。③ Commitment 五态机——时间线（created→ACTIVE→FULFILLED/BROKEN/RENEGOTIATED/WITHDRAWN）。
- **C 动力学 / 运维**：① Replay/Reconsolidation——队列深度、到期项、窗口、ledger。② ConflictProbe——CONFLICTS_WITH 边 + 4 类冲突。③ 队列——outbox / embedding worker 待办 + pipeline_run。
- **D 总览 + Eval**：① Home overview——各表计数 + 健康一眼看（落地页）。② Eval 快照——渲染 `docs/eval/` 的 C1/C2/C3/P1 报告。

---

## 8. 仓库布局

```
python/starling/dashboard/          # FastAPI engine-API（随包，pytest 可测）
  __init__.py  app.py  auth.py  realtime.py  queries.py  config.py
  routes/  (commands.py  inspect.py  eval.py)
dashboard/web/                      # SvelteKit + Tailwind 前端（独立 Node 工程）
  src/  ... ; package.json ; .gitignore ; README 内联
scripts/run_dashboard.py           # 启动器（起 FastAPI；dev 下并行 vite）
dashboard/README.md                # 本地/远端跑法 + 安全姿态
tests/python/test_dashboard_*.py   # API/鉴权/检视/WS 用例（离线确定性）
```

---

## 9. 测试 + 红线

- **Python API（pytest + FastAPI TestClient，全离线确定性）**：用 `runtime._build_local_store_sqlite_runtime` + `relax_preflight_for_m0_3` 建临时库，raw sqlite3 顺序 seed（statements/cognizers/commitments）commit+close 后再起 app；`make_stub_llm` + StubEmbedding 驱动命令路由（无网络）。用例覆盖：命令路由（remember/recall/tick/working_set）、检视路由（overview/statements/cognizers/commitments/replay/conflicts/queues/eval）、鉴权（无/错令牌 401）、WebSocket（TestClient websocket 收到事件）。
- **SvelteKit**：vitest 组件单测（用 mock API JSON 渲染断言）；1 条 Playwright e2e smoke（token 登录 → 看总览 → remember → 实时刷新）。经 npm 跑。
- **红线回归**：`ctest 505` 不动（无 C++ 改）；pytest 增 dashboard API 用例全绿；M0.8 + M0.9 + P2.a–f 全绿；单一 `starling_tests`。
- **CI**：TS 工具链（node/npm）为新增；plan 决定接入方式（CI 增一步 npm test，或先文档化「本地必跑」）。

---

## 10. 实施约束（注入 writing-plans）

- 先建 worktree（`worktree-p2-g-dashboard`，从 main HEAD 切出）；所有命令在 worktree 跑（先 `source .venv/bin/activate`）。
- **无 C++ 改动、无 migration**（最高仍 0021）；不改 `starling.Memory` / 既有 readers；单一 `starling_tests`。
- 检视面板**只读 SQL**（独立只读连接）；命令**只经门面**；subscriber 写沿用 SAVEPOINT（既有，不引入）。
- **令牌 / API key env-only**：`STARLING_DASH_TOKEN` 与 `OPENAI_*` 绝不入库 / log / 前端 / 提交；报告/语料/前端构建产物里不含密钥。
- 新 TS 工具链：`dashboard/web/.gitignore` 排除 `node_modules`/`build`；`package.json` 锁主依赖版本。
- 每 commit 带 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；无 `--no-verify` / 无 `--amend`（hook 失败开新 commit）；plan 文件 untracked 直到 milestone close。
- 合并 main 需 dangerouslyDisableSandbox + 显式 consent；merge 前 `git -C <main> status` 清理 stray，再 `--no-ff` 合并。
- WAL：临时库顺序写（raw sqlite3 seed commit+close 再起引擎），沿用 P2.d/e/f 教训。

---

## 11. 构建顺序（plan 内部分阶段）

0. **脚手架**：SvelteKit + FastAPI 骨架 + token 鉴权中间件 + `/health` + 配置加载 + CI/测试接线。
1. **后端 API**：检视只读查询（overview/statements/cognizers/commitments/replay/conflicts/queues/eval）+ 命令路由（remember/recall/tick/working_set）+ pytest。
2. **D 总览 + Eval**：落地页（首个可见面）。
3. **A 交互核心**：interact / working set / 承诺提醒。
4. **B 认知检视**：statement explorer / cognizer 图 / commitment 五态机。
5. **C 动力学 / 运维**：replay·reconsolidation / conflictprobe / 队列。
6. **实时**：WebSocket 串起各面板增量刷新。
7. **加固**：鉴权 + 远端绑定校验 + CORS + 文档（README）+ e2e smoke。

---

## 12. 验收

- 四 bundle（A/B/C/D）均可在前端渲染、数据来自 FastAPI。
- 命令（remember/recall/tick/working_set）经真引擎；检视面板数据来自只读 SQL。
- 远端绑定（`0.0.0.0` + token）可用，无 token / 错 token → 401。
- WebSocket 实时推送生效（命令后对应面板增量刷新）。
- 离线测试全绿：pytest（API/鉴权/检视/WS）+ vitest + 1 条 e2e smoke；`ctest 505` 不动；M0.8/M0.9/P2.a–f 全绿。
- `dashboard/README.md` 写明本地/远端跑法 + 安全姿态；roadmap 登记 P2.g 行。
