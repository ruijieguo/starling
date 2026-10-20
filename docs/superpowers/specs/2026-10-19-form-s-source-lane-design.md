# 形态 S：带日期的原文通道进入生产召回（完整设计 v1，待 Codex 评审）

日期 2026-10-20。状态：**设计稿，未实现**。本稿由评测结果驱动（见 [召回带时间](2026-10-18-temporal-recall-rendering-design.md) 的 E2 / top-20 / E3 / D5），所有代码事实均已只读核实并标注 `file:line`。评审通过前不动 C++。

## 0. 结论先行

把左脑做成**一条独立的原文召回 lane**：原始话轮按 `source_documents` 存储、按**向量**检索、按 `[SOURCE] [日期] speaker: 文本` 渲染，与右脑语句行在 `RetrievalPlanner` 内融合。它复用现有写入/存储/授权原语，但**必须新增两条东西**：source 单元的向量索引，以及 `ContextPackLabel` 的 `SOURCE` 值。

不新建 `engram_chunks` 投影表（判读表已裁定，见 [双脑设计](2026-10-17-dual-brain-general-memory-design.md)）。

## 1. 为什么是这条路（证据摘要，不在本文重述实验细节）

| 事实 | 读数 |
|---|---|
| 真实检索下，带日期原文 vs 带日期三元组 | 84.1% vs 17.9%（+66.4pp）|
| 日期的边际贡献 | +29.2pp（k=20），k=6 时 +25.7pp |
| 生产 source 腿现有 BM25 vs 评测用的向量 | 55.4% vs 84.1%（**−29.2pp，判劣**）|
| BM25 证据召回@20 | 55.1%（向量 89.4%），34 道题零证据 |
| 抽取漏斗对个人事件的保留率 | 11.1% |

两条结论直接决定设计：**原文通道要进生产**；**它的检索必须是向量，不能是现有 BM25**。

## 2. 现状：生产召回有三条路径，只有两条经过 planner

（勘察结论，逐条核实）

| 入口 | 是否走 `RetrievalPlanner::run` + `render_line` | 位置 |
|---|---|---|
| `/api/converse`、`/ws/converse` | **是**（经 `converse_prepare`）| `engine.py:495-514` → `_memory_core.py:254-263` → `memory_ops.cpp:376`（planner 在 `:395`）|
| `/api/recall` **带 intent** | **是** | `commands.py:114-129` → `engine.py:598` → `_memory_core.py:220-241` → `bind_05_retrieval.cpp:379` → `retrieval_planner.cpp:86` |
| `/api/recall` 不带 intent | 否（直接 `vector_recall`）| `commands.py:130-137` → `_memory_core.py:196-218` |
| OpenClaw 的 recall / workingSet | 否 | `runtime.ts:123`、`index.ts:112-114` |

**设计决定 D4-a**：左脑 lane 只接在 `RetrievalPlanner` 内部（fetch → fuse → render），因此 converse、带 intent 的 recall、`Memory.query` 三条路径自动获得它。不带 intent 的 recall、OpenClaw 的 search、Working Set **本轮不接**——它们各自有独立的取数逻辑，接它们是另一件事，另立设计。这个取舍要写进交付说明，避免"左脑只在部分入口生效"被误读为缺陷。

## 3. 数据与索引

### 3.1 写入（已存在，不改）

`retain_source_turns(adapter, tenant_id, allowed_holders, turns_json, created_at, preserve_invalid_time=false)`（`source_retriever.cpp:1267`）：

- 按 speaker 分组，speaker 必须在 `allowed_holders` 内，否则抛错。
- 逐组合并 `claim_source_turn_payload`，经 `remember_prepare` 写入 Bus 与 engram（`retention_mode='audit_retain'`）。
- 同事务写 `source_documents(tenant_id, holder_id, engram_ref, registered_at)`。
- 每个 engram 的 `payload_inline` 是**换行分隔的 source unit JSON**，unit 字段：`speaker`、`text`、`session_id`、`turn_id`、`turn_index`、`observed_at`，解析时附 `clause_id`。

### 3.2 新增：source unit 向量

