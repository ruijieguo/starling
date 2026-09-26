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

# Prospective Loop

## 功能定义

Prospective Loop 实现"前瞻"，在没有用户 query 的情况下主动想起承诺、触发提醒、检测履行或违约。它承担四项职责：（1）Trigger 类型系统；（2）Commitment 五态机；（3）ActionGuard 动作护栏；（4）Norm 监听。所有 Trigger 命中均经 [Statement Bus](v18_05_bus.md) emit `commitment.fire`，PolicyEngine 不绕过 Bus 直接调用消费者。

## 主要流程

### 1. Commitment 创建

`modality=COMMITS` 的 Statement 经 Validator 通过后，Bus 自动将其状态由 `created` 转为 `ACTIVE`。转 ACTIVE 时 PolicyEngine emit `commitment.active_holding(commitment_id, related_stmt_ids)`，通知 [Replay Scheduler](v18_10_replay.md) decay scheduler 将关联 stmt_id 加入 in-memory 保护集，阻止相关 Statement 被 ARCHIVED。

### 2. Trigger 命中

PolicyEngine 内部维护 Trigger Index 与时间堆，持续监听四类 Trigger。命中条件满足时经 `Bus.emit("commitment.fire", ...)` 发布事件；Working Set 随即注入 `pending_commitments` block，作为对话上下文的提醒插槽。

### 3. ACTIVE 保护

`commitment.active_holding` 的 Consumer 是 Replay decay scheduler。scheduler 在 in-memory set 中持有被保护的 stmt_id 集合，decay 选取候选时 O(1) 排除集合内 Statement，执行 §3.4 例外条款"未结清 Commitment 不允许相关 Statement 进入 ARCHIVED"。

### 4. 终态释放

Commitment 转 `FULFILLED` 或 `WITHDRAWN` 时，emit `commitment.released(commitment_id)`，decay scheduler 从保护集移除对应 stmt_id，解除 ARCHIVED 约束。

### 5. RENEGOTIATED 链长限制

supersedes 链长 `>= 3` 时，Validator 拒绝新的 RENEGOTIATED 请求，emit `commitment.renegotiation_blocked`，要求调用方先执行 WITHDRAWN 再重新 COMMIT。这使 supersedes 链 O(N) 展开成本（ToM 推断、衰减公式）保持可控，上限 3 次协商已覆盖绝大多数现实场景。

### 6. BROKEN 计数自动 WITHDRAWN

同一 `commitment_id` 累计进入 BROKEN 状态 `>= MAX_BROKEN_COUNT`（默认 3）次后，下一次 deadline 过期不再转 BROKEN，而是自动转 WITHDRAWN，emit `commitment.auto_withdrawn(reason="chronic_failure")`。同步触发 [Cognizer Hub](v18_08_cognizer.md) 中对应 holder 的 `trust_priors` 下调（具体公式见 §8.3）。设计意图：防止单一 commitment_id 长期占用 supersedes 链与 Replay 资源，语义上反映"反复失信后系统不再跟踪"。

### 7. dispatcher 重启 boot replay

dispatcher 重启时必须重放最近 7 天内的 `commitment.active_holding` 和 `commitment.released` 事件，重建 in-memory 保护集。若跳过此步骤，未结清 Commitment 关联的 Statement 可能被误 ARCHIVED（critical failure mode，见测试 TC-A9-003）。

## 核心算法

### 1. Commitment 五态机完整迁移表

```
created
  └─ Validator 通过 → ACTIVE  (emit commitment.active_holding)

ACTIVE
  ├─ user 履行          → FULFILLED       (emit commitment.fulfilled)
  │                                        (emit commitment.released)
  ├─ deadline 过期       → BROKEN         (emit commitment.broken)
  │   └─ 累计 >= MAX_BROKEN_COUNT 次后
  │      下次 deadline → WITHDRAWN        (emit commitment.auto_withdrawn)
  ├─ 双方协商           → RENEGOTIATED    (emit commitment.renegotiated)
  │   └─ 新版 supersedes 旧；链长 >= 3 时 Validator 拒绝
  └─ 主动撤回           → WITHDRAWN       (emit commitment.withdrawn)
                                           (emit commitment.released)

BROKEN
  └─ 双方协商           → RENEGOTIATED    (emit commitment.renegotiated)
     (旧 BROKEN 保留，新 RENEGOTIATED 经 supersedes 链关联)

FULFILLED / WITHDRAWN  →  终态，不可再迁移
```

状态迁移规则：

| 迁移 | 触发条件 | 副作用 | emit 事件 |
|---|---|---|---|
| created → ACTIVE | Validator 通过 | PolicyEngine 注册 Trigger Index | `commitment.active_holding` |
| ACTIVE → FULFILLED | user 履行确认 | 清理 Trigger；Working Set 移除 block | `commitment.fulfilled`、`commitment.released` |
| ACTIVE → BROKEN | deadline 过期（未满 MAX_BROKEN_COUNT） | BROKEN 计数 +1 | `commitment.broken` |
| ACTIVE → BROKEN → auto-WITHDRAWN | deadline 过期且 BROKEN 计数 >= MAX_BROKEN_COUNT | trust_priors 下调 | `commitment.auto_withdrawn` |
| ACTIVE / BROKEN → RENEGOTIATED | 双方协商，链长 < 3 | 旧版打 supersedes；新版转 ACTIVE | `commitment.renegotiated` |
| ACTIVE / RENEGOTIATED → WITHDRAWN | 主动撤回 | 清理 Trigger；Working Set 移除 block | `commitment.withdrawn`、`commitment.released` |

