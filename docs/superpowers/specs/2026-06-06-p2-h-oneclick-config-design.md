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

# P2.h Dashboard 一键启动 + UI 配置 LLM 设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

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
