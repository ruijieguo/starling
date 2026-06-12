# Retrieval Planner

## 功能定义

Retrieval Planner 是视角感知检索与心智摘要子系统。它按 `(querier, perspective, intent, goal)` 四元组重构 Context Pack，不是工具堆的 fan-out 封装。对外可见效果上它是纯读模块：不直接修改 Statement state，只以 fire-and-forget 方式 emit `statement.recalled` 事件，由 [Reconsolidation Engine](v24_11_reconsolidation.md) 异步消费决定是否开窗。

---

## 输入

- query(querier, perspective, intent, goal) 调用
- 9 种 QueryIntent 之一（FACT_LOOKUP / BELIEF_OF_OTHER / META_BELIEF / HISTORY / COMMITMENT_DUE / PREFERENCE / NORM_LOOKUP / COMMON_GROUND / ABSTAIN_CHECK）
- holder 子图查询（来自 Neocortex）
- KnowledgeFrontier 遮蔽规则（来自 Cognizer Hub）
- CommonGround 共识池快照（来自 Neocortex）

## 输出

- Context Pack（8 标签：FACT / BELIEF / HEARSAY / INFERRED / COMMON / TODO / CONFLICT / ABSTAIN）
- RetrievalReceipt（trace_id / query_id / filters_applied / candidate_counts / evidence_erased_count / sufficiency_status）
- statement.recalled 事件（fire-and-forget，触发 Reconsolidation 异步开窗判定）
- Abstention 决策（拒答原因：max_score < τ_recall / perspective frontier 不允许 / 唯一证据来自 RECANTED 链 / 冲突未仲裁）

---

## 主要流程

### P1 basic_retrieve 闭环

```
basic_retrieve(holder=self, intent=FACT_LOOKUP, subject, predicate, as_of=now())
  → 只查 Statement 主表轻量索引 (holder, consolidation_state, valid_from, valid_to)
  → 只返回 consolidation_state ∈ {CONSOLIDATED, ARCHIVED}
  → 过滤 review_status ∈ {REJECTED, PENDING_REVIEW}
  → 过滤 EvidenceRef.status = ERASED
  → 不做 rerank / ToM / CommonGround
  → 返回 list[Statement]（附 evidence hash / source metadata）
```

约束：`basic_retrieve` 只支持单 holder。传入多 holder 必须拒绝（或显式拆分调用），不得 silently broaden scope。

### P3 完整 7 步规划

```
1. parse   → Query → intent + 关键 entity
2. mask    → 按 perspective 的 KnowledgeFrontier 遮蔽不可见证据（EnigmaToM iterative masking）
3. plan    → 按 intent 选择路径（见 Intent→Path 映射）
4. fetch   → 并发多源（向量 / 图 / KG / EngramStore / Working Set / ToM API）
             fetch 完成后异步 emit statement.recalled × N（Bus 防抖合并）
5. fuse    → 按 holder 子图 + salience + recency 重排；Affect-aware Reranker
6. ground  → 检查 CommonGround，标"已 grounded"以便复述抑制
7. abstain → Abstention Gate（max_score / frontier / RECANTED / conflict 四条件）
```

step 4 fetch 完成后，**异步** emit `statement.recalled`，Retrieval 主流程不等待。Reconsolidation Engine 异步判定是否开窗（频繁召回短窗口内 ≥ K 次、或与近期 `belief.conflict` 同 key 则开窗；否则只升软 activation）。

### 多 holder 隔离

多 holder 检索时，Planner 必须为每个 holder 构建独立 substrate context，分别执行 fetch，再在 fuse 阶段合并。

规则：
- 每个子查询 filters 必须包含单一 `tenant_id + holder_scope/group_scope`，并写入 `RetrievalReceipt.filters_applied`。
- 并发度受 `ScopedWorkGate(lane=retrieval)` 限制；某 holder 失败只降级该 scope，不扩大到无 scope fallback。
- fuse/merge 阶段只处理 StatementRef / score / metadata，不得重新打开未授权 Engram raw 内容。

### statement.recalled emit 契约