### 2. RENEGOTIATED 链长上限算法

```python
def validate_renegotiation(commitment_id: str, store) -> bool:
    chain_len = store.supersedes_chain_length(commitment_id)
    if chain_len >= 3:
        bus.emit("commitment.renegotiation_blocked", {"commitment_id": commitment_id})
        return False
    return True
```

调用方需先执行 WITHDRAWN，再新建 Commitment，绕过链长限制重新开始计数。

### 3. BROKEN 计数累计与自动 WITHDRAWN 判定

```python
MAX_BROKEN_COUNT = 3

def on_deadline_expired(commitment_id: str, store, bus):
    broken_count = store.broken_count(commitment_id)
    if broken_count >= MAX_BROKEN_COUNT:
        store.transition(commitment_id, "WITHDRAWN")
        bus.emit("commitment.auto_withdrawn", {
            "commitment_id": commitment_id,
            "reason": "chronic_failure",
        })
        cognizer_hub.downgrade_trust_priors(store.holder(commitment_id))
    else:
        store.transition(commitment_id, "BROKEN")
        store.increment_broken_count(commitment_id)
        bus.emit("commitment.broken", {"commitment_id": commitment_id})
```

### 4. 四类 Trigger 命中判定

| Trigger 类型 | 命中条件 |
|---|---|
| `TimeTrigger(at=datetime)` | 系统时钟到达指定时刻 |
| `TimeTrigger(every="1d at 09:00")` | 每日循环，Trigger Index 时间堆轮询 |
| `EventTrigger(when=...)` | Bus 事件流中出现匹配事件（如 `cognizer:Alice.observed`、`statement.written: predicate=mentions, object=X`） |
| `StateTrigger(predicate=...)` | EngramStore 中指定谓词当前为真（如 `goal:onboarding.completed`） |
| `CompoundTrigger(all_of=[...])` | 子 Trigger 全部命中（AND 组合） |
| `CompoundTrigger(any_of=[...])` | 子 Trigger 任一命中（OR 组合） |

CompoundTrigger 递归嵌套，PolicyEngine 按深度优先顺序评估子节点，短路求值（all_of 遇到第一个未命中即停止）。

### 5. ActionGuard 三件套

P3 默认 ActionGuard：

```python
class ActionGuard(BaseModel):
    profile_name: str
    allowed_actions: set[str]       # 允许直接执行的动作名称集合
    requires_approval: set[str]     # 需要人工审批才能执行的动作名称集合
    idempotency_window: dict[str, timedelta]  # 每个动作的幂等窗口
```

执行规则：

- `commitment.fire` 默认仅将 pending reminder 注入 Working Set，不调用外部 tool。
- 调用外部 tool/action 须满足 `action_name in allowed_actions`。
- 命中 `requires_approval` 的动作进入 human approval 队列，不得由 LLM 自行确认。
- 每个外部动作须携带 `business_idempotency_key`，窗口规则沿用 [Statement Bus](v18_05_bus.md) §5.4。
- Guard 失败默认 fail-closed，emit `action.policy_blocked`，并在 `PipelineRun.warnings/counters` 中可见。

## 数据结构

### Commitment 五态枚举

```python
class CommitmentState(str, Enum):
    created      = "created"
    ACTIVE       = "ACTIVE"
    FULFILLED    = "FULFILLED"
    BROKEN       = "BROKEN"
    RENEGOTIATED = "RENEGOTIATED"
    WITHDRAWN    = "WITHDRAWN"
```

### 四类 Trigger

```python
class Trigger(BaseModel):
    kind: Literal["time", "event", "state", "compound"]
    spec: TriggerSpec

# 具体类型
TimeTrigger(at=datetime(...))
TimeTrigger(every="1d at 09:00")
EventTrigger(when="cognizer:Alice.observed")
EventTrigger(when="statement.written: predicate=mentions, object=X")
StateTrigger(predicate="goal:onboarding.completed")
CompoundTrigger(all_of=[...])   # AND
CompoundTrigger(any_of=[...])   # OR
```

### ActionGuard（P3 默认）

```python
class ActionGuard(BaseModel):
    profile_name: str
    allowed_actions: set[str]
    requires_approval: set[str]
    idempotency_window: dict[str, timedelta]
```

### Bus 事件 schema

