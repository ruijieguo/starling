# P2.h Dashboard 一键启动 + UI 配置 LLM 设计

**里程碑**：P2.h（P2 收尾追加，继 P2.g dashboard 之后）
**日期**：2026-06-06
**状态**：设计已 user approved，待 writing-plans
**依赖**：P2.g 已合并 main（HEAD 9b76683）——FastAPI engine-API（`python/starling/dashboard/`）+ SvelteKit 前端（`dashboard/web/`）+ WebSocket + bearer token + `starling.Memory` 门面均已落地

---

## 0. 背景与目标

P2.g dashboard 启动较繁琐：① 起两个进程（`run_dashboard.py` + `npm run dev`，两终端）；② 记一堆 env（`STARLING_DASH_*` + `OPENAI_*`）；③ **LLM 写死在 env**（命令路由 `_memory` 懒构建 `Memory.open(..., llm=make_openai_llm())`，`make_openai_llm` 从 `OpenAIAdapterConfig.from_env()` 读 `OPENAI_API_KEY`，启动前必须配好）。

**目标一句话**：让 dashboard **一键单进程启动**（无需两终端、无需记 env），LLM 与 embedder **在界面里后配置**（先把面板跑起来再填），所有配置收敛到**一个 gitignored + 0600 的 `starling.json`**，token **首次运行自动生成**（类 OpenClaw/Jupyter，启动打印登录链接），**不改 `starling.Memory`、零 C++、无 migration**。

**本轮范围**：产出 spec + plan + roadmap 登记 P2.h。是否执行另行决定。

---

## 1. 范围与口径

口径仍是「小规模应用」。

**范围内（P2.h 交付）：**
- 统一配置文件 `starling.json`（后端 + LLM + embedder + token 全收敛）。
- 一键单进程启动（FastAPI 同端口 serve 前端静态产物 + `/api` + `/ws`）。
- dashboard 自有可配置/可热切换引擎栈（`engine.py`，llm + embedder 都可配）。
- 设置页 `/settings`（配 LLM + embedder）+ 配置路由 + 状态灯。
- token 首次自动生成 + 登录 URL（`#token=` 片段）+ 前端自动登录。
- 未配 LLM 的降级（remember 409，其余照常）。

**明确范围外（→P3 或不做）：**
- token / db_path 进 UI 配置（db_path 用默认、自动建库；token 自动生成不手配）。
- 多用户 / 多租户配置；密钥加密落盘；打包 exe / docker；运行时热改 host/port（绑定期固定）。
- 改 `starling.Memory`（dashboard 自有引擎栈，Memory 保持不变）；改 C++ / 加 migration。

---

## 2. 统一配置 `starling.json`

**默认位置**：`~/.starling/starling.json`（家目录隔离，不在仓库内）。`STARLING_CONFIG` env / `--config` flag 可覆盖。目录首次创建 0700，文件 0600。

**Schema（含默认值）：**
```json
{
  "db_path": "~/.starling/dashboard.db",
  "agent": "self",
  "tenant": "default",
  "token": "<首次运行自动生成>",
  "host": "127.0.0.1",
  "port": 8787,
  "cors_origins": [],
  "llm":      { "model": "", "base_url": "", "api_key": "" },
  "embedder": { "model": "", "base_url": "", "api_key": "", "dim": 1024 }
}
```

**开箱即用**：文件不存在 → 用内置默认 + 生成 token + 写出文件；`db_path` 指向 `~/.starling/dashboard.db`，首次由 runtime 自动建库（schema 编译期内嵌）；`llm`/`embedder` 留空（未配，embedder 回退 stub 8 维）。

**加载优先级**：显式 env（`OPENAI_API_KEY` / `STARLING_DASH_*`）> `starling.json` > 内置默认。`config.py` 新增 `DashboardConfig.load(path=None)`：读默认→覆盖文件→覆盖 env→（无 token 则生成并回写）。保留 `from_env` 兼容旧跑法。

