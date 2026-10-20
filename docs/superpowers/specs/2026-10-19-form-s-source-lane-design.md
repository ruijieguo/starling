# 形态 S：带日期的原文通道进入生产召回（完整设计 v3）

日期 2026-10-20（v1→v2 经 Codex 首轮 14 条，v2→v3 经二轮 12 条；随后按用户裁定补 §6.3 通用摄入 API 定位与 provenance 列）。状态：**设计稿，未实现**。

**v3 相对 v2 的实质变化**：v2 把授权当成"调用方传一个 scope"的过滤问题，v3 承认它是**信任边界问题**——`SourceScope` 必须由摄入作业权威签发，且索引元数据必须与 payload 交叉验证。v3 还撤回了 v2 的一个错误承诺（Project 机制同轮实现），并重写了 abstain（v2 用名次判据，会把无关结果当证据）。

**产品定位（用户 2026-10-20 澄清）**：原文通道的产品面是**通用摄入 API**，不是某个前端。Claude Code transcript 只是测试数据，Dashboard 摄入是本轮唯一的端到端测试消费者，不是设计依据。

## 0. 结论

左脑 = 一条原文召回 lane：原始话轮存 `source_documents` + engram，按**向量**检索，以 `[SOURCE]` 标签渲染，与右脑语句候选在同一 `Candidate` variant 上 RRF 融合。

**但必须先说清能力边界**：本轮实现的是**会话内**召回（`Session` 模式）。跨会话召回（`Project` 模式）的**机制**设计完整，但**不实现、不暴露**，因为它没有被评测过，也没有被安全复核过。§1 的读数是"跨会话条件下的检索证据"，不是 Project 模式的验证，更不是 Session 模式的预期。

## 1. 证据及其正确边界

| 事实 | 读数 |
|---|---|
| 真实检索，带日期原文 vs 带日期三元组 | 84.1% vs 17.9%（+66.4pp）|
| 日期边际贡献 | +29.2pp（k=20），k=6 时 +25.7pp |
| 生产 source 腿 BM25 vs 评测用向量 | 55.4% vs 84.1%（**判劣**）|
| BM25 证据召回@20 | 55.1%（向量 89.4%），34 题零证据 |
| 抽取对个人事件的保留率 | 11.1% |

**这些实验实际是什么**（v2 的 §7.5 说错了，这里更正）：

- LongMemEval 113 道时序题：每题 haystack 有 **41 到 58 个会话，中位 47，只有 14 道题正好 47**（v2 写"每题 47 个会话"是错的）。
- LoCoMo：**10 个对话组，每组 19 到 32 个会话**（v2 写"每组 10 个会话"是错的）。
- 评测实现是**每题/每组一个独立库**，把话轮平铺成 statement 行后直接调 `SemanticRetriever`（`spike_run.py:78,113`、`locomo_l1.py:115`）。它**没有**经过 `SourceScope`、没有项目身份、没有跨库隔离、没有 planner 融合。

**因此准确的表述是**：这是"在互相隔离的基准库里观察到的跨会话检索证据"。它说明**跨会话能力有价值**，但它**不是**任何生产模式的验证——尤其不是 Session 模式（那些题本来就是多会话的），也不是 Project 模式（没有项目边界参与）。

**这条直接决定了落地顺序**：本轮先做能安全落地的（会话内），跨会话作为独立项目，配它自己的评测（把每个基准库映射成一个显式 project、并测混合库）与安全复核。

## 2. 接入点与生效范围

| 入口 | 经过 planner | 位置 |
|---|---|---|
| `/api/converse`、`/ws/converse` | 是 | `engine.py:495-514` → `_memory_core.py:254-263` → `memory_ops.cpp:376`（planner 在 `:395`）|
| `/api/recall` 带 intent | 是 | `commands.py:114-129` → `engine.py:598` → `_memory_core.py:220-241` → `retrieval_planner.cpp:86` |
| `/api/recall` 不带 intent | 否 | `commands.py:130-137` → `_memory_core.py:196-218`；completion 模式走 `PatternCompletor` |
| OpenClaw recall / workingSet | 否 | `runtime.ts:123`、`index.ts:112-114` |

左脑只接 planner 内部。这是范围限制，不是缺陷。