`VectorIndex` 目前硬绑 `statement_vectors`（`sqlite_blob_vector_index.cpp:27` 直接 `INSERT INTO statement_vectors`），`SearchScope` 只有 tenant / holder / perspective / visible_only（`vector_index.hpp:13-18`），**没有命名空间参数**。因此不复用 statement 索引，另建一张表（迁移 `0037_source_unit_vectors.sql`）：

```sql
CREATE TABLE source_unit_vectors (
  tenant_id   TEXT NOT NULL,
  engram_ref  TEXT NOT NULL,
  clause_id   TEXT NOT NULL,      -- unit 在 payload 内的稳定编号 (c0, c1, ...)
  holder_id   TEXT NOT NULL,      -- 归一后的 speaker
  index_vector BLOB,              -- 嵌入式向量
  raw_embedding BLOB,
  dim INTEGER NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL,           -- pending | embedded | failed
  embedded_at TEXT,
  PRIMARY KEY (tenant_id, engram_ref, clause_id)
);
CREATE INDEX idx_source_unit_vectors_status ON source_unit_vectors(status);
```

主键 `(tenant_id, engram_ref, clause_id)` 与 unit 的稳定身份一致：engram 内容幂等（`sha256(payload)` 前 16 hex），`clause_id` 在 `units()` 内按行序生成，因此重建可复现。

**为什么按 unit 而不是按 engram**：检索粒度、日期粒度、授权粒度都必须是话轮。engram 可含多说话人；按 engram 建向量会把它们混在一起，也拿不到逐话轮 `observed_at`。

### 3.3 新增：嵌入队列的 kind 分发

`EmbeddingWorker` 的待嵌入查询是 `statements LEFT JOIN statement_vectors`（`embedding_worker.cpp:218-221`），只认语句。P1 把它拆成按 kind 取数的泛型接口（`statement` 与 `source_unit` 各自的取数 SQL、渲染文本、向量表、健康计数），**source unit 不做 pattern separation**（那是语句侧的行为）。

嵌入走异步 worker，**不放在写后 Pump**：Pump 在写事务后内联执行，嵌入是网络 IO，放进去会拖慢每次写入。

健康指标：待嵌入积压、失败重试数、滞后秒数，进 `Vitals`。写入零 LLM 调用、每 unit 一次 embedding。

### 3.4 幂等与重建

- 同一 engram 幂等命中不重切、不重嵌。
- 重建：`source_unit_vectors` 从 `source_documents` + engram payload 全量重建，走既有 repair guard。
- 删除/擦除：engram 被擦除时级联删向量（`memory_ops.cpp:637` 的清空路径已有 `source_documents` 处理，向量表加入同一列表）。

## 4. 检索与融合（C++）

### 4.1 请求形状

沿用 `temporal_evidence` 的先例（`retrieval_planner.hpp:40`）：在 `PlannerQuery` 上加一个**默认关闭**的可选请求，而不是加一个必填 lane 枚举。

```cpp
struct SourceLaneRequest {
    int k = 10;                       // 默认 k=10（D6）
    std::size_t max_context_bytes = 8000;
    std::vector<std::string> allowed_holders;   // 显式授权，不复用租户全集
    bool render_time = true;          // 关闭则渲染原样，用于对照
};
std::optional<SourceLaneRequest> source_lane;   // 默认 nullopt = 现有行为逐字节不变
```

### 4.2 fetch

在 planner 的 fetch 步内（`retrieval_planner.cpp:220-337` 之后）增加一次 source 检索：

1. 用问题文本嵌入（与语句腿同一 embedder、同一维度）。
2. `search_topk` 于 `source_unit_vectors`，**授权过滤在 SQL 里下推**：`holder_id IN allowed_holders`，`tenant_id` 匹配，`status='embedded'`。
3. 取回 `(engram_ref, clause_id, holder_id, observed_at)`，再从 engram payload 解析 unit 正文与元数据。解析失败的行丢弃并计数（`source_unit_filtered`）。
4. **as-of 截断**：`observed_at <= as_of`；缺失时间的 unit **不进入候选**（`include_unknown_time` 默认 false，与现有 observer 语义一致）。
5. 逐 unit 去重（同一 engram 内 `clause_id` 唯一，跨 engram 按 `(session_id, turn_index, speaker, text)` 去重）。
6. 按分数排序后按字节预算截断。