**安全（硬线）**：`token` 与 `llm/embedder.api_key` 持久化在此文件——**绝不进 git、绝不进 SQLite 记忆库、绝不进 log**。文件 0600、家目录隔离、`.gitignore` 补 `starling.json`。这是对 env-only 约束的安全调和（等同 `~/.aws/credentials` / `~/.netrc` 业界惯例：本地 0600 明文，不入版本库/库/log）。

---

## 3. 单进程一键启动

**前端构建形态切换**：SvelteKit `adapter-node` → **`adapter-static`**（SPA，`fallback: 'index.html'`，根 `+layout.ts` 加 `export const ssr = false; export const prerender = false;`）→ 产出纯静态 `dashboard/web/build`。运行时**不需要 node**（node 仅构建期）。dev 仍走原 `npm run dev`（vite proxy）。

**FastAPI 挂载**：
- `/api/*`、`/ws`：现有路由（最先匹配）。
- 静态资产（`/assets/*` 等）：`StaticFiles` serve `dashboard/web/build`。
- **SPA 深链兜底**：catch-all 路由——任何非 `/api`、非 `/ws`、非已存在静态资产的 GET 一律返回 `index.html`（否则硬刷新 `/settings`、`/eval` 会 404）。
- 静态壳（index.html/JS/CSS）**无鉴权公开**（无密钥）；数据面 `/api` + `/ws` 才需 token。

**启动器 `scripts/run_dashboard.py`（一键）**：
1. `DashboardConfig.load()`（含 token 自动生成 + 回写）。
2. 若 `dashboard/web/build` 缺失且本机有 node → 自动 `npm ci && npm run build`（首次，可 `--no-build` 跳过）；无 node 且无 build → 报错提示先构建。
3. `validate_bind()`（非 loopback 总有 token，因 token 恒生成；守护保留）。
4. **打印登录 URL**：`Dashboard ready → http://<host>:<port>/#token=<token>`。
5. `uvicorn.run(app, host, port)` —— 单端口。

---

## 4. dashboard 自有引擎栈 `engine.py`

**动机**：要 embedder 可配，必须控制写嵌入（EmbeddingWorker）与读召回（SemanticRetriever）用**同一可配 embedder**；而 `starling.Memory` 内部硬编码 `StubEmbeddingAdapter(8)` 且约定不改 → dashboard 自建引擎栈（镜像 Memory 薄逻辑），`starling.Memory` 不碰。

**`DashboardEngine`（`python/starling/dashboard/engine.py`）**：
- **构建一次（启动期）**：`relax_preflight_for_m0_3()` → `runtime._build_local_store_sqlite_runtime(Path(db_path))` → `rt.start()`；持有 `rt`、`rt.adapter`、`rt.adapter.connection()`、`SqliteBlobVectorIndex`。`db_path` 固定，**runtime/连接永不重建**（避免 WAL 双写者）。
- **可配 llm**（默认 None=未配）：**仅当 `llm.api_key` 非空（`key_set`）才构建** `OpenAIAdapter`（经 §4 env-swap 建）；否则 `engine.llm = None`（→ remember 409）。
- **可配 embedder**（默认 `StubEmbeddingAdapter(8)`）：**`embedder.api_key` 非空才**构建 `OpenAIEmbeddingAdapter`（env-swap 建，dim 来自配置），否则回退 stub 8 维；随之（重）建 `SemanticRetriever(rt.adapter, emb, idx)`、`PatternCompletor(rt.adapter, semantic)`、`EmbeddingWorker(rt.adapter, emb, idx)`。`PolicyEngine(rt.adapter)` 与 embedder 无关，建一次。
- **空配置即未配**：`load()` 读到的空字符串 model/base_url/api_key 视为未配置（`key_set=false`）。
- **命令方法**（镜像 `memory.py`，~120 行）：
  - `remember(text, holder, now)`：`for_user_input(...)` → `rt.bus.append_evidence(inp, None)` → `Extractor(conn, llm).run(...)`；**llm 为 None 时 raise**（路由转 409）。
  - `recall(query, perspective, k, mode)`：`semantic.vector_recall(SemanticRetrieverParams)` / `completor.complete(PatternCompletionParams)`。
  - `tick(now)`：`worker.tick_one_batch(now)` + `policy.tick(now)` → `{embedded,fired,broken,auto_withdrawn}`。
  - `working_set(interlocutor, goal, token_budget)`：Persona/CommonGround.read + recall + CommitmentEngine.pending（⚠ fired）+ affect → `working_set.assemble`。

