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

# Reconsolidation Engine

## 功能定义

Reconsolidation Engine 实现"被回忆即可塑"机制：`CONSOLIDATED` Statement 被召回或被冲突触发后进入 `REPLAYING_RECONSOLIDATING` 可塑窗口期，期间收到的支持或反对证据决定回归 `CONSOLIDATED`（confidence 调整）或 fork 新版本（severe path）。它不删旧版，旧版进 supersedes 链；轻微反对路径仅修改原 Statement 的 confidence 字段，不产生新版本，provenance 保持不变。

---

## 主要流程

### 触发五路径

Reconsolidation Engine 作为 [Statement Bus](v19_05_bus.md) 的异步 Subscriber，不被任何模块同步调用，所有触发均走异步事件。满足下列任意一条的 `CONSOLIDATED` 或 `ARCHIVED` Statement，异步进入 `REPLAYING_RECONSOLIDATING` 可塑窗口：

1. **statement.recalled**：由 Retrieval Planner emit；Retrieval 不直接开窗，异步处理。
2. **statement.references_existing**：被新输入的 Statement 通过 `derived_from` 引用时 emit。
3. **belief.conflict**：由 ConflictProbe emit。
4. **显式 reconsolidate API**：audit 或用户编辑场景直接调用。
5. **commitment.fulfilled / commitment.broken**：影响相关 Commitment Statement 的 confidence。

### 窗口锁机制

同一 `stmt_id` 同时只允许一个活跃窗口。窗口已开启时，新触发不开新窗口，只追加证据到现有窗口的 `pending_evidence` 队列（防抖）。窗口 close 时统一仲裁，减少争用与重入风险。

### 窗口 close 时仲裁：三种结果路径

窗口关闭后，`aggregate_evidence` 默认处理最近 50 条高权重证据，其余作为低权重背景统计输入，然后按以下路径仲裁：

```
supports(aggregated, stmt)
  → confidence 贝叶斯上调
  → stmt.consolidation_state = CONSOLIDATED
  → emit statement.consolidated（生命周期信号）

mild contradict(aggregated, stmt)
  → confidence 贝叶斯下调（原 Statement 原地修改）
  → provenance 保持原值不变
  → 追加 confidence_history 记录
  → stmt.consolidation_state = CONSOLIDATED
  → emit statement.consolidated（生命周期信号；不 emit statement.corrected）

severe contradict(aggregated, stmt)
  → 四项原子提交（见下文）
```

### severe path：四项原子提交

local-lite 走原子事务；cloud-graphiti（`cross_partition_transaction=false`）走 saga 补偿。

原子提交四项不变量（必须同事务，缺一不可）：

1. 写入新版 Statement（`provenance=reconsolidation_derived`，`consolidation_state=CONSOLIDATED`）
2. 写入 `SUPERSEDES` 边（新版 → 旧版）
3. 旧版 `consolidation_state` 改 `ARCHIVED`
4. emit `statement.corrected` + `statement.archived` + `statement.superseded`（同 outbox batch）

新版不走 `tom_inferred`，不进入 `VOLATILE`，不 emit `statement.written`（防止重入 Replay）。

若 `review_status_for(aggregated) = REVIEW_REQUESTED`，新版仍可进入 holder 子图，但 Context Pack 必须标注 `REVIEW_REQUESTED`，不得作为无条件 FACT 输出。

### saga 补偿步骤（cloud-graphiti）

```
步骤 1 → 写入新版 Statement（reconsolidation_derived，CONSOLIDATED）
步骤 2 → 写入 SUPERSEDES 边（新版 → 旧版）
步骤 3 → 旧版 state 改 ARCHIVED
步骤 4 → emit statement.corrected + statement.archived + statement.superseded

失败回滚顺序：
  步骤 1 失败 → 无副作用，直接报错
  步骤 2 失败 → 删除步骤 1 新版，emit reconsolidation.compensated
  步骤 3 失败 → 删除步骤 1 新版 + 步骤 2 边，emit reconsolidation.compensated
  步骤 4 失败 → 已写入数据保留，audit log + Ops 告警（数据一致但事件未发，需手动重发）
```

补偿成功后，旧版保持 `CONSOLIDATED`，系统语义不变。

### pending_evidence 容量管理