**intent 限制照搬父 spec**（`2026-10-17-...md:102-118`）：FACT_LOOKUP、HISTORY、PREFERENCE、ABSTAIN_CHECK 开；BELIEF_OF_OTHER、META_BELIEF、COMMON_GROUND、COMMITMENT_DUE、NORM_LOOKUP 不开。

## 3. 作用域：签发、校验、传播

### 3.1 为什么这是信任边界，不是过滤器（Codex 二轮 #1）

v2 的做法是"调用方在请求里传 scope"。问题：`SourceScope` 由调用方提供，而 Dashboard 的鉴权只有**一个配置 bearer token**（`auth.py:9-30`，常量时间比较、无会话/项目成员概念）。传什么值都由调用方决定，等于没有边界。

v3 分两层：

1. **签发（authoritative issuance）**：`session_id` 与 `project_key` 在**摄入作业被 claim 的那一刻**从 job 记录确定，写进 unit 元数据，此后不可变。job 里本来就有 `session_id`（`ingest_session.py:66` 写入 `{"session_id","transcript_path","cwd","tenant"}`），只是 `engine.py:883` 现在没用它——v3 用它。
2. **校验（cross-check）**：检索时向量行只提供定位 `(engram_ref, clause_id)`。取回 payload 后必须验证 **`unit.session_id` 与索引行的 `session_id` 一致**，不一致即丢弃并计 `scope_mismatch`（Codex 二轮 #1 指出的正是这个缺口：v2 只校验 speaker 与 hash，不校验会话）。

`project_key` 的签发（本轮不实现 Project 模式，但要签发，见 §3.3）：从 job 的 `cwd` 与（若存在）git remote 计算，**在 claim 后冻结**，重试复用同一值。

### 3.2 会话内模式（`Session`，本轮唯一实现）

- 授权集：`{holder@session_id}`；
- 检索条件：`session_id = 当前会话`；
- **前提缺口（Codex 二轮 #5）**：现在没有任何调用方知道"当前会话"。摄入是 SessionEnd 作业，而 Dashboard 聊天与那个 transcript UUID 没有关联。

v3 的处理不是假装它存在，而是**明确定义消费者**：

| 消费者 | 会话如何确定 |
|---|---|
| 通用摄入 API 的调用方（产品面）| 调用方本就知道自己的会话，直接传 `session_id` |
| `POST /api/converse`、`WS /ws/converse` | 请求体新增可选 `session_id`；不传则 lane 不工作 |
| `POST /api/recall`（带 intent） | 同上 |
| `Memory.query`（Python） | 新增可选 `session_id` 参数 |
| OpenClaw | 本轮不接 |

**这意味着**：Session 模式的真实用法是"调用方按自己的会话召回"。Dashboard 网页端的聊天没有这个关联，属于已知范围而不是缺陷（§13 第 2 条已裁定不做 hook 集成）。

这一条必须写进交付说明，否则会误以为"接上就能用"。

### 3.3 跨会务模式（`Project`，机制设计完整，本轮不实现）

Codex 二轮 #4 指出 v2 自相矛盾：§7.6 说"同轮实现机制"，§14 说"只留接口"。**v3 撤回实现承诺**，只保留：

- 模式定义：授权集 `{holder@project_key}`，检索 `project_key = 当前项目`；
- **写入侧仍然签发并存储 `project_key`**（列 + 值），因为不这么做，日后启用就要重灌全部历史数据。这是**数据先见**，不是代码先见——写数据不等于实现检索分支。
- 不实现 `Project` 检索分支、不加开关暴露、不加未测的授权逻辑。

**project_key 的稳定性（Codex 二轮 #2，v2 说错）**：v2 写"移动仓库会改变 key"。**改法**：优先用 git remote URL 的规范化哈希——remote 不变则仓库移动**不会**改变 key；没有 remote 时才退回 `cwd` 绝对路径哈希（这时移动会变，属于已知限制）。同一 remote 的多个克隆会合并成同一 project，这是**设计意图**（同一个项目的不同工作副本）。`--bootstrap` 作业的 `cwd` 为空（`ingest_session.py:96`），这类导入**不签发 project_key**，留空，日后按"未知来源"处理，不猜。

### 3.4 缺省语义（Codex 二轮 #11）

v2 同时写了"缺省即 Off"与"缺省即拒绝"，矛盾。v3 统一：

