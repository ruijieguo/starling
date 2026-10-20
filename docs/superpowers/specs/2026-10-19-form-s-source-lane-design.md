# 形态 S：带日期的原文通道进入生产召回（完整设计 v2）

日期 2026-10-20（v1 同日出，经 Codex 评审后全面重写）。状态：**设计稿，未实现**。评审前不动 C++。

**v2 相对 v1 的实质变化**：v1 自造了一套并行 `source_entries` + 交替融合，绕过了父 spec（[双脑设计](2026-10-17-dual-brain-general-memory-design.md)）已经设计好的 `Candidate` variant、RRF(k=60)、第 9 标签 `[SOURCE]`、`neutralize_recall_fence`。v2 回到父 spec 的路线，并逐条修掉 Codex 的 14 条发现。逐条处置见 §13。

## 0. 结论

左脑 = 一条原文召回 lane：原始话轮存 `source_documents` + engram，按**向量**检索，以 `[SOURCE]` 标签渲染，与右脑语句候选**在同一个 `Candidate` variant 上融合**。复用现有写入/存储/授权原语；新增的是 source 单元的向量索引、嵌入生命周期、以及 planner 内部的类型化候选重构。

## 1. 证据（不在本文重述实验）

| 事实 | 读数 |
|---|---|
| 真实检索，带日期原文 vs 带日期三元组 | 84.1% vs 17.9%（+66.4pp）|
| 日期边际贡献 | +29.2pp（k=20），k=6 时 +25.7pp |
| 生产 source 腿 BM25 vs 评测用向量 | 55.4% vs 84.1%（**判劣**）|
| BM25 证据召回@20 | 55.1%（向量 89.4%），34 题零证据 |
| 抽取对个人事件的保留率 | 11.1% |

结论：原文通道要进生产；检索必须向量，不能沿用 BM25。

## 2. 接入点与生效范围

生产召回有四条路径，只有两条经过 `RetrievalPlanner`：

| 入口 | 经过 planner | 位置 |
|---|---|---|
| `/api/converse`、`/ws/converse` | 是 | `engine.py:495-514` → `_memory_core.py:254-263` → `memory_ops.cpp:376`（planner 调用在 `:395`）|
| `/api/recall` 带 intent | 是 | `commands.py:114-129` → `engine.py:598` → `_memory_core.py:220-241` → `retrieval_planner.cpp:86` |
| `/api/recall` 不带 intent | 否 | `commands.py:130-137` → `_memory_core.py:196-218`；`mode="completion"` 走 `PatternCompletor`，不是 `vector_recall` |
| OpenClaw recall / workingSet | 否 | `runtime.ts:123`、`index.ts:112-114` |

**决定 D4-a**：左脑 lane 只接 `RetrievalPlanner` 内部（fetch → fuse → render）。这是**范围限制，不是 bug**：另外三条路径有各自独立的取数逻辑，接它们另立设计。交付说明必须写清，不能让"左脑只在部分入口生效"被误读。

**同时修正 v1 的错误表述**：v1 说这让三条入口"自动获得"——错。planner 内部改动不会让 Python 侧的返回结构自动带上 source，见 §4.4。

## 3. 检索范围：父 spec 的 intent 表照搬

父 spec（`2026-10-17-...md:100-118`）规定左脑只在四个 intent 开启，五个不开。v2 照搬，不重新发明：

| Intent | 左脑 |
|---|---|
| FACT_LOOKUP、HISTORY、PREFERENCE、ABSTAIN_CHECK | 开 |
| BELIEF_OF_OTHER、META_BELIEF、COMMON_GROUND、COMMITMENT_DUE、NORM_LOOKUP | **不开** |

理由：后五类是右脑的社会心智语义，原文通道不改善它们，且会引入无关上下文。`HISTORY` 下 source 按 `observed_at` 升序。

## 4. 检索与融合

### 4.1 类型化候选（父 spec 的设计，v2 采纳）