| 事件 | 字段 | 说明 |
|---|---|---|
| `commitment.active_holding` | `commitment_id`, `related_stmt_ids: list[str]` | 转 ACTIVE 时 emit，保护关联 Statement |
| `commitment.released` | `commitment_id` | 转 FULFILLED 或 WITHDRAWN 时 emit，解除保护 |
| `commitment.fire` | `commitment_id`, `trigger_kind`, `triggered_at` | Trigger 命中时 emit |
| `commitment.fulfilled` | `commitment_id` | 用户履行时 emit |
| `commitment.broken` | `commitment_id`, `broken_count` | deadline 过期未达上限时 emit |
| `commitment.auto_withdrawn` | `commitment_id`, `reason` | 慢性失信自动 WITHDRAWN |
| `commitment.renegotiated` | `commitment_id`, `supersedes` | 协商成功时 emit |
| `commitment.withdrawn` | `commitment_id` | 主动撤回时 emit |
| `commitment.renegotiation_blocked` | `commitment_id`, `chain_len` | 链长超限时 emit |
| `action.policy_blocked` | `action_name`, `commitment_id` | ActionGuard 拒绝时 emit |

### Norm 与 Commitment 的关系

Norm 是 Group 内的默认行为规则；违反时 emit `norm.violated`，作为高 salience EpisodicEvent 进入 Affect Buffer。Commitment 是个体对个体的具体承诺。两者通过 `induce_norm` 操作（§10.3）连接：多次相似 Commitment 模式可凝结为 Norm 候选，由 Cognizer Hub 写入群组级 Norm 表。

### ActionPolicyGraph（P5 可选完整版）

```python
class ActionPolicyRule(BaseModel):
    kind: Literal[
        "init",                 # 动作链入口
        "parent_child",         # 父动作允许子动作
        "conditional",          # 条件分支
        "max_count",            # 限制单次执行次数（防重复投递）
        "terminal",             # 结束当前 Prospective run
        "required_before_exit", # 前后置保证（如"发送提醒后必须记录 delivery receipt"）
        "requires_approval",    # 人工审批才能执行
    ]
    action_name: str
    target_actions: list[str] = []
    condition: Optional[str]
    max_count: Optional[int]
    prefilled_args: dict = {}

class ActionPolicyGraph(BaseModel):
    profile_name: str
    rules: list[ActionPolicyRule]
    audit_mode: Literal["enforce", "dry_run", "disabled"] = "enforce"
```

`max_count` 与 [Statement Bus](v18_05_bus.md) §5.4 `business_idempotency_window` 互补：前者限制单次 action graph 内执行次数，后者限制 at-least-once 事件重复。`terminal` 动作结束该 Prospective run，后续动作须新建 `causation_chain`。

## 相关概念

**Trigger 类型系统**
PolicyEngine 内部维护 Trigger Index（哈希表）和时间堆（min-heap），TimeTrigger 基于堆轮询，EventTrigger 订阅 Bus 事件流，StateTrigger 在每次 Bus 事件落库后检查谓词，CompoundTrigger 递归组合。

**Commitment 五态机**
`created → ACTIVE → {FULFILLED / BROKEN / RENEGOTIATED / WITHDRAWN}`，所有终态都须经 Bus outbox 发布事件。BROKEN 不是终态，允许 `BROKEN → RENEGOTIATED` 迁移（对应现实"后来又答应了"场景）。

**ACTIVE 保护事件 commitment.active_holding**
设计意图：Replay decay scheduler 需要排除"未结清 Commitment 的关联 Statement"，若每次 decay 选取候选时查询 Commitment 表，代价为 O(N×M)（N 条 Statement × M 个活跃 Commitment）。改用 in-memory set + Bus 事件维护，命中检查降为 O(1)，且 set 状态通过 boot replay 保证持久化语义。

**ActionGuard**
最小动作护栏，三字段控制"哪些动作可执行、哪些需审批、幂等窗口多长"。P3 默认仅 ActionGuard；P5+ 升级为 ActionPolicyGraph，支持多步前后置、条件分支与复杂工具链。

**ActionPolicyGraph（P5 可选）**
完整动作策略图，8 种规则类型覆盖 init / parent_child / conditional / max_count / terminal / required_before_exit / requires_approval。`audit_mode` 支持 enforce / dry_run / disabled 三挡。

**PolicyEngine 与 Bus 关系**
PolicyEngine 是 [Statement Bus](v18_05_bus.md) 的 publisher 之一，同时也是 Bus 订阅者（订阅 commitment.fulfilled / broken / renegotiated / withdrawn 用于 Trigger 清理和 trust_priors 调整）。所有外发事件经 `Bus.emit`，所有内入事件来自 Bus，满足 §5"所有读写必经 Bus"硬约束。

**Norm 与 Commitment 的关系**
Norm 作用于 Group 级默认规则，Commitment 作用于个体间具体约定。`induce_norm` 操作将高频 Commitment 模式提炼为 Norm 候选；Norm 违反产生的 `norm.violated` 事件与 Commitment 的 `commitment.broken` 事件在 Affect Buffer 均作为高 salience EpisodicEvent 处理，但归属层次不同。

**引用**
- 事件总线契约：[Statement Bus](v18_05_bus.md)
- trust_priors 下调公式：[Cognizer Hub](v18_08_cognizer.md) §8.3
- decay scheduler 例外条款：[Replay Scheduler](v18_10_replay.md) §3.4
- ToM 推断 supersedes 链展开：[ToM Engine](v18_09_tom.md) §9.2


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
