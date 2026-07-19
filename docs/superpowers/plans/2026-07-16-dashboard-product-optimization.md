# Dashboard 产品优化方案（plan-design-review 定稿）

> **For agentic workers:** 这是 plan-design-review 的产出——一份按 4 个优化方向组织的实施方案。
> 执行前需用户确认。用 subagent-driven-development 或 executing-plans 逐任务实施。

**背景**：Starling dashboard 是类脑社会心智记忆中间件的**只读观测 + 溯源 + 配置面**（CLAUDE.md 硬规则：dashboard 禁持算法/状态机/管线编排，那些在 C++ 内核）。视觉系统（语义 token、翠绿品牌 + tint 三件套、暖中性三层、明暗无 FOUC）、IA（类脑记忆流 20 路由）、交互状态（空/载/错阶梯 + 丰富空态）**都已成熟，过至少一轮 design review**。

**核心诊断**：产品完成度 7/10。两层缺口——(A) **IA 层：三类数据未对齐 CLS 模型**：原始数据（Engram）无搜索/浏览入口（仅能从 statement 反向溯源瞥见），快记忆（海马 VOLATILE）vs 慢记忆（新皮层 CONSOLIDATED）在 /statements 里无切分（端点无 consolidation_state 过滤），working-set 错位在海马组下（它是检索/输出侧的跨脑区上下文组装，非海马存储）。(B) **呈现层：后端富数据 vs 前端拍平**——可解释检索轨迹、溯源血缘、社交动力学被压成通用表格 + 原始 key 网格。

> **用户审查补充（2026-07-16）**：原方案（方向一~四）聚焦「已有数据呈现得更好」，漏了 IA 层——整一类数据（Engram 原始数据）无入口 + 短/长记忆无切分 + working-set 归属错位。新增**方向零（IA 修正，最高优先）**先补这层，再谈呈现。

**评分（当前 → 目标）**：
| 维度 | 分 | 目标 |
|---|---|---|
| 视觉设计系统 | 9/10 | 保持 |
| **信息架构（三类数据对齐）** | **6/10** | 9（engram 入口 + 短/长切分 + working-set 归位） |
| 交互状态覆盖 | 8/10 | 9（错误处理统一） |
| **数据呈现质量** | **5/10** | 8 |
| **系统能力暴露** | **4/10** | 8 |
| **实时性** | **5/10** | 8 |
| 一致性债务 | 6/10 | 9 |

**约束（不可违反）**：
- dashboard 只读检视 + 配置，禁持核心语义（算法/预算裁剪/状态机/管线编排在 C++）。
- 复用既有设计词汇（语义 token、既有 UI primitives：Card/StatCard/DataTable/Badge/Drawer/EmptyState 等），不引新视觉体系。
- 复用既有数据 primitive `createQuery`（三态契约 + stale-response guard）与 WS 基建（`$lastWsEvent`）。
- 不改后端语义，只改前端呈现 + 接线既有后端端点。新后端端点仅在纯派生只读查询时才加。
- 中文标签（跟随既有 nav.ts 约定）。

---

## 方向零：IA 修正 —— 三类数据对齐 CLS 模型（6/10 → 9）——最高优先

Starling 的核心是 CLS（互补学习系统）：原始证据 → 海马快记忆 → 新皮层慢记忆。dashboard 现在这三类数据的可见性都有缺口。这层先补，后面的呈现优化才有正确的骨架。