- 单窗口最多 100 条，超过后按时间戳 FIFO 淘汰，保留被淘汰数量与摘要 hash 供审计。
- 同一窗口触发超过 K 次（默认 K=10）后强制 close 并仲裁，后续事件排入下一窗口或被防抖合并。
- 高频对象（`access_count` 或触发频率超过阈值）窗口自动缩短至 5 分钟，防止长期占用队列。
- 容量淘汰、强制 close 均须 emit audit metadata，无需额外用户可见事件。

---

## 核心算法

### 可塑窗口超时

默认 30 分钟，自适应范围 5 分钟到 6 小时（参考 Nader 2000 神经科学 6h 上限），按 modality 与更新频率动态调整。高频对象强制上限 5 分钟。

### mild correction provenance 不变规则

```python
# mild contradict 路径，原 Statement 原地修改
stmt.confidence = bayesian_update_down(stmt.confidence, aggregated.strength)
stmt.consolidation_state = CONSOLIDATED
stmt.confidence_history.append(ConfidenceEvent(
    old_value=old_confidence,
    ts=now_utc(),
    evidence_summary_hash=hash(aggregated.summary),
))
# provenance 字段不写，保持原值：
#   user_input 经多轮 mild correction 后 provenance 仍是 user_input
#   不变为 reconsolidation_derived
```

设计理由：轻微 confidence 调整高频发生，若每次产生新版本会让 supersedes 链被动拉长 O(N)，也违反 provenance 不变量。`confidence_history` 提供审计轨迹替代版本号。

### severe contradict 四项原子提交（伪代码）

```python
def reconsolidate_severe(stmt, aggregated, tx):
    new_version = stmt.fork(modifications=delta_from(aggregated))
    new_version.supersedes = stmt.id
    new_version.provenance = "reconsolidation_derived"
    new_version.review_status = review_status_for(aggregated)
    new_version.consolidation_state = CONSOLIDATED

    Validator.check(new_version)
    ConflictProbe.scan(new_version)

    tx.upsert_statement(new_version)                            # 步骤 1
    tx.upsert_edge(new_version.id, "SUPERSEDES", stmt.id)      # 步骤 2
    stmt.consolidation_state = ARCHIVED
    tx.upsert_statement(stmt)                                   # 步骤 3
    tx.outbox_append("statement.corrected",  {"old": stmt, "new": new_version})
    tx.outbox_append("statement.archived",   stmt)
    tx.outbox_append("statement.superseded", {"old": stmt, "new": new_version})  # 步骤 4
    # 不 emit statement.written，不走 tom_inferred，不进 VOLATILE
```

### saga 补偿状态机

```
状态：PENDING → STEP1_DONE → STEP2_DONE → STEP3_DONE → COMMITTED
                                                       ↘ COMPENSATED（任一步失败后回滚至此）
```

回滚顺序严格逆序：步骤 4 幂等重试（outbox 重发）；步骤 3 失败删步骤 1+2；步骤 2 失败删步骤 1；步骤 1 失败无副作用。

### 多主体并发仲裁

多条相关 Statement 并发进入 `REPLAYING_RECONSOLIDATING` 是允许的（例：关于同一主体的多条 Statement 同时被召回）。但跨 Statement 的并发仲裁可能产生互相矛盾的修正。当前设计不做跨窗口锁；调用方须在仲裁后由 ConflictProbe 扫描新版本集合，由下一个 Bus 周期处理潜在冲突。

---

## 数据结构

### PlasticWindow（可塑窗口元数据）

```python
@dataclass
class PlasticWindow:
    stmt_id: str                        # 目标 Statement ID
    opened_at: datetime                 # 窗口开启时间（UTC）
    close_deadline: datetime            # 超时关闭时间（opened_at + adaptive_timeout）
    trigger_event_ids: list[str]        # 触发本窗口的事件 ID 列表（审计用）
    pending_evidence: deque             # 最多 100 条，FIFO 淘汰
    force_close_trigger_count: int      # 已触发次数，达 K=10 后强制 close
    evicted_count: int                  # 已淘汰条数（审计）
    evicted_summary_hashes: list[str]   # 被淘汰证据的摘要 hash（审计）
```

### PendingEvidence（队列元素）

```python
@dataclass
class PendingEvidence:
    event_id: str
    event_type: str          # statement.recalled | belief.conflict | ...
    source_stmt_id: str | None
    payload_hash: str        # 证据摘要 hash，避免存储原始 payload
    weight: float            # 证据权重（Retrieval Planner 或 ConflictProbe 提供）
    arrived_at: datetime
```