`FetchedRow`、`RerankCandidate`、`StatementRow`、按 statement ID 去重、claim 证据校验、标签分类全是 statement 形状。v1 用"并行向量"绕开它们，代价是 source 完全进不了计数、receipt 与 Python 返回（Codex #2）。

v2 采用父 spec 的 `std::variant<StatementCandidate, SourceCandidate>`：

```cpp
struct StatementCandidate { StatementRow row; double score; ContextPackLabel label; /* 现状 */ };
struct SourceCandidate {
    std::string tenant_id, engram_ref, clause_id, holder_id;
    std::string session_id; std::optional<int> turn_index;
    std::string observed_at;            // 渲染用；来源见 §4.5
    TimeProvenance provenance;          // source_turn | caller_supplied | ingest_clock | unknown
    std::string text;
    double score = 0.0;                 // 融合前为向量相似度，融合后为 RRF
    int rrf_rank = 0;
};
using Candidate = std::variant<StatementCandidate, SourceCandidate>;
```

`identity` 分别为 statement id 与 `(tenant_id, engram_ref, clause_id)`；去重按 identity。这是 planner 内部重构，工作量计入 P1（父 spec 已如此声明）。

### 4.2 fetch：source 候选

1. 问题文本嵌入（与语句腿同一 embedder、model、dim；**dim/model 不匹配的行一律不参与**）。
2. `search_topk` 于 source 向量索引（§5.2），**过滤条件全部下推到 SQL，且在任何排序之前**：
   - `tenant_id` 精确匹配；
   - `holder_id IN allowed_holders`；
   - `status='embedded'`；
   - **时间三重界**（Codex #7）：`julianday(registered_at) <= as_of` **且** `julianday(engram.created_at) <= as_of` **且** `(observed_at IS NULL OR julianday(observed_at) <= as_of)`。只查 `observed_at` 会让晚摄入的旧 transcript 出现在早期的知识快照里。
   - `erased_at IS NULL`、`retention_mode='audit_retain'`（与 `source_retriever.cpp:1377` 的现有条件一致）。
3. **top-k 之后再过滤的问题（Codex #7 第二条）**：上一步已把时间/授权条件下推，所以不会出现"高分全被时间过滤掉、剩下的空"。若仍需二次过滤（如同一 unit 的重复），采用**取 k×3 候选再回填**，保证最终返回 k 条或明确不足。
4. **payload-speaker 复核（Codex #3）**：向量行只提供 `(engram_ref, clause_id)` 定位，**不能信任它的 `holder_id`**。取出 engram `payload_inline` 后必须重做与 `source_retriever.cpp:1396` 相同的校验：解析 unit、`unit.speaker == holder_id`、内容哈希与 `engrams.content_hash` 一致、`erased_at IS NULL`。任一不符则丢弃并计数 `source_unit_rejected`。**许可来自 payload，不来自索引行。**
5. **perspective frontier 交叉（Codex #3）**：source 命中的 engram 必须与 planner 现有的可见 engram 集相交（类型化 join，不用子串 mask，沿用父 spec 的 v2 授权规则）。与 `global_holder_filter` 的交互照现有拒绝逻辑（`retrieval_planner.cpp:204-212` 的 `invalid_scope_filter_mix`）处理：source lane 的 `allowed_holders` 若与 `global_holder_filter` 不一致，直接拒绝整次查询，不静默降级。

### 4.3 fuse：RRF（修正 v1 的错误理由）

v1 拒绝 RRF 的理由是"两路分数不可比"——**这是错的**。RRF 正是为此设计的：它用**名次**而非分数，`Σ 1/(k + rank)`，`k=60`，因此两路分数分布无需可比。v2 采用父 spec 的 RRF。

- 两路各自排序得到名次；
- `score = 1/(60 + rank_statement) + 1/(60 + rank_source)`（某路缺席则该路项为 0）；
- 融合后按 score 降序，同分按 identity 稳定排序；
- 每行带 `lane` 与 `rrf_rank` 进 `score_breakdown`；
- 最终上下文受**统一字节预算**约束（`chunk_byte_budget`，默认 8000）；截断按整行，计数 `budget_skipped`。