- fire-and-forget，Retrieval 主流程不阻塞。
- Bus 防抖合并同 key 的重复事件。
- 同一 `(querier, perspective, intent, text, time)` 在 2s 内多次调用，返回相同结果，事件去重（幂等窗口）。
- `access_count` 是 in-memory 软统计，由 Replay Scheduler 周期批量 flush 到 Statement，非每次召回即写库。

### Abstention 触发条件

```
abstain if:
    max_score < τ_recall                   # 召回分低于阈值
    OR perspective frontier 不允许该信息   # KnowledgeFrontier 硬约束
    OR 唯一证据来自已 RECANTED 链
    OR conflict 未仲裁（请求澄清，而非赌一边）
```

abstain 时输出结构化"我不知道，因为 ___"，而非编造或模糊的"不确定"。

### 渐进式 scope 计划

Progressive plan 先查低成本 scope（`working_set / statement_main / projection_index`）；若 `sufficiency_status=SUFFICIENT` 且 stop\_policy 允许，跳过 `graph_index / semantic_index / engram_evidence`。跳过的 scope 必须写入 `skipped_scopes` 与 `stop_reason`，不得让 Receipt 看起来像全量检索。

### Intent → Path 映射

| Intent | 主路径 | 辅助 |
|---|---|---|
| FACT\_LOOKUP | Neocortex Semantic（holder=self）+ EngramStore 证据 | Working Set |
| BELIEF\_OF\_OTHER | Neocortex Semantic（holder=target） | EngramStore 中 target 发言 |
| META\_BELIEF | 嵌套 Statement（nesting\_depth=2） | perspective\_take 即时构建 |
| HISTORY | 时间索引 + supersedes 链 | EngramStore time-window |
| COMMITMENT\_DUE | Prospective Loop 队列 | — |
| PREFERENCE | Persona.preferences | PREFERS 类 Statement |
| NORM\_LOOKUP | Norms 子区 + scope 过滤 | enforcement\_history |
| COMMON\_GROUND | CommonGround pool（parties=...） | — |
| ABSTAIN\_CHECK | 跨子区低召回判定 + 校准置信度 | KnowledgeFrontier |

---

## 核心算法

### 1. perspective filter 位序

perspective filter 必须在语义排序之前执行。这是隐私边界硬约束，不可绕过。`filters_applied` 必须能证明 perspective filter 与 tenant/holder scope 已执行，否则结果不得返回。

### 2. Affect-aware Reranker

```python
def rerank(candidates, querier_state):
    for c in candidates:
        c.score = (
            base_relevance(c)
            * (1 + 0.3 * recency_factor(c))
            * (1 + 0.4 * c.salience)
            * (1 + 0.3 * activation_level(c))
            * affect_consistency(c.affect, querier_state.affect)
            * (1 - temporal_distance_penalty(c, query_time))
        )
    return sorted(candidates, key=lambda c: -c.score)
```

`affect_consistency` 对情感一致性加权；`temporal_distance_penalty` 对距查询时间锚点远的 triplet 降权（借鉴 cognee temporal\_retriever）。

P3 可升级为三级 RRF 融合（Topic → Episode → Fact），使用 vector-anchored fusion：

```python
score = alpha * vector_score_or_floor + (1 - alpha) * bm25_saturated_or_floor
# 默认 alpha=0.7, saturation_k=5.0
```

最终 score breakdown 必须写入 RetrievalReceipt。

### 3. Context Pack 8 标签判定

| 标签 | 语义 |
|---|---|
| FACT | 已建立共识，持有者确认 |
| BELIEF | 某方视角下的信念，含置信度 |
| HEARSAY | 单一来源，可能过时 |
| INFERRED | 基于行为模式推断 |
| COMMON | 所有 party 共同知道 |
| TODO | 待办承诺，含 deadline |
| CONFLICT | 多方陈述矛盾，待澄清 |
| ABSTAIN | 无可靠记忆，主动拒答 |

LLM 接收到的不是无差别文本块，而是已分类、归因、置信度标注的语用结构。

Context Pack 示例：