- 请求**未提供** scope 字段 → `Off`，lane 不工作（正常情况）；
- 请求提供 scope 但**格式非法或字段冲突**（如 `mode=Session` 却无 `session_id`）→ **拒绝查询**（`invalid_source_scope`），不静默降级；
- `Project` 模式在开关关闭时收到请求 → 拒绝（`source_scope_mode_disabled`），**不允许用请求参数开启**。

## 4. 检索与融合

### 4.1 类型化候选

采用父 spec 的 `std::variant<StatementCandidate, SourceCandidate>`。`SourceCandidate` 字段：`tenant_id`、`engram_ref`、`clause_id`、`holder_id`、`session_id`、`project_key`、`turn_index`、`observed_at`（**unit 级**，见 §5.3）、`text`、`score`、`rrf_rank`。

**去重身份（Codex 二轮 #8）**：v2 只写 `(tenant, engram_ref, clause_id)`，但增长的 transcript 快照会得到新 engram_ref，导致同一话轮重复出现、白白占上下文。v3 改为与现有 observer 一致的元组去重：`(holder, session_id, turn_id 或 turn_index, observed_at, text)`（参照 `source_retriever.cpp:1423` 的 `seen_turns` 构造）。

### 4.2 fetch

1. 问题嵌入（与语句腿同 embedder/model/dim；不匹配的行不参与）。
2. `SourceVectorIndex::search`，**所有条件在 SQL 下推、排序之前**：
   - `tenant_id` 精确匹配；
   - `holder_id IN allowed_holders`；
   - **scope**：`Session` 下 `session_id = ?`；`Off` 不检索；
   - `status='embedded'`；
   - **时间三重界**：`registered_at <= as_of` 且 `engram.created_at <= as_of` 且 **`observed_at IS NOT NULL AND observed_at <= as_of`**。
     - v2 写 `(observed_at IS NULL OR ...)` 与"无时间不可见"自相矛盾（Codex 二轮 #9 指出）。v3 明确：**source lane 只召回有可信时间的 unit**，`observed_at IS NULL` 的一律不进候选。
     - 理由：`observed_at` 是渲染日期与 as-of 语义的唯一依据；缺失时既不能排序也不能截断。这类 unit 仍存在于库中（可审计），只是不进召回。这要在 receipt 里计数 `source_no_time`。
   - `erased_at IS NULL`、`retention_mode='audit_retain'`（对齐 `source_retriever.cpp:1377`）。
3. **回填（Codex 二轮 #8）**：v2 的"取 k×3"不保证 k 条——若前 3k 全被去重或复核拒绝，后面还有合法行也拿不到。v3 改为**迭代回填**：以倍增批量取（k、2k、4k…，上限 `k_max=200`），直到凑够 k 条或遍历完符合条件的集合；若遍历完仍不足，返回实际条数并在 receipt 标 `source_truncated=true`（截断），**不**标成"语料不足"。
4. **payload 交叉校验**：解析 unit → `unit.speaker == holder_id` → `unit.session_id == 索引行 session_id`（§3.1）→ 内容哈希与 `engrams.content_hash` 一致 → `erased_at IS NULL`。任一不符丢弃并计数。
5. **frontier 交叉**：命中的 engram 必须与 planner 的可见 engram 集相交（类型化 join）。与 `global_holder_filter` 不一致时照现有 `invalid_scope_filter_mix`（`retrieval_planner.cpp:204-212`）拒绝整次查询。

### 4.3 融合：RRF

两路各自按名次，`score = Σ 1/(60 + rank)`，`k=60`（RRF 用名次，不需要分数同分布——v1 的相反说法是错的）。融合后按 score 降序、同分按 identity 稳定排序，每行带 `lane` 与 `rrf_rank` 进 `score_breakdown`。统一字节预算（`chunk_byte_budget`，默认 8000），按整行截断，计数 `budget_skipped`。不引入 `min_source_items`（父 spec 已放弃该参数）。

### 4.4 abstain（Codex 二轮 #6，v2 的判据是错的）

v2 用 `best_source_rank <= k` 判"有证据"——**这等于取消低分保护**：只有 source 候选时，最不相关的那条也是 rank 1，自动通过。

v3 改为**分数判据 + 预算后判定**：