### T0a：Engram 原始数据浏览/搜索页（填补整类数据缺口）
**现状**：engrams 表（verbatim 原始证据）**无专属端点、无前端页面**。全仓库只有 `provenance` 的 `_engrams_for()` 从某条 statement 反向溯源时才顺带查它（限 280 字符预览、privacy-gated）。用户无法问「我喂进去过哪些原文？这段证据还在吗？被合规擦除了吗？」
**优化**：
- 后端加只读派生端点 `GET /api/engrams`（列表 + 分页 + 按 source_kind/privacy_class/erased 状态过滤 + content_hash/source_item_id 搜索）和 `GET /api/engram/{id}`（单条 + privacy-gated 预览，复用 provenance 已有的 privacy 逻辑）。纯 SQL 只读，不碰核心语义。
- 前端新页 `/engrams`（原始数据），DataTable：id/source_kind/privacy_class/retention_mode/created_at/erased_at/refcount，drawer 显示 privacy-gated payload 预览 + 「哪些 statement 引用了它」反查（refcount 展开）。
- 展示列有充足元数据（0001+0003 迁移：source_kind/privacy_class/retention_mode/adapter_name/source_item_id/chunk_index/redacted_content/erased_at），有 `idx_engrams_content_hash` 索引支撑搜索。
**IA 归属**：nav 新增「原始数据 · 证据」组（排在总览之后、海马之前——它是记忆流的源头），或归入总览组。见 D4。
**Files**: `python/starling/dashboard/routes/inspect.py`（+2 端点）、`python/starling/dashboard/queries.py`（engrams 列表/单条查询）、`dashboard/web/src/routes/engrams/+page.svelte`（新）、`dashboard/web/src/lib/nav.ts`（新组/条目）、`dashboard/web/src/lib/api.ts`（类型）。
**约束**：纯只读派生查询（engram 是不可变证据），复用 provenance 的 privacy 抑制逻辑，不新增可写路径。

### T0b：海马短期记忆三态视角（statements 加 consolidation_state 过滤）
**现状**：`/api/statements` 端点签名 `holder/perspective/predicate/review_status/limit/offset`——**无 consolidation_state 参数**。前端表格显示 consolidation_state 列但不能按它筛。海马快记忆的三个状态（VOLATILE / REPLAYING_CONSOLIDATING / REPLAYING_RECONSOLIDATING）vs 新皮层慢记忆（CONSOLIDATED/ARCHIVED）这个 Starling 最核心的 CLS 分野在 dashboard 里看不到。
**优化**：
- 后端 `queries.statements` + 端点加 `consolidation_state` 过滤参数（WHERE 追加，纯 SQL）。
- 前端 /statements 加 consolidation_state 过滤器（既有 filter chip 模式）。海马组快捷视角=「短期记忆」= VOLATILE + REPLAYING_CONSOLIDATING + REPLAYING_RECONSOLIDATING 三态；新皮层组的长期视角由 T0d 的五子区细分承接。
- nav 的「短期记忆 · 海马」组条目深链 `/statements?consolidation_state=VOLATILE,...`，让 IA 分组名与实际过滤对齐（现在指向不分状态的 /statements）。working-set 移走后（T0c），海马组正由这个短期视角填充，不再空。
**Files**: `python/starling/dashboard/routes/inspect.py`、`python/starling/dashboard/queries.py`、`dashboard/web/src/routes/statements/+page.svelte`、`dashboard/web/src/lib/nav.ts`（海马组深链带过滤）。
**约束**：consolidation_state 值域以 C++ 枚举为准（VOLATILE/REPLAYING_CONSOLIDATING/REPLAYING_RECONSOLIDATING/CONSOLIDATED/ARCHIVED/FORGOTTEN），前端不硬编码语义、只传参。

### T0c：working-set 归位（移出海马组）
**现状**：nav.ts 把「工作集」放在「短期记忆 · 海马」组下。但 working-set 是**渲染记忆上下文供 LLM 使用**——检索/输出侧的跨脑区组装（7 block 里 interlocutor_persona 来自 ToM、common_ground 来自新皮层固化、pending_commitments 来自前额叶），不是海马存储的短期记忆。
**优化**：把「工作集」移出海马组。两个候选归属（见 D5）：(a) 归入「对话」组——它服务于 converse 的上下文组装；(b) 新建「检索 · 输出」概念组，和 recall/lens 归一类（检索侧产物）。海马组在 T0b 后由「短期记忆快捷视角」填充（深链到 VOLATILE statements），不再空。
**Files**: `dashboard/web/src/lib/nav.ts`（移动条目 + 可能新建组）。
**约束**：nav.ts 是导航单一源，只动分组归属，不改 working-set 页本身。

### T0d：新皮层五子区呈现（语义/程序/规范/画像/共识）