```
[FACT]    Bob 当前负责 auth（Alice 在 4/15 群聊宣布，共识已建立）
[BELIEF]  据 Carol 所知，新方案下周一上线（置信 0.7，但 Bob 暂未确认）
[HEARSAY] 我听 Alice 说 Bob 上周休假（单一来源，可能过时）
[INFERRED]根据 Bob 长期工作模式，他可能晚于 deadline 交付
[COMMON]  我们都知道：本季度目标是发布 v2
[TODO]    你 3/12 答应给 Alice 看代码（还有 2 天）
[CONFLICT]关于 X 的负责人：Alice 认为是 Bob，Carol 认为是 Dave，待澄清
[ABSTAIN] 关于 Y 的最新进展：无可靠记忆（Bob 上次提及在 2 月，之后无更新）
```

### 4. Abstention Gate 输出

输出结构化"我不知道，因为 ___"。四条件任意一条满足即触发：低召回分、frontier 不允许、唯一证据 RECANTED、冲突未仲裁。

### 5. RetrievalReceipt 合法性约束

- `filters_applied` 必须能证明 perspective filter 与 tenant/holder scope 已执行，否则结果不得返回。
- projection lag 超过 §4.1 SLA 时，必须记录 `degraded_paths` 与 fallback；无 fallback 则 Context Pack 加 `[ABSTAIN]` 或 stale 标记。
- `score_breakdown` 只记录可审计分数与 StatementRef，不泄露被遮蔽证据正文。
- `sufficiency_status` 四态：`SUFFICIENT / MISSING_INFO / NEEDS_RAW / ABSTAINED`。`NEEDS_RAW` 必须先通过 retention/visibility 检查，gate 失败则 `ABSTAINED`。

### 6. filter 混合形式拒绝规则

禁止同一 plan 同时使用全局 filter 又让部分 scope 自带不同 holder/group。这种混合形式必须拒绝，写入 `RetrievalReceipt.abstention_reason=invalid_scope_filter_mix`。

### 7. 幂等与 access_count flush

- 同 `(querier, perspective, intent, text, time)` 在 2s 内多次调用，返回相同结果，事件去重。
- `access_count` 是 in-memory 软统计，通过 Replay Scheduler 周期批量 flush，非每次召回写库。

---

## 数据结构

### QueryIntent 枚举（9 种）

```python
class QueryIntent(Enum):
    FACT_LOOKUP        # 查事实
    BELIEF_OF_OTHER    # 查 X 相信什么
    META_BELIEF        # 查 X 以为 Y 知道什么（二阶，深度上限受 ToMDepthEstimator 调制）
    HISTORY            # 查时间线
    COMMITMENT_DUE     # 查待办
    PREFERENCE         # 查偏好
    NORM_LOOKUP        # 查规范
    COMMON_GROUND      # 查共识
    ABSTAIN_CHECK      # 主动检查"是否真的不知道"
```

### Query 输入

```python
class Query:
    querier:      CognizerRef               # 谁在问（默认 self）
    perspective:  CognizerRef               # 从谁的视角检索（默认 = querier）
    intent:       QueryIntent
    text:         str
    time:         datetime                  # 检索时间锚（as_of）
    goal_context: Optional[GoalRef]
```

### basic_retrieve 函数签名（P1）

```python
def basic_retrieve(
    holder:    CognizerRef,         # 仅支持单 holder，多 holder 必须拒绝
    intent:    QueryIntent,         # P1 固定 FACT_LOOKUP
    subject:   str,
    predicate: str,
    as_of:     datetime,
) -> list[Statement]:
    ...
```

### RetrievalScopeStep / RetrievalScopePlan（P3）

```python
class RetrievalScopeStep(BaseModel):
    scope: Literal[
        "working_set", "statement_main", "projection_index",
        "semantic_index", "graph_index", "container_view",
        "engram_evidence", "tom_runtime"
    ]
    adapter_scope:  Optional[str]           # 外部库原生 scope，仅作 metadata
    holder_scope:   Optional[CognizerRef]
    group_scope:    Optional[str]
    filters:        dict
    max_candidates: int
    on_error:       Literal["degrade","abstain","fail_closed"]

class RetrievalScopePlan(BaseModel):
    plan_id:      str
    mode:         Literal["basic","progressive","parallel","exhaustive"]
    steps:        list[RetrievalScopeStep]
    stop_policy:  Literal["after_first_sufficient","merge_all",
                           "needs_raw_gate","abstain_on_gap"]
    merge_policy: Literal["ranked_union","intersection",
                           "priority_order","rrf"]
    filter_mode:  Literal["global_inherited","per_scope_explicit"]
```