- source 候选的相似度分数与语句的 `final_score` 不可直接比，所以**分别设阈值**：`tau_source`（新配置项，默认待实测确定，初始取与 `tau_recall=0.25` 同量级但必须由一次标定实验给出，不拍脑袋）；
- `AbstentionInput` 增加 `best_source_score`（无 source 为 `-inf`）；
- 判据：`any_candidates || best_source_score >= tau_source`；
- **预算之后判定**：只有当该 source 行**实际进入了渲染后的 context pack** 才算证据（被字节预算截掉的不能用来宣称"有证据"）；
- 语句侧三个否决条件（frontier/recanted/conflict）对 source 不适用，但成立时仍拒答，理由里带 `source_available` 供诊断（保守，见 §14）。

`tau_source` 未标定前，**lane 默认关闭**——这一步是硬约束，不允许用未经标定的阈值上线。

### 4.5 渲染

**payload 的真实结构（v2 已更正，此处确认）**：带版本前缀的行（`turn_prefix="@starling/source-turn-v1 "`，`claim_contract.cpp:120`；容错 `v2` 在 `:121`）。`units()` 产出的 unit 里 `text` 是整行原文，解析后的说话内容在 `utterance`（`claim_contract.cpp:194`）。

**时间来源（Codex 二轮 #9；用户 2026-10-20 澄清后进一步修正）**：v2 说"按 `adapter_name` 区分 `source_turn` 与 `ingest_clock`"——**不成立**，因为 `retain_source_turns` 对所有调用都写死 `adapter_name="source_turns"`（`source_retriever.cpp:1297`）。

v3 原以为"本轮只有一个写入路径，一律 `source_turn`"，但 §6.3 的裁定（通用摄入 API，transcript 只是测试数据）使 `ingest_clock` 成为真实用例。因此：

- **provenance 显式存储**：写入 API 增加必填参数 `provenance ∈ {source_time, ingest_clock}`，落 `source_unit_vectors.provenance` 列（§5.3）。
- `source_time` → 渲染日期；`ingest_clock` → **不渲染日期**（行仍出现，日期位留空）。
- 检索侧不因 provenance 过滤：两种来源都可召回，只是显示不同。as-of 截断对 `ingest_clock` 用 `observed_at`（= 摄入时刻）判断，语义正确。

**多行注入（Codex 首轮 #11）**：原文换行 JSON 转义为单行，续行不产生标签前缀；`neutralize_recall_fence`（`memory_ops.cpp:360`，在 `:408` 调用）继续作用于 SOURCE 行。

**标签**：`ContextPackLabel` **追加** `SOURCE` 在末尾（`context_pack.hpp:15`），现有值编号不变；Python 镜像同步（`bind_05_retrieval.cpp:274-282`）。枚举自省会变，需审计所有遍历/长度断言。

### 4.6 计数、receipt、Python 返回

- `PlannerResult` 增加 `source_entries`；**计数与充分性以融合后的 `entries` 为准**；
- `RetrievalReceipt` 增加 `source_scope_mode`、`source_candidates`、`source_selected`、`source_rejected`、`source_no_time`、`source_truncated`、`source_partial`、`source_degraded_reason`；
- Python 侧**两处返回结构不同，v2 说错了**（Codex 二轮 #12）：
  - `memory.py:189-190` 返回 `{"row": e.row, ...}`——整个 row 对象，不是扁平字段；
  - `engine.py:613-617` 是扁平化 `subject/predicate/object`。
  - 两处都要改：source 条目带 `kind:"source"` 与 `engram_ref/clause_id/holder/session_id/observed_at/text`；statement 条目补 `kind:"statement"` 保持向后兼容。

## 5. 存储

### 5.1 写入侧不是"不变"（Codex 二轮 #7，v2 说错）

v2 写"写入路径不变"。**不成立**，有三处必须改：

1. **`source_documents` 按 speaker 分组，不是按会话**（`source_retriever.cpp:1279-1283` 用 `std::map<speaker, turns>`）。同一 speaker 在多个会话的话轮会被并成一个 engram，**document 级 `session_id` 无法表达**。v3 必须：要么按 `(speaker, session_id)` 分组，要么把 `session_id` 存到 **unit 级**元数据。选择**后者**（unit 级），因为 unit 级元数据对检索与渲染都需要。
2. **`retain_source_turns` 内部自行提交**（`source_retriever.cpp:1291` 的 `TransactionGuard`），无法与"入队 pending 向量行"原子完成。v3 要加一个可选参数或在同一事务内追加插入，保证"原文写入成功但向量没入队"不会留下静默空洞。
3. **`project_key` 需要写入**（§3.3）。