父 spec 已放弃 `min_source_items`（v1 引用了它，实际不存在），v2 也不引入：RRF 自然决定两路比例，人为下限需要单独实测才配得上一个参数。

### 4.4 abstain（Codex #1）

v1 只改 `any_candidates`，**不够**：`evaluate_abstention` 的四个条件里，`max_score < tau_recall`（默认 **0.25**，`abstention.hpp:10`）在"只有 source 命中、没有语句"时仍会触发拒答，因为 `max_score` 取自语句重排分。

v2 定义：
- **`max_score` 取融合后最高分，但两路分数量纲不同，所以按 lane 分别归一**：语句路沿用现有 `final_score` 与 `tau_recall` 比较；source 路用**融合名次**判据——只要 source 候选进入融合结果前 `k` 名，即视为"有证据"。实现上给 `AbstentionInput` 增加 `best_source_rank`（无 source 为 INT_MAX），判据为 `best_source_rank <= k`。
- `frontier_denied`、`only_recanted_evidence`、`unresolved_conflict` 三个**语句侧**条件保持不变，且对 source **不适用**（source 无状态、无冲突边）。但要注意：当三个条件之一成立而 source 有命中时，**不能**因此豁免——它们表达的是"语句侧知道但不可用"，与"另有原文可用"是两件事。v2 的规则是：这些条件成立时**仍然拒答**，但拒答理由里保留 `source_available=true` 供诊断。这一条是保守选择，需要评审确认。
- `Sufficiency`（`retrieval_receipt.hpp:18`，含 `MISSING_INFO`）在 source 有命中时不得为 `MISSING_INFO`；source 检索被降级（§6.3）时另设 `source_partial` 标记。

### 4.5 渲染（Codex #6、#11）

**v1 的事实错误**：payload 不是"换行分隔的 JSON 行"，而是**带版本前缀的行**（`turn_prefix = "@starling/source-turn-v1 "`，`claim_contract.cpp:120`；容错前缀 `v2` 在 `:121`）。`units()` 产出的 unit 里 `text` 是**整行原文**（含前缀），解析出的说话内容字段是 `utterance`（`claim_contract.cpp:178` 附近的注释与解析）。v2 按实际结构写。

**时间来源必须可区分（Codex #6 第二条）**：写合同只接受六个字段（`claim_contract.cpp:123`），无法携带来源与精度，因此：
- 在**读侧**由 engram 的 `adapter_name` 决定来源：`source_turns`（transcript 摄入）→ `source_turn`；其他 → `ingest_clock`。这条规则必须写死在 C++，不靠调用方传参。
- 渲染规则：`source_turn` **渲染日期**；`ingest_clock` **不渲染日期**（行仍出现）；`unknown` 不可见（已被 §4.2 过滤）。
- 若将来要携带逐 unit 的来源，需扩展合同到 v3 并在 C++ 内做版本分派；v2 明确**不做**，只记录为技术债。

**多行原文的标签注入（Codex #11）**：原文若含 `\n[FACT] ...`，逐行前缀方案会让续行冒充权威标签。v2 的处理：
- 渲染为单行：换行替换为 `\n` 转义，与 `[SOURCE]` 行内 JSON 化一致（现有 observer 就是 JSON 转义，`source_retriever.cpp:1444`）；
- 或在每个续行前加 `  ` 缩进 + 不产生标签前缀。**选前者**（JSON 转义），因为它与现有 observer 行为一致，且可机械验证。
- `neutralize_recall_fence`（`memory_ops.cpp:360`，在 `:408` 被调用）**继续作用于** SOURCE 行，不可省。

**标签**：`ContextPackLabel` 追加 `SOURCE`（`context_pack.hpp:15` 现有 FACT…ABSTAIN 共 8 个）。**追加在末尾**，不插入中间——插入会重编号后续枚举值。Python 镜像同步（`bind_05_retrieval.cpp:274-282`）。