**现状**：新皮层（长期记忆）在文档里明确分五子区——Semantic（BELIEVES/KNOWS 语义）、Procedural（Skill 程序）、Norms（NORM_OUGHT/NORM_FORBID 规范）、Personae（画像 Container 视图）、CommonGround（共识 Container 视图）。但 dashboard 里长期记忆只是一个不分子区的 /statements，五子区看不见分野。Personae/CommonGround 甚至无专属视图（只在 working-set block 或 cognizer drawer 里零星出现）。
**优化**：
- Semantic/Procedural/Norms 是 Statement 子区，可用 modality 过滤区分（Semantic=BELIEVES/KNOWS、Norms=NORM_OUGHT/NORM_FORBID、Procedural=Skill 特化）。/statements 页加「子区」快捷视角（modality 组合过滤），或新皮层组 nav 条目分别深链 `/statements?modality=...`。
- Personae/CommonGround 是 Container 物化视图（非 Statement 源）——它们已有数据来源（persona_subscriber checkpoint、common_ground 表），但无专属只读页。评估加 `/personae`、`/common-ground` 两个只读检视页（P2，看是否值得；数据已在库）。
**Files**: `dashboard/web/src/lib/nav.ts`（新皮层组子区深链）、`dashboard/web/src/routes/statements/+page.svelte`（modality 子区视角）、（P2）`routes/personae`、`routes/common-ground` + 对应 `inspect.py`/`queries.py` 只读端点。
**约束**：五子区是文档权威分类；Semantic/Procedural/Norms 靠 modality 派生（不新增字段），Personae/CommonGround 复用既有 Container 表，纯只读。

### T0e：ToM 双维呈现（cognizer 类型 × 信念阶层）

**现状**：心智化（ToM）有两个正交子类维度——① CognizerKind（Self/Human/Agent/Group/Role/External，「谁」的子类）；② nesting_depth 信念阶层（一阶「我信 X」/ 二阶+「我以为你信 X」，嵌套 Statement 展平存储 + provenance=tom_inferred）。前端 /cognizers 只显扁平节点，/statements 无 nesting_depth 过滤——二阶心智（Starling 最独特的能力）完全看不见。
**优化**：
- /cognizers 图 + 表按 CognizerKind 分类（节点形状/颜色映射 kind，与 T3 的 affinity/power 边映射叠加）。
- /statements 加 nesting_depth 过滤 + subject_kind 过滤，加「信念阶层」快捷视角：一阶（depth=0）/ 二阶及以上（depth≥1，标 tom_inferred）。让「我以为你相信什么」这类二阶信念可筛可见。
**Files**: `python/starling/dashboard/routes/inspect.py`、`queries.py`（statements 加 nesting_depth/subject_kind 过滤）、`routes/statements/+page.svelte`（阶层视角）、`routes/cognizers/+page.svelte` + `Graph.svelte`（kind 分类，与 T3 合流）。
**约束**：nesting_depth/subject_kind/cognizer_kind 值域以 C++ 枚举为准，前端只传参不硬编码语义。与 T3（cognizer 社交图）同触 cognizers/Graph，实施时合并避免冲突。

### T0f：前额叶子类呈现（承诺六态 × 触发器四型）

**现状**：意图与承诺（前额叶）有两个子类维度——① Commitment 六态（created/ACTIVE/FULFILLED/BROKEN/RENEGOTIATED/WITHDRAWN，BROKEN≥3 自动 auto_withdrawn）；② Trigger 四型（TimeTrigger/EventTrigger/StateTrigger/CompoundTrigger）。/commitments 页已有六态 kanban（这块做得好），但 **Trigger 类型完全不可见**——commitment_triggers 表有 kind/status，前端只在 /commitments 底部平铺 triggers 列表不分型。
**优化**：
- /commitments 的 triggers 列表按 kind 分组/标签（TimeTrigger 显示到点时间、EventTrigger 显示订阅的 event_type、StateTrigger 显示扫描的字段谓词、CompoundTrigger 显示子节点树）。
- 六态 kanban 保持（已好），补 auto_withdrawn 的来由提示（BROKEN 累计 ≥3 触发）。
**Files**: `routes/commitments/+page.svelte`（triggers 按 kind 分型呈现）、必要时 `queries.py` 的 commitments 查询带出 trigger kind 明细。
**约束**：六态/触发器四型值域以 schema（0018/0019 迁移 + C++ 枚举）为准，纯只读呈现。

---

## 方向一：系统能力暴露（4/10 → 8）

后端有富数据，前端拍平了。三个金矿：