这三处是 v3 的主要实现面，工作量不小，不能按"复用现有原语"估算。

### 5.2 向量索引：新后端

`VectorIndex` 硬绑 `statement_vectors`（`sqlite_blob_vector_index.cpp:27`）、`SearchScope` 单 holder、返回 `ScoredId` 只有 id+分数、planner 拿不到 `SemanticRetriever` 的私有 embedder。因此新增：

```cpp
struct SourceVectorHit { std::string engram_ref, clause_id, holder_id, session_id; double score; };
class SourceVectorIndex {
public:
    virtual void upsert(persistence::Connection&, const SourceUnitKey&, const SourceUnitMeta&,
                        const std::vector<float>&, std::string_view model, int dim) = 0;
    virtual std::vector<SourceVectorHit> search(persistence::Connection&, const std::vector<float>&,
                                                int k, const SourceSearchScope&) = 0;
    virtual void erase(persistence::Connection&, std::string_view tenant, std::string_view engram_ref) = 0;
};
```

SQLite 实现是**全量扫描 + 排序**，与现有实现同构。这是已知扩展性上限，必须进验收指标（延迟随 unit 数曲线）。依赖注入：给 `RetrievalPlanner` 增加可选 `SourceLaneDeps{SourceVectorIndex*, EmbeddingAdapter*, int dim, std::string model}`，为空即关闭。两个 planner 构造点都要接线。

### 5.3 表（含 unit 级元数据）

迁移 `0037_source_unit_vectors.sql`（仓内最新 `0036`，无冲突）：

```sql
CREATE TABLE source_unit_vectors (
  tenant_id     TEXT NOT NULL,
  engram_ref    TEXT NOT NULL,
  clause_id     TEXT NOT NULL,      -- unit 在 payload 内的稳定编号
  holder_id     TEXT NOT NULL,
  session_id    TEXT NOT NULL,      -- §3，unit 级，签发后不可变
  project_key   TEXT,               -- §3.3，可为空（bootstrap/未知来源）
  turn_index    INTEGER,
  observed_at   TEXT,               -- unit 级；NULL = 无可信时间，不参与召回
  provenance    TEXT NOT NULL CHECK (provenance IN ('source_time','ingest_clock')),  -- §4.5 来源，决定是否渲染日期
  dim           INTEGER NOT NULL CHECK (dim > 0),
  model         TEXT NOT NULL,
  index_vector  BLOB,
  raw_embedding BLOB,
  status        TEXT NOT NULL CHECK (status IN ('pending','embedded','failed')),
  retry_count   INTEGER NOT NULL DEFAULT 0,
  last_attempt_at TEXT,
  embedded_at   TEXT,
  PRIMARY KEY (tenant_id, engram_ref, clause_id)
);
CREATE INDEX idx_suv_scope   ON source_unit_vectors(tenant_id, session_id, status);
CREATE INDEX idx_suv_project ON source_unit_vectors(tenant_id, project_key, status);
CREATE INDEX idx_suv_scan    ON source_unit_vectors(tenant_id, status);
```

`observed_at` 必须在这张表里，因为 §4.2 要在排序前按它过滤（Codex 二轮 #7）。

### 5.4 擦除

- **读侧立即生效**：查询条件含 `erased_at IS NULL`，被擦除 engram 的 unit 立刻不可见，不依赖清理任务；
- 异步清理：tick 删除 `engrams.erased_at IS NOT NULL` 的向量行，滞后进 Vitals；
- `clear_tenant` 的删除列表加入 `source_unit_vectors`（`memory_ops.cpp:642` 附近）；
- 测试必须有：擦除后同一事务外立刻查询，该 unit 不出现。

### 5.5 嵌入生命周期

