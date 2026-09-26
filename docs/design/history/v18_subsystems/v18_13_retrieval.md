<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Retrieval Planner

## 功能定义

Retrieval Planner 是视角感知检索与心智摘要子系统。它按 `(querier, perspective, intent, goal)` 四元组重构 Context Pack，不是工具堆的 fan-out 封装。对外可见效果上它是纯读模块：不直接修改 Statement state，只以 fire-and-forget 方式 emit `statement.recalled` 事件，由 [Reconsolidation Engine](v18_11_reconsolidation.md) 异步消费决定是否开窗。

---

## 主要流程

### P0 basic_retrieve 闭环

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

### P4 完整 7 步规划

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

P4 可升级为三级 RRF 融合（Topic → Episode → Fact），使用 vector-anchored fusion：

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

### basic_retrieve 函数签名（P0）

```python
def basic_retrieve(
    holder:    CognizerRef,         # 仅支持单 holder，多 holder 必须拒绝
    intent:    QueryIntent,         # P0 固定 FACT_LOOKUP
    subject:   str,
    predicate: str,
    as_of:     datetime,
) -> list[Statement]:
    ...
```

### RetrievalScopeStep / RetrievalScopePlan（P4）

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

注：P0/P1 不需要创建 `RetrievalScopePlan` 对象，Receipt 可用固定字段记录 `scope="statement_main"`、filters、candidate\_counts 与 sufficiency。

### Affect-aware Reranker 输入输出

```python
# 输入
candidates:    list[StatementCandidate]   # 含 base_relevance / salience / affect
querier_state: CognizerState              # 含 affect 向量

# 输出
list[StatementCandidate]                  # 按 score 降序排列，score breakdown 写入 RetrievalReceipt
```

### RetrievalReceipt（P0 最小字段加粗，完整结构如下）

```python
class RetrievalReceipt(BaseModel):
    trace_id:             str                 # P0 必填
    query_id:             str                 # P0 必填
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
    filters_applied:      list[dict]          # P0 必填：holder/perspective/tenant/review/evidence erasure
    candidate_counts:     dict                # P0 必填：fetched/reranked/returned/dropped_by_mask/dropped_by_review
    score_breakdown:      list[dict]          # statement_id + base/vector/bm25/salience/recency/final
    evidence_erased_count: int                # P0 必填
    degraded_paths:       list[dict]          # path + reason + fallback
    abstention_reason:    Optional[str]
    emitted_events:       list[str]           # statement.recalled ids，或抑制时为空
```

P0 `basic_retrieve` 只需填 `trace_id / query_id / filters_applied / candidate_counts / evidence_erased_count`。

### Context Pack 8 标签

```python
ContextPackLabel = Literal[
    "FACT", "BELIEF", "HEARSAY", "INFERRED",
    "COMMON", "TODO", "CONFLICT", "ABSTAIN"
]
```

---

## 相关概念

**9 种 QueryIntent**
`FACT_LOOKUP / BELIEF_OF_OTHER / META_BELIEF / HISTORY / COMMITMENT_DUE / PREFERENCE / NORM_LOOKUP / COMMON_GROUND / ABSTAIN_CHECK`。覆盖事实、信念、二阶信念、时间线、承诺、偏好、规范、共识、主动拒答九类检索意图。

**7 步规划**
`parse → mask → plan → fetch → fuse → ground → abstain`。每步有明确输入输出，fetch 后异步 emit 事件，主流程不阻塞。

**perspective filter**
硬约束，必须在语义排序之前执行。依赖 [Cognizer Hub](v18_08_cognizer.md) 的 KnowledgeFrontier 实现 EnigmaToM iterative masking，决定哪些证据对当前 perspective 可见。

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
`statement.recalled` 事件由 Bus 防抖合并，[Reconsolidation Engine](v18_11_reconsolidation.md) 异步消费。频繁召回（短窗口内 ≥ K 次）或与近期 `belief.conflict` 同 key 时开窗；否则只升软 activation，不开窗。Retrieval 主流程不等待。

**Mentalizing Primitives**
META\_BELIEF intent 的嵌套深度由 [Mentalizing Primitives](v18_09_tom.md) 的 ToMDepthEstimator 调制，防止无限递归二阶信念推断。

**basic\_retrieve（P0 闭环）**
P0 最简路径。只查 Statement 主表轻量索引，只返回 `CONSOLIDATED / ARCHIVED` 状态，过滤被拒绝与被删除证据，不做 rerank / ToM / CommonGround。验证目标是"Bus.append\_evidence → Extractor → Bus.write → direct state transition helper → basic\_retrieve"端到端可跑通。

**多 holder 隔离**
多 holder 检索为每个 holder 构建独立 substrate context 分别执行，fetch 后 fuse 阶段合并。P0 `basic_retrieve` 只支持单 holder。

**幂等窗口**
同 `(querier, perspective, intent, text, time)` 在 2s 内多次调用返回相同结果，`statement.recalled` 事件去重。

**access\_count flush**
in-memory 软统计，Replay Scheduler 周期批量 flush 到 Statement，不是每次召回即写库。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