### 4.3 fuse 与类型

`PlannerEntryOut` 只装 `StatementRow`（`retrieval_planner.hpp:43-47`），而 `emit()`（`:522`）、`record_claim_link()`（`:489`）以及 Python 侧的 `e.row.subject_id`（`engine.py:614`）都假定它是语句。**不改 `PlannerEntryOut`**，改为与它平行的 `std::vector<SourceEntry> source_entries`（字段：`engram_ref`、`clause_id`、`holder_id`、`observed_at`、`observed_precision`、`session_id`、`turn_index`、`text`、`score`）。

融合规则（P1 取最简，不引入学习权重）：
- 两路各自内部按分数排序；
- 输出顺序：先满足 `min_source_items`（若设置），其余按 `round-robin` 交替，语句优先；
- 共享一个总字节预算；先到先得，被截断的行计入 `budget_skipped`。

不引入 RRF：RRF 需要两路分数同分布，而向量 cosine 与语句侧的综合分（语义 + 结构 + 新近度）不可直接比。交替排布在评测里对应的是"两路都给模型看"，已足够；权重融合留给有实测依据的后续工作。

### 4.4 渲染

新增 `ContextPackLabel::SOURCE`（`context_pack.hpp:15` 目前 8 个值，无 SOURCE），Python 镜像同步（`bind_05_retrieval.cpp:274-282`）。**这是有意的破坏性改动**：加枚举值会让快照里的标签集合变化。缓解方式是标签只在 lane 开启时出现，关闭时字节不变。

渲染形态（D3 裁定）：

```
[SOURCE] [2023-05-27 Sat 00:34] user: <原文>
```

与评测臂 `- [日期] role: text` 的差异只有前缀标签与列表符；正文与日期格式完全一致。**保留 `[SOURCE]` 前缀**以满足"原文不混入 `[FACT]`"的不变量（双脑设计不变量 2）。

时间渲染规则（与既有"只渲染可信时间"一致）：
- `observed_at` 来源 `source_turn`（transcript 事件时间）→ 渲染。
- 来源 `ingest_clock` → **不渲染**（D2 裁定）；行仍出现，只是没有日期。
- 缺失 → `unknown_time`，候选阶段已被过滤，不会走到渲染。

### 4.5 abstain

abstain 步（`retrieval_planner.cpp:458-482`）当前只看语句命中（`ab.any_candidates = !cands.empty()`，`:458`）。P1 改为**source 命中同样算作有证据**：否则"只有原文能回答"的题会被判弃答——而这正是左脑要解决的题。

## 5. 写入侧：摄入点（D4 裁定）

唯一调用点：`python/starling/dashboard/engine.py:892`（摄入 worker 内 `for chunk in chunks: self.remember(...)`）。新增一次 `retain_source_turns` 调用。

需要同时改 `clean_turns`（`python/starling/dashboard/ingest_filter.py:23-52`）：它现在返回 `[(role, text)]`，要改为同时返回事件时间。实测 transcript 的 user/assistant 事件 **100% 带 `timestamp`**（ISO UTC），只是被丢掉了。

映射（D1 裁定）：
- `assistant` → speaker 与 holder 都是 `self`（与 `holder="self"`、converse 的 querier 一致）。
- `user` → speaker 与 holder 都是 `claude-code:{project}`（与 `interlocutor` 一致）。
- 两者都必须同时出现在 `allowed_holders` 里，因为 `retain_source_turns` 与检索都是精确匹配。

**没有时间戳的来源**（自由文本 `remember`、OpenClaw 写入）：`observed_at` 填摄入时刻，标为 `ingest_clock`，不渲染日期（D2 裁定）。原文可召回，只是不带时间锚。

**不做的事**：不新增 Pump 订阅者（理由见 D4）；不自动把 `append_evidence` 的所有 engram 都登记为 source（Dashboard 的块是 `User: …\nAssistant: …` 自由文本，不满足 `claim_source_turn_payload` 的逐话轮合同）。

## 6. 授权模型

沿用 `retain_source_turns` 的显式 `allowed_holders`，**不自动扩到租户全部**。