**部分热切换（配置变更，不动 Memory、不重建连接）**：
- 改 **llm**：仅替换 `engine.llm`（下次 `Extractor(conn, llm)` 即用新值）。
- 改 **embedder**：重建 embedder + `semantic`/`completor`/`worker`（复用同一 `rt`/`conn`/`idx`），并**重嵌**（见 §5）。

**key 注入 = 瞬时 env-swap at build**（关键，因 `api_key` 非可写绑定字段、`from_env` 在构建时捕获 key，P2.f 已验证）：建 `OpenAIAdapter` / `OpenAIEmbeddingAdapter` 时，临时设 `os.environ["OPENAI_API_KEY"]`（+ `OPENAI_BASE_URL`）为该组件配置值 → `from_env()` 捕获 → 还原 `os.environ`。这样 chat 与 embedder 可用**不同 provider/key**。env-swap 在单进程 asyncio 下顺序执行、低风险。

---

## 5. 设置页 + 配置路由

**`routes/config.py`（新，需 token）：**
- `GET /api/config` → 返回非密钥配置（`llm.model/base_url`、`embedder.model/base_url/dim`、`agent/tenant/host/port`）+ `llm.key_set` / `embedder.key_set` 布尔（可选末 4 位提示）。**绝不回 token / 完整 key 字符**。
- `POST /api/config` `{llm?: {...}, embedder?: {...}}` → ① 合并进 `app.state.config`；② **写 `starling.json`（0600）**；③ 改 llm → `engine.set_llm(...)`（env-swap 建）；④ 改 embedder → `engine.rebuild_embedder(...)`（env-swap 建）+ **重嵌**（清 `statement_vectors` 该 tenant 行 → 下次 tick / 立即 `worker.tick_one_batch` 重跑，使旧向量不与新 embedder 维度/空间失配）；⑤ 返回更新后的 masked 配置。

**改 embedder 的向量失配处理**：旧向量（embedder A，dim 8/1024）与新查询（embedder B）余弦不可比 → 改 embedder 时清空 `statement_vectors`（该 tenant）并触发重嵌；UI 提示「已切换 embedder，正在重嵌已有记忆」。

**设置页 `/settings`（前端）+ 状态灯**：
- 表单：**LLM**（model / base_url / api_key 密码框）+ **embedder**（model / base_url / api_key / dim）。无 token、无 db_path。
- 顶栏状态灯：`LLM: 已配置 / 未配置`（读 `GET /api/config` 的 `llm.key_set`）。
- Save → `POST /api/config` → 刷新状态灯。

---

## 6. Token 生命周期（类 OpenClaw/Jupyter）

- **首次运行自动生成**：`secrets.token_urlsafe(24)`，无 token 时生成并回写 `starling.json`（0600）；后续复用。可选 `--rotate-token` 重生成。
- **登录 URL 用片段**：启动打印 `http://<host>:<port>/#token=<token>`。**用 `#` 片段而非 `?` query**——浏览器**不把 fragment 发给服务器** → token 永不进 uvicorn access log。
- **前端自动登录**：页面加载读 `location.hash` 的 `token` → 存 localStorage → `history.replaceState` 抹掉地址栏片段。手填 Token 框保留为 fallback。
- token 恒存在 → 无「loopback 裸奔」模式，绑 `0.0.0.0` 也总有 token。`auth.py` 从 `app.state.config.token` 读（统一真相源）。

---

## 7. 未配 LLM 的降级

