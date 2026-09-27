<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

> **Dashboard 样例契约补记（2026-09-27）**：离线样例通过真实 C++ 链路写入，人物必须显式标注 `subject_kind=cognizer`，普通实体继续标注为 `entity`；不修改核心默认类型。主服务与样例服务使用独立数据库和摄入队列。设计及验收见[样例契约修复设计](2026-09-27-dashboard-demo-contract-design.md)和[全面回归报告](../../eval/2026-09-27-regression-dashboard.md)。

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

# P2.g 可视化观测面（Dashboard）设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

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
- 每 无 `--no-verify` / 无 `--amend`（hook 失败开新 commit）；plan 文件 untracked 直到 milestone close。
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