### 4.6 计数、receipt 与 Python 返回（Codex #2）

只加候选类型不够，下游仍只认语句：
- `PlannerResult` 增加 `std::vector<SourceEntryOut> source_entries`（供需要原文字段的调用方），但**计数与充分性以融合后的 `entries` 为准**；
- `RetrievalReceipt` 增加 `source_candidates`、`source_selected`、`source_rejected`、`source_partial`；
- Python 侧：`memory.py:186-194` 与 `engine.py:610-620` 现在只序列化 `e.row.subject_id/predicate/object_value`。**必须同时改**：source 条目输出 `{"kind":"source","engram_ref":…,"clause_id":…,"holder":…,"observed_at":…,"text":…,"label":"SOURCE","score":…}`，并保留 `kind:"statement"` 区分。不改的话，source 会出现在 `context_pack` 里却在 `results` 中消失——这正是 Codex 说的"上下文里有、结果里没有"。

## 5. 存储与索引

### 5.1 写入（不变）

`retain_source_turns`（`source_retriever.cpp:1267`）。payload 格式见 §4.5（版本前缀行）。写入本身不需要改，但**读侧需要新的元数据**（§4.5 的来源判定），所以 `source_documents` 需要记录 `adapter_name`（或复用 engram 的）——v2 选择**直接 join engrams.adapter_name**，不加列。

### 5.2 向量索引：明确是新后端（Codex #9）

v1 写"另建一张表"是**低估**。实际问题：
- `VectorIndex::insert/search_topk/remove` 的 id 参数叫 `stmt_id`，`SearchScope` 只带一个 `holder_id`（单值），`search_topk` 实现 `JOIN statements`（`sqlite_blob_vector_index.cpp:60` 附近）；
- 返回类型 `ScoredId` 只有 id + 分数，装不下 `(engram_ref, clause_id)` 复合身份；
- planner 拿不到 `SemanticRetriever` 私有的 embedder（`semantic_retriever.hpp:32`）。

因此 v2 明确：**新增 `SourceVectorIndex` 抽象**，不复用 `VectorIndex`：

```cpp
struct SourceVectorHit { std::string engram_ref, clause_id, holder_id; double score; };
class SourceVectorIndex {
public:
    virtual ~SourceVectorIndex() = default;
    virtual void upsert(persistence::Connection&, const SourceUnitKey&, std::string_view tenant,
                        std::string_view holder, const std::vector<float>& v, std::string_view model, int dim) = 0;
    virtual std::vector<SourceVectorHit> search(persistence::Connection&, const std::vector<float>& q,
                                                int k, const SourceSearchScope&) = 0;
    virtual void erase(persistence::Connection&, std::string_view tenant, std::string_view engram_ref) = 0;
};
```

`SourceSearchScope` 带 `tenant_id`、`std::vector<std::string> holders`（**多值**）、`as_of`、`include_unknown_time`。

**成本要写明**：SQLite 后端的 `search` 是**全量扫描 + 排序**（与现有 `SqliteBlobVectorIndex` 同构）。在 source unit 数量达到数万级之前可接受，但这是已知的扩展性上限，必须进当轮验收指标（查询延迟 p50/p95 随 unit 数的曲线）。zvec 后端可作为后续替换，接口为此预留。

**依赖注入**：planner 需要一个 embedder 引用。v2 的做法是给 `RetrievalPlanner` 构造参数增加**可选的** `SourceLaneDeps{SourceVectorIndex*, EmbeddingAdapter*, int dim, std::string model}`，为空时等于关闭。不改 `SemanticRetriever` 的封装。

### 5.3 表

迁移 `0037_source_unit_vectors.sql`（当前最新 `0036`）：