- 未配 llm：总览 / 检视 / `recall` / `tick` / `working_set` 照常（走 embedder——未配则 stub 8 维离线）。
- `remember`（需抽取，llm=None）：路由返回 **409**（`{"error": "llm_not_configured", "hint": "configure LLM in /settings"}`）；前端引导去设置页。
- 配好 llm 后 `set_llm` 热切换，立即可 remember，无需重启。

---

## 8. 安全小结

- **所有密钥**（token + llm/embedder key）只在 `~/.starling/starling.json`（0600、家目录、`.gitignore`）+ 进程内存（os.environ 瞬时 + adapter 捕获）；**绝不进 git / SQLite 记忆库 / log**；`/api/config` 永不回密钥字符。
- token 经 `#` 片段传递（不进 access log）；`#` 片段加载后即从地址栏抹掉。
- WS Origin 校验（防 CSWSH，P2.g 已有）保留；静态壳公开、数据面 gated。
- `validate_bind` 守护保留（非 loopback 须有 token，因 token 恒生成故恒满足）。

---

## 9. 改动面 / 仓库布局

**后端（`python/starling/dashboard/`）**：
- `config.py` —— 加 `load()`（文件 + env + 默认 + token 自动生成回写）、写文件 helper（0600）。
- `engine.py`（新）—— `DashboardEngine`（可配 llm/embedder + 部分热切换 + env-swap build + 命令方法）。
- `routes/config.py`（新）—— `GET/POST /api/config`（masked + 持久化 + 应用 + 重嵌）。
- `routes/commands.py` —— `_memory` → 改用 `app.state.engine`；remember 未配 llm → 409。
- `auth.py` —— 从 `app.state.config.token` 动态读。
- `app.py` —— 挂 `StaticFiles` + SPA catch-all 兜底 + 装 `app.state.engine`。
- `scripts/run_dashboard.py` —— `load()` + 自动 build + 打印登录 URL + uvicorn。

**前端（`dashboard/web/`）**：`/settings` 页 + 顶栏状态灯 + `#token=` 自动登录（`src/lib/token.ts` 扩展）+ `adapter-static` 切换（`svelte.config.js` + 根 `+layout.ts` ssr=false）。

**其它**：`.gitignore` 补 `starling.json`、`dashboard/web/build`。**不改 `starling.Memory`、无 C++、无 migration（仍 0021）、单一 `starling_tests`**。

---

## 10. 测试 + 红线

- **pytest（离线确定性）**：① `config.load` 优先级（env > 文件 > 默认）+ 默认 + token 自动生成回写 + 文件 0600；② `GET /api/config` 不泄 token/key（只 masked + key_set）；③ `POST /api/config` 写文件 0600 + `set_llm` 热切换 + 改 embedder 重嵌 + 应用生效；④ 未配 llm `remember` → 409；⑤ `DashboardEngine` remember/recall/tick/working_set 离线（stub llm via FakeLLMAdapter + stub embedder）；⑥ token 经 `#` 不进 query（鉴权仍走 header）。
- **vitest**：设置页表单 + 状态灯 +（`#token=` 解析）。**Playwright e2e smoke** 更新为单端口。
- **红线**：`ctest 505` 不动（无 C++）；无新 migration；不改 `starling.Memory`；pytest 增 config/engine 用例全绿；密钥不入 git/log/库；M0.8 + M0.9 + P2.a–g 全绿。

---

## 11. 验收

- 一条 `python scripts/run_dashboard.py` 单进程起 dashboard，打印 `http://…/#token=…` 登录 URL；点开自动登录、无需手填 token、无需第二终端、无需记 env。
- 设置页能配 LLM + embedder；未配时检视/recall 可用、remember 提示先配；配好后热切换即可 remember。
- 改 embedder 触发重嵌、recall 与新 embedder 一致。
- 所有密钥只在 `~/.starling/starling.json`（0600）+ 进程内存；`.gitignore` 含 `starling.json`；`/api/config` 不泄密钥；token 不进 access log。
- 离线测试全绿；`ctest 505` 不动；无 migration；不改 `starling.Memory`。
- roadmap 登记 P2.h。