### ConfidenceEvent（confidence_history 元素）

```python
@dataclass
class ConfidenceEvent:
    old_value: float
    new_value: float
    ts: datetime
    evidence_summary_hash: str   # 触发本次调整的证据摘要 hash
    path: Literal["mild_support", "mild_contradict"]
```

`confidence_history` 字段类型：`list[ConfidenceEvent]`，存为 JSON 数组，追加写入，不覆盖历史。

### ReconsolidationResult（仲裁结果事件 schema）

```python
# supports 或 mild contradict → emit statement.consolidated
{
  "event": "statement.consolidated",
  "stmt_id": str,
  "path": "supports" | "mild_contradict",
  "confidence_delta": float,
  "window_id": str,
}

# severe contradict → emit 三条事件（同 outbox batch）
{
  "event": "statement.corrected",
  "old_stmt_id": str,
  "new_stmt_id": str,
  "window_id": str,
}
{
  "event": "statement.archived",
  "stmt_id": str,          # 旧版 ID
  "window_id": str,
}
{
  "event": "statement.superseded",
  "old_stmt_id": str,
  "new_stmt_id": str,
  "window_id": str,
}

# saga 补偿 → emit reconsolidation.compensated
{
  "event": "reconsolidation.compensated",
  "stmt_id": str,
  "failed_step": int,      # 1-4
  "window_id": str,
  "error": str,
}
```

### SagaState（补偿状态机）

```python
class SagaState(Enum):
    PENDING     = "pending"
    STEP1_DONE  = "step1_done"   # 新版写入完成
    STEP2_DONE  = "step2_done"   # SUPERSEDES 边写入完成
    STEP3_DONE  = "step3_done"   # 旧版 ARCHIVED 完成
    COMMITTED   = "committed"    # outbox batch 写入完成
    COMPENSATED = "compensated"  # 回滚完成

@dataclass
class SagaRecord:
    window_id: str
    stmt_id: str
    new_stmt_id: str | None
    state: SagaState
    failed_step: int | None
    started_at: datetime
    finished_at: datetime | None
```

---

## 相关概念

### 术语

| 术语 | 说明 |
|---|---|
| `REPLAYING_RECONSOLIDATING` | Statement 状态机中的可塑窗口状态，详见 [Statement Bus](v19_05_bus.md) 状态机定义。 |
| 可塑窗口 | Statement 进入可塑状态后的时间窗口，默认 30 分钟，自适应 5 分钟到 6 小时。 |
| `pending_evidence` | 窗口期内积累的证据队列，窗口 close 时批量仲裁。 |
| mild correction | 轻微反对路径：原 Statement confidence 下调，provenance 不变，不产新版，不进 supersedes 链。 |
| severe contradict | 强烈反对路径：原子提交新版 + 旧版 ARCHIVED + SUPERSEDES 边 + outbox 三事件。 |
| supersedes 链 | 历次 severe correction 形成的版本有向链，旧版进入 `ARCHIVED` 但不删除。 |
| saga 补偿 | `cross_partition_transaction=false` 时（cloud-graphiti）用于替代原子事务的逐步提交+逆序回滚机制。 |
| `reconsolidation_derived` | severe path 新版的 provenance 值；mild correction 不产生此 provenance。 |
| `confidence_history` | Statement 字段，JSON 数组，记录每次 mild correction 的前值、时间戳、证据 hash。 |

### 与现有系统对照

- **mem0**：UPDATE 直接覆盖，旧值消失，无可追溯历史。
- **Letta**：GitEnabledBlockManager 保有版本历史，但不区分"是否被回忆触发"；sleeptime 触发基于简单 turns_counter 取模，无 salience 或 conflict 优先级。
- **Starling**：只有被回忆（或冲突、commitment 等五路径之一）才能改；改完不删旧版，轻微调整走 `confidence_history`，强烈反对走 supersedes 链，这是大脑可塑性的工程模拟。

### 交叉引用

- [Statement Bus](v19_05_bus.md)：`REPLAYING_RECONSOLIDATING` 状态定义、`cross_partition_transaction` 标志、Bus Subscriber 契约。
- [Replay Scheduler](v19_10_replay.md)：`replay_derived` 与 `reconsolidation_derived` 的区别（前者由定期 Replay 产生，后者由 Reconsolidation Engine 的 severe path 产生；新版不 emit `statement.written`，防止 Replay Scheduler 将其重入 Replay 流程）。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