```sql
CREATE TABLE source_unit_vectors (
  tenant_id    TEXT NOT NULL,
  engram_ref   TEXT NOT NULL,
  clause_id    TEXT NOT NULL,
  holder_id    TEXT NOT NULL,
  dim          INTEGER NOT NULL CHECK (dim > 0),
  model        TEXT NOT NULL,
  index_vector BLOB,
  raw_embedding BLOB,
  status       TEXT NOT NULL CHECK (status IN ('pending','embedded','failed')),
  retry_count  INTEGER NOT NULL DEFAULT 0,      -- Codex #8：现有 worker 依赖
  last_attempt_at TEXT,
  embedded_at  TEXT,
  PRIMARY KEY (tenant_id, engram_ref, clause_id),
  FOREIGN KEY (tenant_id, engram_ref) REFERENCES engrams(tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX idx_source_unit_vectors_scan ON source_unit_vectors(tenant_id, status);
```

`retry_count` 与 `last_attempt_at` 是照现有 worker 的字段补的（`embedding_worker.cpp:90,103-108`），v1 漏了。

**`ON DELETE CASCADE` 不足以实现擦除（Codex #5）**：`clear_tenant`（`memory_ops.cpp:642`）是物理删整个租户，不是 engram 擦除钩子；且级联不会处理"设 `erased_at`"。v2 明确：
- **擦除 = 读侧过滤 + 异步清理**：§4.2 的查询条件已含 `erased_at IS NULL`，所以被擦除的 engram 其 source unit **立即不可见**，不依赖向量表是否清干净；
- 清理任务由 `ProjectionMaintainer` 风格的 tick 执行（删除 `engrams.erased_at IS NOT NULL` 对应的向量行），滞后计入 Vitals；
- `clear_tenant` 的删除列表加入 `source_unit_vectors`（与 `source_documents` 同列，`memory_ops.cpp:642`）；
- **立即性证明**：必须有一条测试——擦除 engram 后**同一事务外**立刻查询，该 unit 必须不出现（靠读侧过滤而非清理任务）。

### 5.4 嵌入生命周期（Codex #8）

v1 说"kind 分发"，没说清谁驱动。v2 补全：

| 环节 | 做法 |
|---|---|
| 待处理单元的产生 | `retain_source_turns` 成功后，在同一事务内为每个 unit 插 `status='pending'` 行（只写元数据，不算向量） |
| 谁嵌入 | 现有 `EmbeddingWorker` 的 tick 里按 kind 分支：语句分支现状不变；source 分支扫 `source_unit_vectors WHERE status IN ('pending','failed') AND retry_count < 3` |
| 背填 | 已存在的 `source_documents`（评测脚本写入的历史数据）在首次启用时一次性扫描入队；**这是迁移的一部分**，不是运行时行为 |
| 重试与退避 | 沿用现有语义：失败 `retry_count+1`、`last_attempt_at` 更新、`retry_count>=3` 永久 failed |
| 模型/维度变更 | **必须同时清空 source 向量**。现有行为只删 `statement_vectors`，不清 source 会让新旧模型向量混在一张表里、余弦不可比。变更路径需同时置 `status='pending'` |
| 原子发布 | 一条 unit 的写入是单行 UPSERT，天然原子；批量 tick 用 SAVEPOINT |
| 重建 | source 专用重建：从 `source_documents` + payload 重新枚举 unit；现有 repair guard 的计数与分支是 statement 专用，**不能直接套用**，需各自的计数器与验证（重建后 unit 数与 payload 行数一致） |
| 增量幂等 | payload 幂等（`sha256` 前 16 hex）保证重复摄入不重切；但**增长的 transcript 批次**不等于幂等——同一 engram 若被追加内容会得到新 ref，旧 ref 的向量保留，这是预期行为，需在测试里固定 |

## 6. 写入侧

### 6.1 唯一摄入点

`engine.py:892` 的摄入循环。v1 说"加一次 `retain_source_turns`"，但漏了三点（Codex #5）：