### T1：检索归因轨迹面板（plan_query receipt 可视化）
**现状**：`plan_query` 返回完整可解释检索轨迹（trace_id、sufficiency_status、逐语句 score_breakdown 六因子 base/recency/salience/activation/affect_consistency/temporal_penalty、candidate dropped 计数、degraded_paths、frontier_masked、stop_reason）。`/interact` 页的 intent-planned recall 已渲染了「归因 receipt」score-breakdown 表——**但埋在 interact 控制台里，且 plain `/api/recall` 塌成 `{id,subject,predicate,object,score}` 丢弃全部轨迹**。
**优化**：把 score_breakdown 六因子做成可复用组件 `ScoreBreakdown.svelte`（水平堆叠条，每因子一段 + 数值 tooltip），在 recall 结果里对每条命中可展开。degraded_paths / dropped 计数做成一个「检索健康」小结栏（本轮取回 N，因 review/state/time/evidence 各丢弃 M）。
**Files**: `dashboard/web/src/lib/components/ScoreBreakdown.svelte`（新）、`dashboard/web/src/routes/interact/+page.svelte`（复用组件替换内联表）。
**约束**：纯前端呈现既有 receipt 数据，不改 plan_query。

### T2：/lens 溯源提权（brain_map count + 概览入口）
**现状**：`/lens` 是完整溯源森林（原始 LLM 输出、失败 attempt、token/延迟、privacy-gated 证据预览、derived_from + supersedes 血缘），但 brain_map 里 `/lens` count:None（安静角落），概览页无入口。
**优化**：(a) statements 表 + drawer 里每条语句加「溯源」深链按钮 → `/lens?stmt={id}`（lens 已支持 `?stmt=` 深链）；(b) brain_map 给 /lens 一个有意义的 badge（如「可溯源语句数」或直接标「审计入口」而非空）。
**Files**: `dashboard/web/src/routes/statements/+page.svelte`（drawer 加深链按钮）、`dashboard/web/src/routes/brain/+page.svelte` 或 `routes/inspect.py` brain_map（lens badge）。

### T3：cognizer 社交图升级（affinity + power_asymmetry）
**现状**：后端 `cognizer_relations` 带 affinity + power_asymmetry，presence_log 带 channel。前端 `Graph.svelte` 是固定半径径向布局（R=140 CX=200 CY=170 max-w-lg），节点多必重叠，且未用 affinity/power 维度。
**优化**：(a) 边粗细/透明度映射 affinity，边样式或箭头映射 power_asymmetry（谁对谁的权力不对称）；(b) 节点 tooltip 显示 relation 详情。**布局重构（力导向/缩放平移）单列 T3b 作可选**——先做数据映射（低成本高价值），力导向布局成本高单独评估。
**Files**: `dashboard/web/src/lib/components/Graph.svelte`、`dashboard/web/src/routes/cognizers/+page.svelte`。

### T4（可选，评估后定）：生命周期 Sankey + 独立成本视图
- lifecycle occupancy + event funnel 结构适合 Sankey 流图（VOLATILE→CONSOLIDATED→ARCHIVED→FORGOTTEN），现状是堆叠比例条 + 列表。
- extraction cost（per-tenant/per-run token+延迟）埋在 /vitals 里，可提为独立「用量」视图。
**判断**：这俩是「锦上添花」，非缺口。列 P3，先不做，看前三个落地后是否还需要。

---

## 方向二：数据呈现质量（5/10 → 8）

原始 key 直接当 label 铺网格 = 看着像自动生成。

### T5：友好标签 + 策展呈现（overview / queues / replay）
**现状**：`/`（counts、queue_by_status）、`/queues`（dispatch、vectors_by_status）、`/replay`（scheduler）都 `Object.entries` 铺后端原始 key（如 `statement_edges`、原始 status 串）当 label。
**优化**：加一个 label 字典 `lib/labels.ts`（后端 key → 中文友好名 + 可选排序权重 + 可选 gloss），网格按策展顺序渲染而非 API 返回顺序。例：`statements`→「语句」、`statement_edges`→「关系边」、`bus_events`→「总线事件」。
**Files**: `dashboard/web/src/lib/labels.ts`（新）、`routes/+page.svelte`、`routes/queues/+page.svelte`、`routes/replay/+page.svelte`。

### T6：detail drawer 策展（statements / commitments）
**现状**：statements、commitments 的 drawer `Object.entries(detail)` 裸 dump DB 列名 dt/dd 列表，无层次。
**优化**：drawer 分区呈现——核心区（holder/subject/predicate/object/modality/polarity）、元数据区（confidence/salience/consolidation_state/review_status）、时间区（observed_at 等），用既有 Field/Badge/Chip 组件，DB 列名过 T5 的 label 字典。
**Files**: `routes/statements/+page.svelte`、`routes/commitments/+page.svelte`（复用 T5 的 labels.ts）。