| 环节 | 做法 |
|---|---|
| 产生 | `retain_source_turns` 内为每个 unit 插 `pending` 行（与原文写入同一事务，§5.1 第 2 点） |
| 驱动 | 现有 `EmbeddingWorker` tick 按 kind 分支；source 分支扫 `status IN ('pending','failed') AND retry_count < 3` |
| 背填 | 首次启用时一次性把已有 `source_documents` 入队（迁移的一部分，非运行时） |
| 重试 | 沿用现有语义：`retry_count+1`、`last_attempt_at` 更新、`>=3` 永久 failed。**注意**：现有 worker **只按 retry_count 判定，没时间退避**（`embedding_worker.cpp:223` 的 SQL），v2 写"退避"是错的 |
| 模型/维度变更 | 必须同时清空 source 向量并把 `retry_count` **重置为 0**、状态置 `pending`；否则永久 failed 的行会带着 `retry_count>=3` 永远不被处理（Codex 二轮 #10） |
| 原子发布 | 单行 UPSERT 原子；批量 tick 用 SAVEPOINT |
| 重建 | source 专用重建：从 `source_documents` + payload 重新枚举；repair guard 的计数与分支是 statement 专用，需各自的验证（重建后 unit 数 == payload 有效行数） |

### 5.6 降级可见性（Codex 二轮 #10）

`source_partial` 必须有**明确的触发规则**，不是只加个字段：

| 情形 | 标记 | 外部表现 |
|---|---|---|
| 查询嵌入失败 | `source_partial=true`, `reason=query_embed_failed` | 只有语句结果；receipt 明示 |
| 存在 pending/未嵌入 unit | `source_partial=true`, `reason=index_pending`, 附带 `index_pending_count` | 同上 |
| payload 复核拒绝 | `source_rejected>0`，不单独置 partial | 计数可见 |
| 依赖未注入（lane 关闭） | `source_off` | 与"没检索到"区分 |
| 重试耗尽 | `source_partial=true`, `reason=index_failed`, 附带 `index_failed_count` | 同上 |

Vitals 聚合积压与永久失败数。**要求**：任何"没检索到"的查询，receipt 必须能区分"语料里没有"与"索引没建好"。

## 6. 写入侧与 Python 适配

### 6.1 写入入口（两条，都是同一个 API）

**产品入口：通用摄入 API。** 任何调用方提供逐话轮数组（`speaker`、`text`、`session_id`、`turn_id`、`turn_index`、`observed_at`）+ `provenance` + `project_key`，即可写入左脑。底层就是 `retain_source_turns`（`source_retriever.cpp:1267`）加 §5.1 的三处改动。**这是产品面，不绑定前端。**

**测试入口：Dashboard transcript worker**（`engine.py:892`）。它是本轮唯一的端到端消费者，用来验证真实数据上的行为，不是设计依据。接它时必须在现有锁与 generation 检查下：generation 在 `engine.py:871` 捕获、`:470` 检查，新调用放在同一 try 块内，`source_missing` 与 `_TenantCleared` 语义照现有 remember 路径。`retain_source_turns` 继承写入门禁（`memory_ops.cpp:56`），但门禁不等于 generation 检查。

### 6.2 时间与清洗

- **毫秒截断**：`valid_observation_time` 只接受秒级（`claim_contract.cpp:124`），transcript 是毫秒（`2026-10-17T10:17:33.385Z`）。在 Python 适配层截断到秒，不改 C++ 合同。
- **新增 `clean_turns_ts()`**：返回 `(role, text, event_time, turn_index)`；不动 `clean_turns()`，避免破坏 `chunk_dialogue` 的两元解包（`ingest_filter.py:84`）。
- **已知损失**：`clean_turns` 剥掉代码块与超长行，source lane 拿到的是清洗后文本，不是逐字节原文。写明，不掩盖。

### 6.3 来源范围（用户 2026-10-20 裁定：transcript 只是测试数据）

**这条改变了设计的重心。** Claude Code transcript 只是**测试数据**，不是产品的摄入主路径。因此：

- 原文通道的入口必须是**通用的摄入 API**：任何调用方只要提供符合 `claim_source_turn_payload` 合同的逐话轮数组（`speaker`、`text`、`session_id`、`turn_id`、`turn_index`、`observed_at`），并给出 `session_id` 与 `project_key`，就能写入左脑。这条 API 就是现有的 `retain_source_turns`（`source_retriever.cpp:1267`）加上 §5.1 的改动，**不绑定任何特定前端**。
- Dashboard transcript 摄入（`engine.py:892`）只是**第一个消费者**，也是本轮唯一的消费者，因为它是现成的、可用于端到端验证的数据源。
- **不作为设计依据的**：transcript 的字段形状（`clean_turns` 的清洗损失、毫秒时间戳、SessionEnd 作业的会话关联）。这些是实现第一个消费者时要处理的细节，不是原文通道的普遍约束。v3 的 §6.2 保留为"transcript 消费者的适配说明"，不再当作核心设计的组成部分。
- **`ingest_clock` 不再是空转**：通用 API 的调用方若无法提供事件时间，就填摄入时刻，来源标 `ingest_clock`，渲染时不显示日期。这条来源语义因此有了真实用例（§4.5 需要它能被区分，见下）。