1. **必须在现有锁与 clear-generation 检查下执行**。`engine.py:470` 有 generation 捕获，`engine.py:894` 有 `_TenantCleared` 与 `source_missing` 处理。新调用必须放在同一个 try 块内，否则旧 job 能把已清空的租户重新填满。
2. `retain_source_turns` 经 `remember_prepare` 继承了写入门禁（`require_write_admission`，`memory_ops.cpp:56`），但**这不等于 generation 检查**——门禁拦的是运行时状态，generation 拦的是"这个 job 是否属于被清空之前"。
3. 失败语义：`source_missing`（抽取期间租户被清）必须让整个 job 作废，与现有 remember 路径一致。

### 6.2 `clean_turns` 的改动（Codex #12）

`clean_turns`（`ingest_filter.py:23-52`）返回 `[(role, text)]`，且**会剥掉代码块与超长行**——所以它的输出**不是**原始对话文本。v2 明确：

- 加时间：返回 `[(role, text, event_time)]`；
- **但这会破坏 `chunk_dialogue` 的两元解包**（`ingest_filter.py:84-85`）。v2 不改 `chunk_dialogue` 的签名，而是**新增** `clean_turns_ts()` 返回三元组供 source lane 用，`clean_turns()` 保持原样供 `chunk_dialogue` 用。二者共用同一解析逻辑，避免行为漂移。
- **记录已知损失**：source lane 拿到的是"清洗后"文本（无代码块、无超长行），不是逐字节原文。这与"原文通道"的承诺有差距，必须在设计里写明，不掩盖。

### 6.3 时间精度（Codex #6 第三条，硬阻塞）

`valid_observation_time` 的正则只接受**秒级**（`^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})?$`，`claim_contract.cpp:124`），而 transcript 的 `timestamp` 是毫秒级（`2026-10-17T10:17:33.385Z`）。**v1 的方案会被合同直接拒收。**

v2 的处理：**在 Python 适配层截断到秒**（`2026-10-17T10:17:33Z`），不改 C++ 合同。理由：合同放宽精度会影响所有 `observed_at` 消费方（排序、as-of 比较），风险远大于收益；而毫秒对记忆语义无价值。这一条要在 `clean_turns_ts()` 里实现并有测试。

### 6.4 其他来源（Codex #12 第 3 条，v1 错误）

v1 声称自由文本 `remember` 与 OpenClaw 的原文也会变得可召回——**错**。本设计唯一的注册钩子是 Dashboard 的 transcript worker。自由文本路径不会调 `retain_source_turns`，因此它们的原文**不会**进入 source lane。

v2 明确：**本轮只覆盖 Dashboard transcript 摄入**。其他来源若需要，各自在其摄入点加调用，另立工作。`ingest_clock` 这一来源语义因此只对"将来接入的其他来源"有意义，本轮没有实际用例——保留定义，但要在文档里说明它当前是空转。

## 7. 授权语义（Codex #4，需要用户裁定）

v1 的映射是 `assistant → self`、`user → claude-code:{project}`，授权集 `{self, 当前对话方}`。Codex 指出两个问题，都成立：

1. **`self` 不是对话隔离**。所有项目的 assistant 话轮都记在 `self` 下，于是任何对话都能召回任何项目的助手输出——而助手输出经常引用或总结第三方内容（比如转述用户提到的同事）。字面上满足 holder allowlist，实质上破坏了"不涉及第三方"。
2. **`claude-code:{project}` 用的是目录 basename**，同名目录会合并成同一个人。

**v2 的候选方案（需裁定）**：

| 方案 | 内容 | 代价 |
|---|---|---|
| A. 会话级隔离 | 引入 `session_scope`（= transcript 会话 id 或 job id），授权集从 `{self, 对话方}` 收紧为 `{self@session_scope, 对话方@session_scope}`；跨会话不召回 | 需要 `source_unit_vectors` 与检索都带 session 维度；`source_turn` 合同已有 `session_id`，可复用 |
| B. 保持 `self`，但只召回"当前会话" | 检索时强制 `session_id = 当前会话` | 简单，但左脑退化为"当前对话内的记忆"，跨会话的通用记忆能力（本任务的目标）基本消失 |
| C. 保持现状，接受跨项目 | 不做隔离 | 与"不涉及第三方"冲突，不推荐 |