### T7：概览实时 feed 结构化
**现状**：概览「最近活动」feed 是 `JSON.stringify(payload).slice(0,80)` 裸截断。
**优化**：按事件类型（tick / statement_added / commitment_fired / recall / forgotten）做结构化渲染——每类型一个图标 + 友好模板文案 + 关键字段（如 statement_added 显示 subject·predicate），而非裸 JSON。
**Files**: `routes/+page.svelte`（feed 渲染）、可复用 T5 labels。

---

## 方向三：实时性铺开（5/10 → 8）

WS 基建齐全，仅 4/20 页订阅。

### T8：活数据页接线 WS 刷新
**现状**：仅 overview/vitals/runtime-health/layout 订阅 `$lastWsEvent`。commitments、queues、conflicts、gists、statements、lifecycle 等在系统 tick/写入时不刷新，需手动 reload。
**优化**：既有模式很简单（`$effect` 里判 `e.type === 'tick' || 'statement_added'` 就 `q.refetch()`）。给这些活数据页加同款订阅。**按数据变化频率筛**——commitments（commitment_transition/fired）、queues（tick）、conflicts（statement_added）、statements（statement_added/forgotten）、lifecycle（tick）值得；eval（静态报告）、settings（配置）不需要。
**Files**: 上述各 `+page.svelte`（每页 +3~5 行 `$effect` 订阅）。
**约束**：只加订阅，不改 createQuery 契约；避免 refetch 风暴（tick 30s 一次，可接受）。

### T9（评估后定）：路由级 error boundary
**现状**：无 `+error.svelte`；layout 注释提过历史事故（undefined bind 白屏整页）。
**优化**：加 `routes/+error.svelte` 应用壳级 fallback（保住 sidebar + 显示错误 + 重试）。
**判断**：P2，防白屏值得，但独立于实时性，可单列。

---

## 方向四：一致性债务清理（6/10 → 9）

### T10：density 死代码——接线或删
**现状**：`lib/ui/density.ts`（Density 类型 + pageSizeFor）+ `app.css` `[data-density='compact']` 规则 + token 全在，但**无处触发**——无组件设 `data-density`、无 UI 控件、DataTable 硬编码 pageSize=12 未调 pageSizeFor。designed-but-unshipped。
**优化（已定 = 接线）**：header 加密度切换（挨着 ThemeToggle），DataTable 用 pageSizeFor（compact 25 / comfortable 12），容器设 data-density + 持久化 localStorage['starling_density']。数据密集的观测面板 compact 模式一屏看更多行。
**Files**: `+layout.svelte`（密度切换控件）、`DataTable.svelte`（调 pageSizeFor 替硬编码 12）、`density.ts`（已有，接线即可）。

### T11：nav 标签 vs 页标题漂移
**现状**：`/settings` nav 标签「设置」，页 header「模型 / Models」。
**优化（已定 = 页面改「设置」）**：settings 页 header 从「模型 / Models」改成「设置」，与 nav 组名「配置」一致（IA 位置是通用配置组，未来可能加非模型配置）。
**Files**: `routes/settings/+page.svelte`（页 header title）。

### T12：错误处理统一
**现状**：14 页用 createQuery 的 `EmptyState title="加载失败"` 阶梯；converse/interact/working-set/lens/settings 手搓，几个只 toast 无持久错误面（working-set 渲染失败静默停在空态，看着像「还没渲染」）。
**优化**：手搓页对齐 createQuery 阶梯，或至少加持久错误面（失败时明确显示「加载失败 + 原因 + 重试」而非静默）。working-set 优先（静默失败最误导）。
**Files**: `routes/working-set/+page.svelte`（优先）、`routes/lens/+page.svelte`、`routes/interact/+page.svelte`。

---

## 设计决策（已定 — plan-design-review 定稿）

**D1（检索轨迹放哪）→ 增强 /interact 现有 receipt**。不新增路由；把 score_breakdown 六因子抽成可复用 `ScoreBreakdown.svelte`，在 /interact 的 recall 结果里对每条命中可展开，并补 degraded_paths/dropped 的「检索健康」小结栏。（对应 T1）