**对 §4.5 的连带影响**：既然通用 API 会有 `ingest_clock` 来源，v3 原来说"本轮只有一个写入路径，一律 `source_turn`"不再成立。因此 **provenance 必须显式存储**，不能推迟到"将来"：写入 API 增加一个必填的来源参数（`source_time` | `ingest_clock`），存进 `source_unit_vectors.provenance` 列。这是把 v2 标记为技术债的东西提到了本轮。

**对 §3.2 的连带影响**：`session_id` 由通用 API 的调用方提供，不是从 transcript 作业推断。Dashboard 网页端"拿不到会话"的问题，在通用 API 视角下不存在——调用方本来就知道自己的会话。§3.2 的"实际可用面比预期窄"这条风险相应降低，但对**网页端**仍然成立。

## 7. 开关

| 开关 | 默认 | 说明 |
|---|---|---|
| `source_lane.enabled` | `false` | 关闭即不检索、不渲染 |
| `source_lane.render_time` | `false` | 从属于 enabled |
| `current_date_in_prompt` | `false` | 独立 |

**上线额外门槛**：`tau_source` 未标定前 lane 不得开启（§4.4）。

## 8. 与右脑及不变量

不改右脑三通道、六态机、§0.1、Bus 单入口。source unit 无状态，不参与六态机。事实权威在 Statement 图，`[SOURCE]` 靠转义与 fence 保证不冒充。检索/融合/渲染全在 C++，Python 只做信封适配与三元组构造。

## 9. 测试矩阵（Codex 二轮 #11）

| 组 | 用例 |
|---|---|
| 作用域 | Session 排除兄弟会话；Project 含授权兄弟、排除其他项目与其他租户；未提供 scope=Off；非法或冲突字段=拒绝；开关关闭时请求 Project=拒绝；伪造索引 session/project 被 payload 交叉校验拒；frontier 拒绝高排名不可访问命中 |
| 身份稳定性 | 移动仓库后 remote 不变则 key 不变；重试期间 remote 变化不得重分配；同名不同目录不合并；同目录复用；空 cwd/bootstrap 不签发；symlink/worktree；remote URL 规范化 |
| 时间 | 无 `observed_at` 不召回且计 `source_no_time`；as-of 三重界；未来时间不泄漏 |
| 去重与回填 | 重叠 transcript 不重复占上下文；拒绝数 > 3k 时仍能取到后续合法行或明确 `source_truncated` |
| abstain | 只有 source 且全低分时**拒答**；入选但被预算截掉不算证据；`tau_source` 标定前后行为 |
| 渲染 | 多行原文转义后不产生 `[FACT]`；fence 生效；`render_time=false` 无日期；枚举追加不自省破坏（审计所有遍历） |
| 生命周期 | pending→embedded；重试耗尽；模型变更重置 retry_count；重建后 unit 数一致；查询嵌入失败时 `source_partial` |
| Python | `Memory.query`（row 对象）与 Dashboard（扁平）两条返回都带 source 条目 |
| parity | `enabled=false` 时 planner 输出与现状逐字节相同（固定行集） |

## 10. 验收与预算

- 守护：SocialMemBench 0.7825 不下降（固定行集比对）；
- 不劣化：LoCoMo 全量，非时序不劣化（基线 +3.1pp）；
- 进攻：父 spec 原式 `S_dual − max(S_full, S_rag) ≥ max(5pp, α_judge)`（`2026-10-17-...md:158`）；
- 预算：父 spec 给的是**两个基准各约 3e7**（`2026-10-17-...md:171`），不是合计；
- **但注意**：本设计是 Session 模式，上述判据都是跨会话条件下定义的。Session 模式的评测需要**新的**判据与数据集（单会话内的问题），本轮不承诺进攻数字。