**我倾向 A**，但它会改变"左脑是通用记忆"的能力边界——跨会话召回是通用记忆的核心。所以这不是纯技术取舍，需要你定。

在裁定前，v2 采用**保守的中间态**：`self` 的 assistant 话轮**只按 session 召回**（等价 B），`user` 话轮按对话方 holder 召回（跨会话）。这样一个项目内的对话记忆仍然可用，同时不会把别的项目的助手总结带进来。这条要标注为"临时，待裁定"。

## 8. 开关

三个开关，**全部默认关闭**（修正 v1 的 `render_time=true`）：

| 开关 | 默认 | 关闭时 |
|---|---|---|
| `source_lane.enabled` | `false` | 不检索、不渲染 |
| `source_lane.render_time` | `false`（**且从属于 enabled**）| 行出现但不带日期，仅当 enabled=true 时才有意义 |
| `current_date_in_prompt` | `false` | 不加 `Current Date` 行 |

**兼容性（Codex #13 的修正）**：
- `SOURCE` **追加**在枚举末尾（FACT…ABSTAIN 之后），现有枚举值编号不变；
- 但**枚举自省会变**：任何对 `ContextPackLabel` 做遍历/长度断言的代码都会看到第 9 个值。必须审计 `tests/cpp/test_context_pack.cpp` 与所有 `switch`；
- 固定行集快照只能证明**渲染字节**不变，**不能**证明 receipt、事件、摄入行为、worker 行为、Python 返回结构不变。v2 把兼容性主张收窄为"渲染字节 + 现有测试全绿"，不再声称更强的保证。

## 9. 与右脑及不变量的关系

- 不改右脑三通道抽取、六态机、§0.1、Bus 单入口；
- source unit 无状态，不参与六态机；
- 事实权威仍在 Statement 图；`[SOURCE]` 行靠 §4.5 的转义与 `neutralize_recall_fence` 保证不冒充；
- 融合、检索、渲染全在 C++（边界裁定）；Python 只做 transcript 信封适配与三元组构造。

## 10. 测试

| 类别 | 用例 |
|---|---|
| 单元 | unit 解析（含版本前缀）、`clause_id` 稳定性、时间三重界、多 holder 检索、payload-speaker 复核拒绝伪造行 |
| 授权 | 混合说话人 engram；擦除后**立即**不可见（不靠清理任务）；generation 过期 job 不得回填 |
| 渲染 | `SOURCE` 行多行原文转义后不产生 `[FACT]`；`neutralize_recall_fence` 仍生效；`render_time=false` 时不带日期；`ingest_clock` 不渲染日期 |
| 融合 | RRF 名次计算；同分稳定；字节预算截断计数；abstain 在"只有 source"时不误拒 |
| 生命周期 | pending→embedded；重试耗尽转 failed；模型变更清空并重排；重建后 unit 数与 payload 行数一致 |
| parity | `source_lane.enabled=false` 时 planner 输出与现状逐字节相同（固定行集快照） |
| 端到端 | converse、带 intent 的 recall、`Memory.query` 三条路径都能返回 source 条目；不带 intent 的 recall 与 OpenClaw 明确断言**不返回** |

## 11. 验收与预算

- 守护：SocialMemBench 0.7825 不下降（固定行集比对）；
- 不劣化：LoCoMo 全量复跑，非时序类不劣化（基线 +3.1pp）；
- 进攻：父 spec 的原始判据是 `S_dual − max(S_full, S_rag) ≥ max(5pp, α_judge)`（`2026-10-17-...md:158`）。v1 写成 `S_left − S_rag` 是**错的**，v2 更正为父 spec 的原式；
- 预算：父 spec 给的是 **两个基准各约 3e7**（`2026-10-17-...md:152,153`），不是合计 3e7。v1 写错，v2 更正，并说明本轮要各自申请。