注：P1 不需要创建 `RetrievalScopePlan` 对象，Receipt 可用固定字段记录 `scope="statement_main"`、filters、candidate\_counts 与 sufficiency。

### Affect-aware Reranker 输入输出

```python
# 输入
candidates:    list[StatementCandidate]   # 含 base_relevance / salience / affect
querier_state: CognizerState              # 含 affect 向量

# 输出
list[StatementCandidate]                  # 按 score 降序排列，score breakdown 写入 RetrievalReceipt
```

### RetrievalReceipt（P1 最小字段加粗，完整结构如下）

```python
class RetrievalReceipt(BaseModel):
    trace_id:             str                 # P1 必填
    query_id:             str                 # P1 必填
    querier:              CognizerRef
    perspective:          CognizerRef
    intent:               QueryIntent
    runtime_health:       Literal["READY","DEGRADED","DRAINING","UNREADY"]
    trace_retention:      Literal["metadata_only","hash_only",
                                  "redacted_debug","full_debug"]
    sanitized_query:      Optional[dict]      # method/original_length/clean_length
    sufficiency_status:   Literal["SUFFICIENT","MISSING_INFO",
                                  "NEEDS_RAW","ABSTAINED"]
    scope_plan:           Optional[RetrievalScopePlan]
    plan_steps:           list[dict]          # parse/mask/plan/fetch/fuse/ground/abstain
    skipped_scopes:       list[dict]          # scope + reason + stop_policy
    stop_reason:          Optional[str]
    projection_lag:       dict                # per projection: lag_seconds/sequence_delta/stale
    scopes_searched:      list[str]
    filters_applied:      list[dict]          # P1 必填：holder/perspective/tenant/review/evidence erasure
    candidate_counts:     dict                # P1 必填：fetched/reranked/returned/dropped_by_mask/dropped_by_review
    score_breakdown:      list[dict]          # statement_id + base/vector/bm25/salience/recency/final
    evidence_erased_count: int                # P1 必填
    degraded_paths:       list[dict]          # path + reason + fallback
    abstention_reason:    Optional[str]
    emitted_events:       list[str]           # statement.recalled ids，或抑制时为空
```

P1 `basic_retrieve` 只需填 `trace_id / query_id / filters_applied / candidate_counts / evidence_erased_count`。

### Context Pack 8 标签

```python
ContextPackLabel = Literal[
    "FACT", "BELIEF", "HEARSAY", "INFERRED",
    "COMMON", "TODO", "CONFLICT", "ABSTAIN"
]
```

---

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

## 相关概念

**9 种 QueryIntent**
`FACT_LOOKUP / BELIEF_OF_OTHER / META_BELIEF / HISTORY / COMMITMENT_DUE / PREFERENCE / NORM_LOOKUP / COMMON_GROUND / ABSTAIN_CHECK`。覆盖事实、信念、二阶信念、时间线、承诺、偏好、规范、共识、主动拒答九类检索意图。

**7 步规划**
`parse → mask → plan → fetch → fuse → ground → abstain`。每步有明确输入输出，fetch 后异步 emit 事件，主流程不阻塞。

**perspective filter**
硬约束，必须在语义排序之前执行。依赖 [Cognizer Hub](v24_08_cognizer.md) 的 KnowledgeFrontier 实现 EnigmaToM iterative masking，决定哪些证据对当前 perspective 可见。