- 写入时 speaker ∉ `allowed_holders` → 抛错（现有行为）。
- 检索时 `holder_id ∈ allowed_holders` 在 SQL 内下推，发生在排序之前。
- converse 的默认授权集：`{self, 当前对话方}`（D1）。`self` 想不起别人说的话在对话上是反常的，但**不包含第三方**。
- 混合说话人 engram 必须有测试：同一 engram 内 A、B 两个 speaker 的 unit，对仅授权 A 的 querier 只返回 A 的 unit。

## 7. 开关与兼容性（三个独立开关，默认全关）

| 开关 | 位置 | 关闭时行为 |
|---|---|---|
| `source_lane` | `PlannerQuery.source_lane`（C++）+ `DashboardConfig` 键 + `MemoryCore` 读侧载体 | 不检索、不渲染，上下文逐字节不变 |
| `source_lane.render_time` | 同上 | 行出现但不带日期 |
| `current_date_in_prompt` | `converse_prepare` | 不加 `Current Date` 行 |

写入侧的时间来源修正（三元组路径）**不在本设计内**，它是独立项，会改变新写入数据的 `observed_at`，不可能字节兼容。

**兼容性验证**：固定行集上比对渲染字节（关闭时不变）；`test_context_pack.cpp` 等精确渲染断言在关闭时不变。

## 8. 与右脑的关系

- **不改**右脑三通道抽取、六态机、§0.1 吸收原则、Bus 单入口。
- 左脑是**只读 lane**：source unit 无状态、不参与六态机、不产生语句。
- 事实权威仍在 Statement 图；`[SOURCE]` 行不混入 `[FACT]`。
- 融合发生在 `RetrievalPlanner` 内，是检索语义，因此在 C++（C++/Python 边界裁定）。

## 9. 测试

| 类别 | 用例 |
|---|---|
| 单元 | unit 解析与 `clause_id` 稳定性；向量表重建可复现；授权下推（混合说话人）；as-of 截断；无时间 unit 被过滤 |
| 渲染 | `SOURCE` 标签字节；`render_time` 开关；`ingest_clock` 不渲染日期 |
| 融合 | 交替顺序；共享字节预算；abstain 计入 source 命中 |
| parity | 关闭开关时 planner 输出与现状逐字节相同（固定行集快照）|
| 端到端 | converse 带 source lane 的固定场景；OpenClaw 路径保持不接（明确断言）|

## 10. 验收与预算

- **守护基准**：SocialMemBench 0.7825 不得下降（该读数出自 `sources` 模式，不经新渲染；混合模式会调 `render_line`，故须固定行集比对）。
- **不劣化**：LoCoMo 全量六臂复跑，非时序类不得劣化（当前基线：日期渲染对非时序 +3.1pp）。
- **进攻**：LongMemEval 确认集上 `S_left − S_rag` 的预注册判据，按原双脑设计的分项口径。
- **预算**：LoCoMo 全量 + LongMemEval 子集约 3e7（沿用双脑设计的记账），另需 embedding 成本单列。

## 11. 风险与未决

1. **上下文体积**：S1 中位 14,743 字符，是三元组的约 5.8 倍。E3 显示 k=6 时仍有 74.8%，所以默认 k=10 是折中，但生产延迟与成本影响未实测。
2. **嵌入覆盖率**：source unit 必须全部嵌入才能被检索；积压期的表现（部分 unit 不可见）需要降级策略——当前设计是"未嵌入即不可检索"，会让新摄入的原文有可见延迟。这一条需要评审时确认是否可接受。
3. **只接三条入口**：不带 intent 的 recall、OpenClaw、Working Set 不受益，可能造成"同一系统两个召回质量"的困惑。
4. **单一基准**：进攻判据只在 LongMemEval 上有数据；LoCoMo 只做不劣化守护。
5. **标签枚举改动**：新增 `SOURCE` 会让标签集合变化，任何按标签集合做断言的旧测试都要检查。
6. **未实测**：`[SOURCE] [日期] speaker: text` 与评测臂 `- [日期] role: text` 前缀差异对模型的影响，假设可忽略但未验证。

## 12. 待实施前确认

- 第 11 节第 2 条（嵌入积压期的降级策略）需要明确裁定。
- 第 11 节第 3 条（只接三条入口）是否需要本轮一并处理。
- 迁移编号 `0037` 的使用需确认不与其他在途工作冲突。