**D2（cognizer 社交图）→ 升级为力导向图**。T3 做 affinity/power 数据映射的同时，Graph 布局从固定径向重构为力导向（消除节点重叠 + 支持缩放平移）。即 T3b 从「可选」提升为 T3 的一部分。（对应 T3/T3b）

**D3（实施顺序）→ 方向零(IA 修正) → 能力暴露 → 呈现质量 → 实时性 → 债务清理**。方向零最先：它填补「三类数据可发现性」的根本缺口（原始数据 engram 无入口、短/长记忆无切分、working-set 错位），是其余方向的 IA 地基。其后能力暴露是最大能力缺口。方向二内部有序：T5 的 `labels.ts` 是 T6/T7 的依赖，先做 T5。

**D4（engram 原始数据 IA 落点）→ 新建「原始数据 · 证据」组**。engram 是三类数据里缺失的「原始数据」类（未抽取前的 verbatim 原文 + retention/privacy/erased 状态），是记忆的证据源头，语义上先于海马/新皮层，故在 nav 里新建独立组置于「总览」之后、「对话」之前（记忆流的最上游）。（对应 T0a）

**D5（working-set 归属）→ 归入「对话」组**。工作集是检索/输出侧产物（把跨脑区记忆组装成 prompt 快照供 LLM），不属海马存储；它直接服务于 converse 的上下文渲染，故归「对话」组（与 /converse、/interact 同组）。从「短期记忆 · 海马」组移出后，该组只剩……见 T0c 说明。（对应 T0c）

**顺带落定**：
- **T10（density 死代码）→ 接线**（非删）。数据密集的观测面板从 compact 模式受益（一屏看更多行）；header 加密度切换（挨着 ThemeToggle）、DataTable 用 pageSizeFor、容器设 data-density + localStorage 持久化。
- **T11（settings 命名）→ 页面改「设置」**。IA 组名是「配置」，未来可能加非模型配置项，页面标题对齐 nav 的「设置」比反过来更前瞻。

---

## NOT in scope（有意不做）
- 视觉体系重做——已成熟，动它是破坏。
- 新增核心语义端点（算法/状态机）——违反 dashboard 只读边界。
- ~~Graph 力导向布局~~——D2 已决定纳入 T3（不再 defer）。
- 生命周期 Sankey + 独立成本视图（T4）——锦上添花非缺口，P3 缓做。
- gist funnel 补 gated/failed 阶段——后端限制（ops_applied_json 不持久化这俩），需 C++ 改，超出 dashboard 范围。
- latency metrics 租户隔离——后端 extraction_attempt 无 tenant_id 列，需 C++ schema 改。

## What already exists（复用，不重建）
- 设计词汇：语义 token 体系、UI primitives（Card/StatCard/DataTable/Graph/Badge/Chip/Drawer/EmptyState/Field/Select/ConfirmDialog…）。
- 数据 primitive：`createQuery`（三态 + stale guard）、WS `$lastWsEvent` store + 自动重连。
- IA：nav.ts 类脑记忆流分组（保持）。
- 溯源深链：/lens 已支持 `?stmt=`（T2 直接用）。
- interact 页已有 score-breakdown 表（T1 抽成组件复用）。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean | score: 7/10 → 8/10, 5 decisions；用户揪出 IA 真缺口（三类数据 + working-set 错位）→ 加方向零 |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **VERDICT:** DESIGN REVIEW CLEAR — dashboard 产品优化方案定稿。五方向 16 任务：方向零 IA 修正（T0a–T0f，最高优先）/ 能力暴露 4→8 / 呈现质量 5→8 / 实时性 5→8 / 债务 6→9。5 设计决策已定（D1 增强 /interact receipt、D2 力导向图、D3 方向零→能力→呈现→实时→债务、D4 新建「原始数据·证据」组、D5 working-set 归对话组）。用户审查中连揪三处领域缺口，均升级为方向零：(1) engram 整类原始数据无入口 → T0a；(2) 短/长记忆无 CLS 切分 → T0b；(3) working-set 误置海马组 → T0c；(4) 进一步按脑区子类细化 IA（海马三态 T0b / 新皮层五子区 T0d / ToM 类型×信念阶层 T0e / 前额叶承诺六态×触发器四型 T0f）——纸面审查漏的、领域知识才能发现的洞。活 UI 审查，非 ship-gate；实施前经用户确认。

NO UNRESOLVED DECISIONS