## 11. 剩余风险

1. 上下文体积：S 臂中位 14,743 字符，约语句路径 5.8 倍；默认 k=10 是折中，延迟未实测。
2. SQLite 向量后端全量扫描，扩展性上限已知。
3. 三条入口不覆盖（不带 intent 的 recall、OpenClaw、Working Set）。
4. 清洗后文本不是逐字节原文。
5. Session 模式需要调用方显式传会话 id。通用 API 的调用方天然具备；**Dashboard 网页端的聊天不具备**，按 §13 裁定不做 hook 集成，属已知范围。
6. `tau_source` 未标定，lane 不能上线。
7. 未实测：`[SOURCE]` 前缀与评测臂格式差异对模型的影响。

## 12. 二轮 12 条处置

| # | 级别 | 处置 |
|---|---|---|
| 1 | P1 | 采纳：§3.1 改为"签发 + 交叉校验"双层；补 `unit.session_id == 索引 session_id` 校验；承认 auth 只有 bearer token |
| 2 | P1 | 采纳并更正：§3.3 project_key 用 remote 哈希（移动不改 key），重试冻结，bootstrap 不签发；撤回"移动必然改 key" |
| 3 | P1 | 采纳：§1 更正会话数（41-58/中位 47/14 题正好 47；LoCoMo 10 组各 19-32 会话）与"这是隔离基准库里的跨会话证据" |
| 4 | P1 | 采纳：§3.3 撤回"同轮实现 Project 分支"；只签发并存储 project_key，不实现检索分支 |
| 5 | P1 | 采纳：§3.2 明确四个消费者与"必须显式传 session_id"，并写明 Dashboard 网页端不具备该能力 |
| 6 | P1 | 采纳：§4.4 改为分数判据 `tau_source` + 预算后判定；未标定前 lane 不得开启 |
| 7 | P1 | 采纳：§5.1 更正"写入不变"；unit 级元数据、事务原子性、project_key 写入三处都要改；§5.3 表补 `observed_at` |
| 8 | P2 | 采纳：§4.1 去重改为 `(holder, session_id, turn, observed_at, text)`；§4.2 改迭代回填 + `source_truncated` |
| 9 | P1 | 采纳并更正：§4.5 撤回"按 adapter_name 判来源"；用户澄清后进一步改为**写入 API 必填 provenance 并落库**（`source_time` / `ingest_clock`），因为通用摄入 API 使 `ingest_clock` 成为真实用例；§4.2 无时间 unit 不召回 |
| 10 | P2 | 采纳：§5.6 给出 `source_partial` 的触发规则表；§5.5 模型变更同时重置 `retry_count`；更正"无退避" |
| 11 | P2 | 采纳：§9 扩为测试矩阵；§3.4 统一缺省语义（缺省 Off / 非法拒绝 / 关闭模式拒绝） |
| 12 | P2 | 采纳：§4.6 更正 `memory.py` 返回 row 对象；§4.5 引用改 `:132`/`:194`；§6.1 generation 在 `:871` 捕获、`:470` 检查；§5.5 更正无退避；§10 预算引用改 `:171` |

## 13. 待确认（用户 2026-10-20 已裁定：按建议执行）

1. **`tau_source` 标定** —— 裁定：**用单会话切片标定，且与验收题分离**。做法是从已用过的 LongMemEval 确认集中切出"单会话可答"的子集（每题只保留与其证据同会话的话轮），留出一半做标定、一半做验收；不得在同一半上既调阈值又报数字。若切不出足够样本（预计偏少），则 lane 保持关闭，改为先采集真实单会话数据再标定——**不允许用拍脑袋的阈值上线**。
2. **Session 模式的消费者** —— 裁定：**不做 Claude Code hook**。用户 2026-10-20 明确 transcript 只是测试数据，不是重点。产品面是通用摄入 API（§6.3）；Dashboard transcript 摄入只作为端到端测试消费者。因此不投入集成工作，§3.2 的"网页端不具备会话关联"从风险降为**已知范围**。
3. **Project 模式** —— 裁定：**立为独立项目**，含它自己的评测（把每个基准库映射成显式 project、并测混合库隔离）与安全复核（助手转述跨会话、共享目录、时间无界三条残余风险）。本轮只签发并存储 `project_key`，不实现检索分支。