## 12. 剩余风险

1. **上下文体积**：S 臂中位 14,743 字符，约语句路径的 5.8 倍；k=6 时 74.8%。默认 k=10 是折中，生产延迟未实测。
2. **SQLite 向量后端是全量扫描**：unit 数上到数万后延迟会退化，需要实测曲线与替换预案。
3. **只接三条入口**：不带 intent 的 recall、OpenClaw、Working Set 不受益。
4. **清洗后的文本不是逐字节原文**（§6.2），"原文通道"有损。
5. **`ingest_clock` 来源本轮无实际用例**（§6.4）。
6. **未实测**：`[SOURCE]` 前缀与评测臂 `- [日期] role: text` 的差异对模型的影响。

## 13. Codex 14 条逐条处置

| # | 级别 | 处置 |
|---|---|---|
| 1 | P1 | 采纳：§4.4 重写 abstain，按 lane 归一，source 用 `best_source_rank`；三语句侧否决条件对 source 不适用但保留保守拒绝 |
| 2 | P1 | 采纳：§4.4 改用 `Candidate` variant；§4.6 明确计数、receipt 与 Python 返回都要改；删除"自动获得"的错误表述 |
| 3 | P1 | 采纳：§4.2 增加 payload-speaker 复核、内容哈希、erased/retention 条件、frontier 交叉、`global_holder_filter` 冲突拒绝 |
| 4 | P1 | 采纳为待裁定：§7 给出 A/B/C 三案，v2 暂用保守中间态 |
| 5 | P1 | 采纳：§5.3 用读侧过滤保立即性 + 异步清理 + `clear_tenant` 列表；§6.1 补 generation 检查与 `source_missing` 语义 |
| 6 | P1 | 采纳并更正：§4.5 更正 payload 为版本前缀行、`utterance` 字段；§6.3 毫秒截断到秒；来源判定改为读侧按 `adapter_name` |
| 7 | P1 | 采纳：§4.2 时间三重界下推、k×3 回填、去重键改为含 session/turn 元数据 |
| 8 | P1 | 采纳：§5.4 补全嵌入生命周期（产生、驱动、背填、重试、模型变更、重建、增量语义），表补 `retry_count`/`last_attempt_at` |
| 9 | P2 | 采纳：§5.2 明确新增 `SourceVectorIndex` 抽象（不复用 `VectorIndex`），并写明全量扫描成本与依赖注入 |
| 10 | P1 | 采纳：§5.4 + §4.6 增加降级可见性（`source_partial`）与覆盖回执；**待评审**：是否需要授权回退或显式"不完整检索"结果 |
| 11 | P1 | 采纳：§4.5 多行原文 JSON 转义，保留 `neutralize_recall_fence` |
| 12 | P2 | 采纳：§6.2 新增 `clean_turns_ts()` 不改 `chunk_dialogue` 签名并记录清洗损失；§6.4 更正"其他来源可召回"的错误；§2 更正 completion 模式走 `PatternCompletor` |
| 13 | P2 | 采纳：§8 `render_time` 默认改为 `false`；兼容性主张收窄；枚举追加在末尾但要求审计自省代码 |
| 14 | P2 | 采纳：§4.3 更正 RRF 理由（名次而非分数）、删除不存在的 `min_source_items`、§11 更正进攻判据与预算口径、§3 照搬父 spec 的 intent 限制 |

## 14. 待实施前确认

1. **§7 的授权方案 A/B/C**（是否引入 session scope）——这条决定左脑是否还是"跨会话通用记忆"。
2. **§4.4** 三个语句侧否决条件在 source 有命中时是否仍应拒答（v2 选了保守：仍拒答）。
3. **§5.4** 嵌入重试耗尽（3 次）后永久 failed 是否可接受，或需要"授权回退 + 显式不完整检索"。
4. **迁移编号 `0037`** 是否与其他在途工作冲突。