**Affect-aware Reranker**
在 base\_relevance 基础上乘以 recency、salience、activation、affect\_consistency、temporal\_distance\_penalty 五个因子。affect\_consistency 来自 [AffectVector](../04_starling_design_v17.md#数据本体) 与 querier 当前情感状态的匹配程度。

**Context Pack 8 标签**
`FACT / BELIEF / HEARSAY / INFERRED / COMMON / TODO / CONFLICT / ABSTAIN`。Retrieval 输出不是无差别 RAG 文本，而是带语用标注的心智摘要，让 LLM 理解每条记忆的认识论地位。

**RetrievalReceipt**
每次检索生成一份回执，记录 scope、filter、候选数量、score breakdown、被遮蔽/删除证据计数、abstention 原因。`filters_applied` 必须能证明 perspective filter 与 tenant/holder scope 已执行，否则结果不得返回。评测体系可直接用 receipt 区分"没查到"、"被权限遮蔽"、"projection stale"、"主动 abstain"。

**Abstention（主动拒答，LongMemEval 关键失分项）**
四条件任意一满足即输出结构化"我不知道，因为 ___"：召回分低于 τ\_recall、perspective frontier 不允许、唯一证据来自 RECANTED 链、冲突未仲裁。不编造，不输出"不确定"。

**读副作用契约**
Retrieval Planner 不修改 Statement state，不直接写 confidence，不直接开 Reconsolidation 窗口，不改 supersedes 链。对外唯一副作用是 emit `statement.recalled`（fire-and-forget）。

**statement.recalled 异步契约**
`statement.recalled` 事件由 Bus 防抖合并，[Reconsolidation Engine](v24_11_reconsolidation.md) 异步消费。频繁召回（短窗口内 ≥ K 次）或与近期 `belief.conflict` 同 key 时开窗；否则只升软 activation，不开窗。Retrieval 主流程不等待。

**Mentalizing Primitives**
META\_BELIEF intent 的嵌套深度由 [Mentalizing Primitives](v24_09_tom.md) 的 ToMDepthEstimator 调制，防止无限递归二阶信念推断。

**basic\_retrieve（P1 闭环）**
P1 最简路径。只查 Statement 主表轻量索引，只返回 `CONSOLIDATED / ARCHIVED` 状态，过滤被拒绝与被删除证据，不做 rerank / ToM / CommonGround。验证目标是"Bus.append\_evidence → Extractor → Bus.write → direct state transition helper → basic\_retrieve"端到端可跑通。

**多 holder 隔离**
多 holder 检索为每个 holder 构建独立 substrate context 分别执行，fetch 后 fuse 阶段合并。P1 `basic_retrieve` 只支持单 holder。

**幂等窗口**
同 `(querier, perspective, intent, text, time)` 在 2s 内多次调用返回相同结果，`statement.recalled` 事件去重。

**access\_count flush**
in-memory 软统计，Replay Scheduler 周期批量 flush 到 Statement，不是每次召回即写库。

- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0

---

## 实现补记(2026-06-12 P3.a1)

P3.a1 交付:9 种 QueryIntent、7 步管线(`src/retrieval/retrieval_planner.cpp`,
每步写 receipt.plan_steps)、Affect-aware Reranker 五因子(`affect_reranker.cpp`,
breakdown 落 receipt.score_breakdown)、Abstention Gate 四条件(`abstention.cpp`,
优先级 frontier>recanted>conflict>score,τ_recall 默认 0.25 可配)、Context Pack
8 标签(`context_pack.cpp`,优先级 TODO>CONFLICT>COMMON>INFERRED>HEARSAY>
BELIEF>FACT,ABSTAIN 由 gate 注入整包)、Receipt 完整字段与 RetrievalScopePlan、
多 holder 隔离(per-step 单一 holder_scope + `invalid_scope_filter_mix` 拒绝)。
perspective mask:结构化路径 SQL 下推,语义路径取回后、rerank 前按
KnowledgeFrontier 可见集遮蔽(满足"排序之前"位序)。statement.recalled 由
planner 中心化 emit(键公式与 basic_retrieve 一致,拒答零事件)。入口:
`Memory.query()` / dashboard `POST /api/recall`(intent 非空)。

本期裁剪(后续里程碑):`sanitized_query`(P3.b 随 query 清洗)、三级 RRF/bm25
融合与多源并发 latency budget(P3.c)、`ScopedWorkGate(lane=retrieval)`(P3.c
治理)、`temporal_distance_penalty` 连续距离函数(v1 为有界惩罚:过期 0.3)。
META_BELIEF 的 ToMDepthEstimator 上限调制接线归 P3.a2(估计器已存在)。
